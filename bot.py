import os
import time
import random
import json
import schedule
import tweepy
import google.generativeai as genai
import requests
from dotenv import load_dotenv

load_dotenv()

# === Twitter API ===
client = tweepy.Client(
    consumer_key=os.getenv("API_KEY"),
    consumer_secret=os.getenv("API_SECRET"),
    access_token=os.getenv("ACCESS_TOKEN"),
    access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
    wait_on_rate_limit=True
)

# 🔒 Защита от ошибки 401 при запуске
try:
    me = client.get_me()
    if not me or not me.data:
        raise Exception("Не удалось получить данные аккаунта. Проверь ключи и разрешения в X Developer Portal.")
    bot_id = me.data.id
    print(f"🤖 Bot ID: {bot_id}")
except Exception as e:
    print(f"❌ Ошибка авторизации: {e}")
    exit(1)

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
    print("✅ Gemini AI включён")
else:
    print("⚠️ GEMINI_API_KEY не задан")

# === RSS-ленты (без лишних пробелов) ===
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
    "https://nftnow.com/feed/",
    "https://nftevening.com/feed/",
    "https://www.coindesk.com/policy/feed/"
]

# === Доверенные аккаунты ===
MEDIA_ACCOUNTS = ["coindesk", "cointelegraph", "decrypt", "bitcoinmagazine", "blockworks", "bingx_official"]
PEOPLE_ACCOUNTS = ["VitalikButerin", "cz_binance", "saylor", "RaoulGMI", "lindaxie", "cobie", "peter_szilagyi", "hasufl", "LynAldenContact", "CryptoRand"]

processed_mentions = set()
processed_trusted_tweets = set()

# ======================
# ПАРСИНГ RSS БЕЗ FEEDPARSER
# ======================

def parse_rss_feed(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.content)
        items = []
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else "No title"
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else "https://cointelegraph.com"
            items.append({"title": title, "link": link})
        return items
    except Exception as e:
        print(f"⚠️ Ошибка парсинга RSS {url}: {e}")
        return []

def get_latest_crypto_news():
    print("🔍 Ищу свежие новости...")
    random.shuffle(RSS_FEEDS)
    for url in RSS_FEEDS:
        print(f"📡 Парсинг: {url}...")
        items = parse_rss_feed(url)
        if items:
            print(f"✅ Новость найдена: {items[0]['title']}")
            return items[0]["title"], items[0]["link"]
    print("❌ Новости не найдены, использую заглушку")
    return "Следи за крипторынком", "https://cointelegraph.com"

# ======================
# ЗАГЛУШКА ДЛЯ АНАЛИЗА НАСТРОЕНИЙ
# ======================

def analyze_sentiment(kw="#bitcoin", cnt=15):
    return random.choice(["бычье 🟢", "медвежье 🔴", "нейтральное ⚪"])

# ======================
# ОСТАЛЬНЫЕ ФУНКЦИИ
# ======================

def load_crypto_terms():
    try:
        with open("crypto_terms.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return [{"term": "Blockchain", "definition": "Децентрализованный реестр."}]

def get_crypto_prices():
    try:
        res = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd", timeout=5)
        data = res.json()
        return f"BTC: ${data['bitcoin']['usd']:,} | ETH: ${data['ethereum']['usd']:,}"
    except:
        return "Цены недоступны"

def should_reply_with_price(text):
    return any(kw in text.lower() for kw in ["price", "btc", "eth", "bitcoin", "ethereum"])

def summarize_news(title, url):
    if not use_gemini:
        return f"{title[:100]}..." if len(title) > 100 else title
    prompt = f"Профессиональный аналитик. Кратко перескажи в один твит (макс 120 символов): '{title}'. Источник: {url}"
    try:
        res = gemini_model.generate_content(prompt)
        s = res.text.strip().replace("\n", " ")
        return s[:117] + "..." if len(s) > 120 else s
    except:
        return title[:100]

def generate_reply(text, username, author_id):
    text_lower = text.lower()
    include_ref = random.random() < 0.3
    ref = os.getenv("REFERRAL_LINK", "https://www.bingx.com") if include_ref else ""
    ref_suffix = f" → {ref}" if ref else ""

    negative_keywords = ["lost", "scam", "rip", "angry", "hate", "bad signal", "wrong", "dumped", "rekt", "sucks", "fuck", "wtf"]
    if any(kw in text_lower for kw in negative_keywords):
        replies = [
            "Потерял, потому что игнорировал стоп-лосс? Это уровень новичка.",
            "Твой R:R отрицательный, потому что дисциплины ноль.",
            "Rekt? Ты торговал без преимущества. Это азарт, а не трейдинг.",
            "Рынки не заботятся о твоём PnL. И я тоже.",
            "Сработал стоп? Отлично. Теперь научишься уважать ликвидность."
        ]
        reply = random.choice(replies) + ref_suffix
        return reply if len(reply) <= 280 else reply[:277] + "..."

    # ... (остальные функции generate_reply без изменений — оставь как есть)

    general_replies = [
        "Ты здесь, чтобы торговать или смотреть, как другие богатеют?",
        "Анализируешь графики или исполняешь сетапы? Выбирай быстро.",
        "Бесплатные сигналы. Ноль затрат. Всё, что нужно — дисциплина и 1% риска.",
        "95% трейдеров терпят неудачу, потому что у них нет преимущества. Ты из 5%?",
        "ИИ не спит. Рынки не закрываются. Какой у тебя план?"
    ]
    final_reply = random.choice(general_replies) + ref_suffix
    if len(final_reply) > 280:
        final_reply = final_reply[:277] + "..."
    return final_reply

def should_retweet(text):
    return any(kw in text.lower() for kw in ["thank", "useful", "great", "accurate"])

# ======================
# ФУНКЦИИ ПУБЛИКАЦИИ
# ======================

def post_crypto_term():
    terms = load_crypto_terms()
    term_data = random.choice(terms)
    tweet = f"📚 Термин дня:\n\n**{term_data['term']}** — {term_data['definition']}\n\nНачни торговать на BingX с бонусом 👉 {os.getenv('REFERRAL_LINK', 'https://www.bingx.com')}"
    if len(tweet) > 280:
        tweet = tweet[:277] + "..."
    try:
        client.create_tweet(text=tweet)
        print("📖 Термин опубликован")
    except Exception as e:
        print(f"❌ Ошибка публикации термина: {e}")

def repost_trusted_content():
    media_part = " OR ".join([f"from:{acc}" for acc in MEDIA_ACCOUNTS])
    people_part = " OR ".join([f"from:{acc}" for acc in PEOPLE_ACCOUNTS])
    query = f"({media_part}) OR ({people_part}) (bitcoin OR ethereum OR crypto)"
    try:
        tweets = client.search_recent_tweets(query=query, max_results=20)
        if not tweets or not tweets.data:
            return
        for tweet in tweets.data:
            if tweet.id in processed_trusted_tweets or "RT @" in tweet.text or len(tweet.text) < 30:
                continue
            try:
                client.retweet(tweet.id)
                print(f"🔁 Репост: {tweet.text[:50]}...")
                processed_trusted_tweets.add(tweet.id)
            except Exception as e:
                print(f"⚠️ Ошибка репоста: {e}")
                processed_trusted_tweets.add(tweet.id)
    except Exception as e:
        print(f"❌ Ошибка поиска для репоста: {e}")

def engage_with_mentions():
    global processed_mentions
    try:
        mentions = client.get_users_mentions(id=bot_id, max_results=20)
        if not mentions or not mentions.data:
            return
        for mention in reversed(mentions.data):
            if mention.id in processed_mentions or mention.author_id == bot_id:
                continue
            try:
                client.like(mention.id)
                if should_retweet(mention.text):
                    client.retweet(mention.id)
                author = client.get_user(id=mention.author_id)
                reply_text = generate_reply(mention.text, author.data.username, mention.author_id)
                client.create_tweet(text=reply_text, in_reply_to_tweet_id=mention.id)
                print(f"💬 Ответил @{author.data.username}")
            except Exception as e:
                print(f"⚠️ Ошибка ответа: {e}")
            processed_mentions.add(mention.id)
    except Exception as e:
        print(f"❌ Ошибка обработки упоминаний: {e}")

def post_analytical_tweet():
    print("🔄 Публикация аналитического твита...")
    try:
        title, url = get_latest_crypto_news()
        sentiment = analyze_sentiment()
        summary = summarize_news(title, url)
        ref = os.getenv("REFERRAL_LINK", "https://www.bingx.com")
        tweet = f"🤖 ИИ-пульс рынка\n\nНастроение: {sentiment}\n📰 {summary}\n{url}\n\nНачни торговать на BingX с бонусом 👉 {ref}"
        if len(tweet) > 280:
            tweet = tweet[:277] + "..."
        client.create_tweet(text=tweet)
        print("✅ Аналитический твит опубликован")
    except Exception as e:
        print(f"❌ Ошибка публикации: {e}")

# ======================
# ЗАПУСК
# ======================

if __name__ == "__main__":
    print("🚀 Запуск BingX Trading Bot...")
    post_analytical_tweet()  # первая публикация
    schedule.every(3).hours.do(post_analytical_tweet)
    schedule.every(30).minutes.do(repost_trusted_content)
    schedule.every(5).minutes.do(engage_with_mentions)

    while True:
        schedule.run_pending()
        time.sleep(30)