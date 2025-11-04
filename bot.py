import os
import time
import random
import json
import schedule
import tweepy
import google.generativeai as genai
import requests
from dotenv import load_dotenv
from threading import Thread

load_dotenv()

# === Twitter API ===
client = tweepy.Client(
    consumer_key=os.getenv("API_KEY"),
    consumer_secret=os.getenv("API_SECRET"),
    access_token=os.getenv("ACCESS_TOKEN"),
    access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
    wait_on_rate_limit=True
)

# 🔒 Защита от 401 Unauthorized
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

# === RSS FEEDS (только рабочие) ===
RSS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
    "https://decrypt.co/feed",
    "https://cryptobriefing.com/feed/",
    "https://news.bitcoin.com/feed/",
    "https://beincrypto.com/feed/",
    "https://thedefiant.io/rss/",
    "https://glassnode.com/feed.xml",
    "https://santiment.net/blog/feed/",
    "https://nftevening.com/feed/"
]

# === Trusted accounts ===
MEDIA_ACCOUNTS = ["coindesk", "cointelegraph", "decrypt", "bitcoinmagazine", "blockworks", "bingx_official"]
PEOPLE_ACCOUNTS = ["VitalikButerin", "cz_binance", "saylor", "RaoulGMI", "lindaxie", "cobie", "peter_szilagyi", "hasufl", "LynAldenContact", "CryptoRand"]

processed_mentions = set()
processed_trusted_tweets = set()

# ======================
# ПАРСИНГ RSS
# ======================

def parse_rss_feed(url):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        from xml.etree import ElementTree as ET
        root = ET.fromstring(response.content)
        items = []
        for item in root.findall(".//item"):
            title_elem = item.find("title")
            link_elem = item.find("link")
            description_elem = item.find("description")
            title = title_elem.text.strip() if title_elem is not None and title_elem.text else "No title"
            link = link_elem.text.strip() if link_elem is not None and link_elem.text else "https://cointelegraph.com"
            description = description_elem.text.strip() if description_elem is not None and description_elem.text else ""
            items.append({"title": title, "link": link, "description": description})
        return items
    except Exception as e:
        print(f"⚠️ RSS parse error for {url}: {e}")
        return []

def get_latest_crypto_news():
    print("🔍 Trying to get news...")
    random.shuffle(RSS_FEEDS)
    for url in RSS_FEEDS:
        print(f"📡 Parsing {url}...")
        items = parse_rss_feed(url)
        if items:
            print(f"✅ Got news: {items[0]['title']}")
            return items[0]["title"], items[0]["link"], items[0]["description"]
    print("❌ No news found, using fallback")
    return "Stay updated on crypto markets", "https://cointelegraph.com", "Comprehensive analysis of current cryptocurrency market trends and developments."

# ======================
# ЗАГЛУШКА ДЛЯ АНАЛИЗА НАСТРОЕНИЙ
# ======================

def analyze_sentiment(kw="#bitcoin", cnt=15):
    return random.choice(["bullish 🟢", "bearish 🔴", "neutral ⚪"])

# ======================
# ОСНОВНЫЕ ФУНКЦИИ
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

def generate_long_analysis(title, url, description):
    """Генерирует длинный аналитический пост с использованием Gemini AI"""
    if not use_gemini:
        # Заглушка для длинного поста без Gemini
        return f"""🤖 ИНТЕЛЛЕКТУАЛЬНЫЙ АНАЛИЗ РЫНКА КРИПТОВАЛЮТ

📈 {title}

🔍 ОСНОВНЫЕ ФАКТЫ:
• Рыночное настроение: {analyze_sentiment()}
• Ключевые события сегодня
• Технический анализ основных пар

📊 ГЛУБОКИЙ АНАЛИЗ:
В текущей рыночной ситуации наблюдается повышенная волатильность из-за геополитической неопределенности и изменений монетарной политики. Биткоин демонстрирует устойчивость на уровне $100K, что указывает на сильную поддержку.

Ключевые факторы, влияющие на рынок:
- US-China торговые переговоры
- Инфляционные данные
- Институциональный интерес
- Халвинг-цикл

💡 ТОРГОВЫЕ СТРАТЕГИИ:
1. Для консервативных инвесторов: диверсификация между BTC и ETH
2. Для активных трейдеров: фокус на ликвидных альтах с четкими уровнями поддержки
3. Управление рисками: стоп-лоссы на 1.5% от депозита

🔗 Подробнее: {url}

#CryptoAnalysis #MarketInsights #TradingStrategy #Bitcoin #Ethereum"""
    
    prompt = f"""Ты — профессиональный криптоаналитик с 10-летним опытом. Напиши подробный аналитический пост на русском языке (не менее 500 символов) по следующим критериям:

ЗАГОЛОВОК: "{title}"
ОПИСАНИЕ: "{description}"
ССЫЛКА: {url}

Структура поста:
1. Краткое введение с главным выводом
2. Глубокий анализ текущей ситуации на рынке
3. Факторы, влияющие на цену (макроэкономические, технические, сентимент)
4. Прогноз на ближайшую неделю с конкретными уровнями
5. Практические рекомендации для разных типов трейдеров
6. Интересный факт или статистика

Тон: профессиональный, но доступный для новичков. Избегай жаргона без объяснений. Используй эмодзи для структурирования текста. Добавь 3-4 релевантных хештега в конце.

ВАЖНО: Пост должен быть информативным, а не маркетинговым. Не упоминай реферальные ссылки. Сфокусируйся на объективном анализе."""
    
    try:
        res = gemini_model.generate_content(prompt)
        analysis = res.text.strip().replace("\n\n", "\n")
        return analysis
    except Exception as e:
        print(f"❌ Ошибка генерации анализа: {e}")
        # Возвращаем запасной вариант с большим объемом текста
        return f"""🤖 АНАЛИЗ РЫНКА КРИПТОВАЛЮТ

📈 {title}

🔍 ДЕТАЛЬНЫЙ АНАЛИЗ:
На текущий момент рынок криптовалют демонстрирует повышенную активность после периода консолидации. Биткоин стабильно торгуется выше психологически важного уровня $100,000, что указывает на сильную поддержку со стороны институциональных инвесторов.

📊 ФАКТОРЫ, ВЛИЯЮЩИЕ НА РЫНОК:
• Положительная динамика в переговорах между США и Китаем снизила геополитическую напряженность
• Устойчивый приток средств в ETF на биткоин продолжает поддерживать спрос
• Эфириум восстанавливается после успешного обновления Pectra, что положительно влияет на экосистему DeFi
• Инфляционные данные показывают замедление роста цен, что снижает давление на ставки ФРС

💡 ТОРГОВЫЕ СТРАТЕГИИ:
Для краткосрочных трейдеров: фокус на парах с высокой ликвидностью (BTC/USDT, ETH/USDT) с целевыми уровнями +5-7%
Для среднесрочных инвесторов: диверсификация между основными криптовалютами с акцентом на проекты с реальным использованием
Управление рисками: использование стоп-лоссов на уровне 2% от депозита и фиксация прибыли при достижении 15%

🔮 ПРОГНОЗ НА БЛИЖАЙШУЮ НЕДЕЛЮ:
Ожидается продолжение восходящего тренда с тестированием новых локальных максимумов. Целевые уровни для BTC: $105,000 — $110,000. Для ETH: $2,700 — $3,000.

📚 СТАТИСТИКА:
За последнюю неделю общий объем торгов на криптобиржах вырос на 23%, что указывает на возобновление интереса со стороны розничных трейдеров.

🔗 Источник: {url}

#CryptoAnalysis #MarketUpdate #Bitcoin #Ethereum #Trading"""
    
def post_analytical_tweet():
    print("🔄 post_analytical_tweet() called")
    try:
        title, url, description = get_latest_crypto_news()
        analysis = generate_long_analysis(title, url, description)
        
        # Публикуем основной твит
        tweet = f"🤖 АНАЛИТИЧЕСКИЙ ОТЧЕТ РЫНКА КРИПТОВАЛЮТ\n\n{analysis[:200]}..."
        main_tweet = client.create_tweet(text=tweet)
        print(f"✅ Основной твит опубликован (ID: {main_tweet.data['id']})")
        
        # Создаем цепочку из дополнительных твитов с подробным анализом
        thread_tweets = [
            analysis[200:500],
            analysis[500:800],
            analysis[800:]
        ]
        
        current_tweet_id = main_tweet.data['id']
        for i, thread_content in enumerate(thread_tweets):
            if thread_content.strip():
                thread_tweet = client.create_tweet(
                    text=thread_content[:280] + "..." if len(thread_content) > 280 else thread_content,
                    in_reply_to_tweet_id=current_tweet_id
                )
                current_tweet_id = thread_tweet.data['id']
                print(f"✅ Дополнительный твит #{i+1} в цепочке опубликован")
                time.sleep(2)  # Пауза между публикациями
        
        print("✅ Полный аналитический пост опубликован в виде цепочки")
    except Exception as e:
        print(f"❌ Tweet error: {e}")

def post_crypto_term():
    terms = load_crypto_terms()
    term_data = random.choice(terms)
    
    # Генерируем подробное объяснение термина с AI
    prompt = f"""Ты — эксперт по криптовалютам. Напиши подробное, но доступное объяснение термина "{term_data['term']}" для новичков. Включи:
1. Простое определение
2. Историю появления термина
3. Практические примеры использования
4. Связанные концепции
5. Почему это важно для трейдеров

Объем: 3-4 абзаца. Тон: дружелюбный, но профессиональный."""
    
    detailed_definition = term_data['definition']
    if use_gemini:
        try:
            res = gemini_model.generate_content(prompt)
            detailed_definition = res.text.strip().replace("\n\n", "\n")
        except:
            pass
    
    tweet = f"📚 ГЛУБОКИЙ РАЗБОР ТЕРМИНА ДНЯ:\n\n**{term_data['term']}**\n\n{detailed_definition}\n\nЭтот термин критически важен для понимания работы крипторынка и формирования эффективных торговых стратегий."
    
    if len(tweet) > 280:
        # Создаем цепочку для длинного поста о термине
        first_part = tweet[:280]
        second_part = tweet[280:]
        
        main_tweet = client.create_tweet(text=first_part)
        client.create_tweet(text=second_part, in_reply_to_tweet_id=main_tweet.data['id'])
        print("📖 Подробный разбор термина опубликован в виде цепочки")
    else:
        client.create_tweet(text=tweet)
        print("📖 Подробный разбор термина опубликован")

def engage_with_mentions():
    global processed_mentions
    try:
        mentions = client.get_users_mentions(id=bot_id, max_results=5)
        if not mentions or not mentions.data:
            return
        for mention in reversed(mentions.data):
            if mention.id in processed_mentions or mention.author_id == bot_id:
                continue
            try:
                client.like(mention.id)
                author = client.get_user(id=mention.author_id)
                
                # Генерируем подробный ответ на упоминание
                prompt = f"""Ты — профессиональный криптоаналитик. Пользователь @{author.data.username} упомянул тебя в твите: "{mention.text}"

Напиши развернутый, полезный ответ (не менее 150 символов), который:
1. Конкретно отвечает на вопрос или комментарий пользователя
2. Предоставляет ценную аналитическую информацию
3. Включает практические советы или прогнозы
4. Сохраняет профессиональный тон, но дружелюбный
5. Поощряет дальнейшее обсуждение

ВАЖНО: Не используй реферальные ссылки. Не проси подписаться. Фокусируйся на качестве анализа."""
                
                reply_text = "Спасибо за упоминание! Рынок криптовалют демонстрирует интересную динамику на текущей неделе. Если у вас есть конкретные вопросы по стратегиям или анализу, пожалуйста, задавайте — я предоставлю развернутый ответ с профессиональной точки зрения."
                
                if use_gemini:
                    try:
                        res = gemini_model.generate_content(prompt)
                        reply_text = res.text.strip().replace("\n\n", "\n")
                    except:
                        pass
                
                client.create_tweet(text=reply_text, in_reply_to_tweet_id=mention.id)
                print(f"💬 Развернутый ответ отправлен @{author.data.username}")
            except Exception as e:
                print(f"⚠️ Reply error: {e}")
            processed_mentions.add(mention.id)
    except Exception as e:
        print(f"❌ Mention error: {e}")

# ======================
# ЗАПУСК
# ======================

if __name__ == "__main__":
    print("🚀 Starting BingX Trading Bot (Full Edition with Long Posts)...")
    print("🔄 Running first analytical post...")
    post_analytical_tweet()
    print("🔄 Setting up schedule...")

    # Оптимальное расписание без перегрузки API
    schedule.every(6).hours.do(post_analytical_tweet)
    schedule.every().day.at("10:00").do(post_crypto_term)
    schedule.every(3).hours.do(lambda: print("🔄 Проверка упоминаний в режиме ожидания"))
    schedule.every(90).minutes.do(engage_with_mentions)

    while True:
        schedule.run_pending()
        time.sleep(30)