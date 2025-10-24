import os
import time
import random
import json
import feedparser
import schedule
import tweepy
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from transformers import pipeline

load_dotenv()
feedparser.USER_AGENT = "CryptoAIBot/1.0"

# === Twitter API ===
client = tweepy.Client(
    consumer_key=os.getenv("API_KEY"),
    consumer_secret=os.getenv("API_SECRET"),
    access_token=os.getenv("ACCESS_TOKEN"),
    access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
    wait_on_rate_limit=True
)

bot_id = client.get_me().data.id
print(f"🤖 Bot ID: {bot_id}")

# === Gemini AI ===
gemini_api_key = os.getenv("GEMINI_API_KEY")
use_gemini = bool(gemini_api_key)

if use_gemini:
    genai.configure(api_key=gemini_api_key)
    gemini_model = genai.GenerativeModel(
        "gemini-1.5-flash",
        safety_settings={k: "BLOCK_NONE" for k in [
            "HARM_CATEGORY_HARASSMENT",
            "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "HARM_CATEGORY_DANGEROUS_CONTENT"
        ]}
    )
    print("✅ Gemini AI enabled")
else:
    print("⚠️ No GEMINI_API_KEY")

# === Sentiment Model ===
print("🧠 Loading sentiment model...")
sentiment_model = pipeline(
    "sentiment-analysis",
    model="cardiffnlp/twitter-roberta-base-sentiment-latest",
    tokenizer="cardiffnlp/twitter-roberta-base-sentiment-latest"
)

# === RSS FEEDS ===
RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://cryptobriefing.com/feed/",
    "https://news.bitcoin.com/feed/",
    "https://bitcoinmagazine.com/.rss/full/",
    "https://beincrypto.com/feed/",
    "https://thedefiant.io/rss/",
    "https://blockworks.co/news/feed/",
    "https://glassnode.com/feed.xml",
    "https://santiment.net/blog/feed/",
    "https://ethereum.org/en/rss/blog.xml",
    "https://blog.chain.link/rss.xml",
    "https://polygon.technology/blog/rss.xml",
    "https://nftnow.com/feed/",
    "https://nftevening.com/feed/",
    "https://www.coindesk.com/policy/feed/"
]

# === Trusted accounts ===
MEDIA_ACCOUNTS = ["coindesk", "cointelegraph", "decrypt", "bitcoinmagazine", "blockworks", "bingx_official"]
PEOPLE_ACCOUNTS = ["VitalikButerin", "cz_binance", "saylor", "RaoulGMI", "lindaxie", "cobie", "peter_szilagyi", "hasufl", "LynAldenContact", "CryptoRand"]

processed_mentions = set()
processed_trusted_tweets = set()

# ======================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ======================

def load_crypto_terms():
    try:
        with open("crypto_terms.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return [{"term": "Blockchain", "definition": "A decentralized ledger."}]

def get_crypto_prices():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd", timeout=5)
        data = res.json()
        return f"BTC: ${data['bitcoin']['usd']:,} | ETH: ${data['ethereum']['usd']:,}"
    except:
        return "BTC & ETH prices unavailable"

def should_reply_with_price(text):
    return any(kw in text.lower() for kw in ["price", "btc", "eth", "bitcoin", "ethereum"])

def get_latest_crypto_news():
    random.shuffle(RSS_FEEDS)
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                e = feed.entries[0]
                return e.get("title", "Market update").strip(), e.get("link", "https://cointelegraph.com")
        except: pass
    return "Stay updated", "https://cointelegraph.com"

def summarize_news(title, url):
    if not use_gemini: return f"{title[:100]}..." if len(title) > 100 else title
    prompt = f"Pro crypto analyst. Summarize in one tweet (max 120 chars): '{title}'. Source: {url}"
    try:
        res = gemini_model.generate_content(prompt)
        s = res.text.strip().replace("\n", " ")
        return s[:117] + "..." if len(s) > 120 else s
    except: return title[:100]

def analyze_sentiment(kw="#bitcoin", cnt=15):
    try:
        tweets = client.search_recent_tweets(query=kw + " -is:retweet lang:en", max_results=min(cnt, 100))
        if not tweets or not tweets.data:
            return "neutral ⚪"
        pos = neg = 0
        for t in [tw.text for tw in tweets.data][:10]:
            lbl = sentiment_model(t[:512])[0]['label']
            if lbl == 'LABEL_2': pos += 1
            elif lbl == 'LABEL_0': neg += 1
        return "bullish 🟢" if pos > neg else "bearish 🔴" if neg > pos else "neutral ⚪"
    except: return "unknown ❓"

# ======================
# ГЛАВНАЯ ФУНКЦИЯ ОТВЕТОВ (DERZKY TRADER MODE)
# ======================

def generate_reply(text, username, author_id):
    text_lower = text.lower()
    include_ref = random.random() < 0.3
    ref = os.getenv("REFERRAL_LINK", "https://www.bingx.com") if include_ref else ""
    ref_suffix = f" → {ref}" if ref else ""

    # === НЕГАТИВ ===
    negative_keywords = ["lost", "scam", "rip", "angry", "hate", "bad signal", "wrong", "dumped", "rekt", "sucks", "fuck", "wtf"]
    if any(kw in text_lower for kw in negative_keywords):
        replies = [
            "Lost because you ignored your stop-loss? Amateur hour.",
            "Your R:R is negative because your discipline is zero.",
            "Rekt? You traded without an edge. That’s gambling, not trading.",
            "Markets don’t care about your PnL. Neither do I.",
            "You got stopped out? Good. Now you’ll learn to respect liquidity grabs."
        ]
        reply = random.choice(replies) + ref_suffix
        return reply if len(reply) <= 280 else reply[:277] + "..."

    # === БЛАГОДАРНОСТИ ===
    if any(kw in text_lower for kw in ["thank", "thx", "gracias", "cheers", "appreciate", "nice", "good call"]):
        replies = [
            "You’re welcome. Now go compound that PnL.",
            "Don’t thank me — thank your discipline for following the setup.",
            "Glad the R:R worked out. Now find the next A+ entry.",
            "Thanks? Nah. Show me your closed PnL screenshot.",
            "Appreciate the signal? Now appreciate your risk management."
        ]
        reply = random.choice(replies) + ref_suffix
        return reply if len(reply) <= 280 else reply[:277] + "..."

    # === ЗАПРОС ЦЕНЫ ===
    if should_reply_with_price(text):
        prices = get_crypto_prices()
        replies = [
            f"{prices}. Price is at key support. Your entry plan ready?",
            f"{prices}. Volume drying up — expect volatility expansion.",
            f"{prices}. Open interest rising — smart money loading.",
            f"{prices}. Daily RSI oversold. Accumulation zone or trap?",
            f"{prices}. Liquidity pool below at $66.5K. Watch for sweep."
        ]
        reply = random.choice(replies) + ref_suffix
        return reply if len(reply) <= 280 else reply[:277] + "..."

    # === НОВИЧКИ ===
    beginner_keywords = ["how to start", "beginner", "new", "first time", "guide", "help", "where to buy"]
    if any(kw in text_lower for kw in beginner_keywords):
        replies = [
            "Step 1: Learn price action. Step 2: Master risk management. Step 3: Trade small.",
            "New? Good. Now learn: trading ≠ gambling. Start with 1% risk per trade.",
            "Best exchange? The one with deep liquidity and low slippage. BingX has it.",
            "Guide? 1. Study support/resistance 2. Define your R:R 3. Journal every trade.",
            "Still asking? Your edge is zero. Go study candlestick patterns."
        ]
        reply = random.choice(replies) + ref_suffix
        return reply if len(reply) <= 280 else reply[:277] + "..."

    # === ОБЩИЕ УПОМИНАНИЯ ===
    general_replies = [
        "You’re either here to trade or watch others get rich. Which one?",
        "Scrolling charts or executing setups? Choose fast.",
        "Free signals. Zero cost. All you need is discipline and 1% risk.",
        "95% of traders fail because they lack edge. You look like the 5%.",
        "AI doesn’t sleep. Markets don’t close. What’s your trading plan?"
    ]
    
    if use_gemini:
        prompt = f"You're a veteran crypto trader. User @{username} mentioned you: \"{text}\"\nReply in English (max 200 chars) with professional trading jargon. Optionally add CTA to BingX: {ref}. No hashtags."
        try:
            res = gemini_model.generate_content(prompt)
            ai_reply = res.text.strip().replace("\n", " ")
            if 20 < len(ai_reply) <= 200: return ai_reply
        except: pass

    final_reply = random.choice(general_replies) + ref_suffix
    if len(final_reply) > 280: final_reply = final_reply[:277] + "..."

    if len(text) < 30 and not any(k in text_lower for k in ["thank", "price", "btc", "eth", "signal", "bingx"]):
        challenges = ["\n\nStill reading? Your PnL is bleeding. GO TRADE WITH EDGE.", "\n\nFollow me or stay a weak hand. Your choice."]
        extra = random.choice(challenges)
        if len(final_reply + extra) <= 280: final_reply += extra

    return final_reply

# ======================
# ОСНОВНЫЕ ФУНКЦИИ ПУБЛИКАЦИИ
# ======================

def post_crypto_term():
    terms = load_crypto_terms()
    term_data = random.choice(terms)
    tweet = f"📚 Crypto Term of the Day:\n\n**{term_data['term']}** — {term_data['definition']}\n\nStart trading on BingX with bonus 👉 {os.getenv('REFERRAL_LINK', 'https://www.bingx.com')}"
    if len(tweet) > 280: tweet = tweet[:277] + "..."
    try: client.create_tweet(text=tweet); print("📖 Term posted")
    except: pass

def repost_trusted_content():
    media_part = " OR ".join([f"from:{acc}" for acc in MEDIA_ACCOUNTS])
    people_part = " OR ".join([f"from:{acc}" for acc in PEOPLE_ACCOUNTS])
    query = f"({media_part}) OR ({people_part}) (bitcoin OR ethereum OR crypto OR halving OR ETF OR defi OR market)"
    try:
        tweets = client.search_recent_tweets(query=query, max_results=20)
        if not tweets or not tweets.data: return
        for tweet in tweets.data:
            if tweet.id in processed_trusted_tweets or "RT @" in tweet.text or len(tweet.text) < 30: continue
            try: client.retweet(tweet.id); processed_trusted_tweets.add(tweet.id); time.sleep(2)
            except: processed_trusted_tweets.add(tweet.id)
    except: pass

def generate_daily_thread():
    if not use_gemini: return None
    prompt = f"You are a top crypto analyst. Create a 5-tweet thread about today's market.\n1/5 [Headline]\n2/5 [Sentiment]\n3/5 [BTC & ETH]\n4/5 [Top 3 alts]\n5/5 [Outlook + 'Start trading on BingX with bonus 👉 {os.getenv('REFERRAL_LINK', 'https://www.bingx.com')}']\nNo hashtags. Max 260 chars per tweet."
    try:
        res = gemini_model.generate_content(prompt)
        lines = [l.strip() for l in res.text.split("\n") if l.strip()]
        tweets = [l for l in lines if any(l.startswith(f"{i}/5") for i in range(1,6))]
        return tweets[:5] if len(tweets) >= 3 else None
    except: return None

def post_thread():
    tweets = generate_daily_thread()
    if not tweets: return
    try:
        first = client.create_tweet(text=tweets[0])
        cid = first.data["id"]
        for t in tweets[1:]: 
            if len(t) > 280: t = t[:277] + "..."
            reply = client.create_tweet(text=t, in_reply_to_tweet_id=cid)
            cid = reply.data["id"]
            time.sleep(2)
        print("✅ Thread posted")
    except: pass

def should_retweet(text):
    return any(kw in text.lower() for kw in ["thank", "useful", "great", "accurate"])

def engage_with_mentions():
    global processed_mentions
    try:
        mentions = client.get_users_mentions(id=bot_id, max_results=20)
        if not mentions or not mentions.data: return
        for mention in reversed(mentions.data):
            if mention.id in processed_mentions or mention.author_id == bot_id: continue
            try:
                client.like(mention.id)
                if should_retweet(mention.text): client.retweet(mention.id)
                author = client.get_user(id=mention.author_id)
                reply_text = generate_reply(mention.text, author.data.username, mention.author_id)
                client.create_tweet(text=reply_text, in_reply_to_tweet_id=mention.id)
                print(f"💬 Replied to @{author.data.username}")
            except: pass
            processed_mentions.add(mention.id)
            time.sleep(3)
    except: pass

def post_analytical_tweet():
    try:
        title, url = get_latest_crypto_news()
        sentiment = analyze_sentiment()
        summary = summarize_news(title, url)
        ref = os.getenv("REFERRAL_LINK", "https://www.bingx.com")
        tweet = f"🤖 AI Crypto Pulse\n\nMarket sentiment: {sentiment}\n📰 {summary}\n{url}\n\nStart trading on BingX with bonus 👉 {ref}"
        if len(tweet) > 280: tweet = tweet[:277] + "..."
        client.create_tweet(text=tweet)
        print("✅ Analytical tweet posted")
    except: pass

# ======================
# ЗАПУСК
# ======================

if __name__ == "__main__":
    print("🚀 Starting BingX Trading Bot (Derzky Trader Mode)...")
    post_analytical_tweet()
    schedule.every(3).hours.do(post_analytical_tweet)
    schedule.every().day.at("09:00").do(post_thread)
    schedule.every().day.at("14:00").do(post_crypto_term)
    schedule.every(30).minutes.do(repost_trusted_content)
    schedule.every(5).minutes.do(engage_with_mentions)

    while True:
        schedule.run_pending()
        time.sleep(30)