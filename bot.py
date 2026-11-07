import os
import time
import feedparser
import requests

# .env fayli mavjud bo'lsa, o'zgaruvchilarni yuklash
if os.path.exists(".env"):
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

# ==============================================================================
# --- SOZLAMALAR ---
# Token va Guruh ID muhit o'zgaruvchilaridan olinadi (xavfsizlik uchun)
TOKEN = os.getenv("BOT_TOKEN", "9196904535:AAFNzZJEdXWHN_7P4Xyag8uIBZxoQN9EqqE")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID", "-1003839580514")

# Yangiliklar RSS manzili
RSS_URL = "https://kun.uz/news/rss"

# Yangiliklarni tekshirish oralig'i (sekundlarda). 60 sekund = 1 daqiqa
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
# ==============================================================================

# Yuborilgan xabarlarning havolalarini eslab qolish to'plami
sent_links = set()

def send_to_telegram(text):
    """Telegram guruhiga yoki kanaliga xabar yuborish funksiyasi"""
    if not TOKEN or TOKEN == "SIZNING_BOT_TOKENINGIZ":
        print("\n⚠️ DIQQAT: BOT_TOKEN ko'rsatilmagan!")
        return False

    target_chat_id = str(GROUP_CHAT_ID).strip()
    if target_chat_id.startswith("100"):
        target_chat_id = f"-{target_chat_id}"

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": target_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False  # Rasm/prevyu ko'rinishi uchun
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()
        if res_data.get("ok"):
            return True
        else:
            print(f"❌ Telegram xatosi: {res_data.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Ulanishda xatolik yuz berdi: {e}")
        return False

def check_news(is_first_run=False):
    """Kun.uz RSS lentasini tekshirish va yangiliklarni yuborish"""
    print(f"[{time.strftime('%H:%M:%S')}] Yangiliklar tekshirilmoqda...")
    try:
        feed = feedparser.parse(RSS_URL)
    except Exception as e:
        print(f"❌ RSS o'qishda xatolik: {e}")
        return

    if not feed.entries:
        print("Yangiliklar topilmadi.")
        return

    # Bot birinchi marta ishga tushganda:
    # Barcha eski yangiliklarni eslab qoladi va eng so'nggi 1 tasini DARHOL guruhga yuboradi!
    if is_first_run:
        for entry in feed.entries:
            sent_links.add(entry.link)
        
        latest_entry = feed.entries[0]
        message = f"📰 <b>{latest_entry.title}</b>\n\n🔗 <a href='{latest_entry.link}'>Batafsil o'qish</a>"
        print(f"Eng so'nggi yangilik yuborilmoqda: {latest_entry.title}")
        if send_to_telegram(message):
            print("✅ Eng so'nggi yangilik darhol guruhga yuborildi!\n")
        return

    # Keyingi tekshiruvlarda: yangi chiqqan xabarlarni saralash
    new_entries = []
    for entry in feed.entries:
        if entry.link not in sent_links:
            new_entries.append(entry)

    if not new_entries:
        print("Yangi yangilik yo'q.")
        return

    # Yangi xabarlarni xronologik tartibda (eskiroqdan yangiroqqa) yuborish
    for entry in reversed(new_entries):
        message = f"📰 <b>{entry.title}</b>\n\n🔗 <a href='{entry.link}'>Batafsil o'qish</a>"
        if send_to_telegram(message):
            sent_links.add(entry.link)
            print(f"✅ Yangi yangilik guruhga yuborildi: {entry.title}")
            time.sleep(2)  # Ketma-ket yuborilganda cheklovga tushmaslik uchun

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Bot ishga tushdi!")
    print(f"Har {CHECK_INTERVAL} sekundda Kun.uz tekshirib boriladi.")
    print("To'xtatish uchun: Ctrl + C bosing.")
    print("=" * 50)

    # 1. Dastlabki ishga tushganda birdaniga oxirgi yangilikni yuboradi
    check_news(is_first_run=True)

    # 2. Doimiy tekshiruv tsikli
    while True:
        time.sleep(CHECK_INTERVAL)
        check_news(is_first_run=False)
