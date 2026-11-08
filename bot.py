import os
import time
import threading
import html
from http.server import HTTPServer, BaseHTTPRequestHandler
import feedparser
import requests

# Render, Railway va boshqa bulutli serverlar uchun kichik HTTP Health Server
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot 24/7 faol ishlamoqda!")

    def log_message(self, format, *args):
        return  # Konsolni ortiqcha loglar bilan to'ldirmaslik uchun

def start_health_server():
    port = int(os.getenv("PORT", "8080"))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        print(f"🌐 Health server {port}-portda ishga tushdi.")
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ Health server xatosi: {e}")

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

# Yuborilgan havolalarni saqlash fayli (bot qayta tushganda takrorlanmasligi uchun)
SENT_FILE = "sent_links.txt"
# ==============================================================================

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})

def normalize_link(link):
    """Havolani tozalash va bir xil formatga keltirish"""
    if not link:
        return ""
    return link.strip().split("?")[0].rstrip("/")

def load_sent_links():
    """Yuborilgan havolalarni fayldan yuklash"""
    links = set()
    if os.path.exists(SENT_FILE):
        try:
            with open(SENT_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    norm = normalize_link(line)
                    if norm:
                        links.add(norm)
        except Exception as e:
            print(f"⚠️ Faylni o'qishda xatolik: {e}")
    return links

def save_sent_link(link):
    """Yuborilgan yangilik havolasini xotiraga va faylga saqlash"""
    norm = normalize_link(link)
    if not norm:
        return
    sent_links.add(norm)
    try:
        with open(SENT_FILE, "a", encoding="utf-8") as f:
            f.write(f"{norm}\n")
    except Exception as e:
        print(f"⚠️ Faylga yozishda xatolik: {e}")

# Xotiradagi yuborilgan havolalar to'plami
sent_links = load_sent_links()

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
        response = session.post(url, json=payload, timeout=15)
        res_data = response.json()
        if res_data.get("ok"):
            return True
        else:
            print(f"❌ Telegram xatosi: {res_data.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Ulanishda xatolik yuz berdi: {e}")
        return False

def check_news(is_startup=False):
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

    # Agar bot mutlaqo birinchi marta ishga tushayotgan bo'lsa (sent_links bo'sh):
    # Mavjud barcha yangiliklarni eslab qoladi va faqat 1 ta eng so'nggisini yuboradi
    if is_startup and not sent_links:
        print("ℹ️ Dastlabki ishga tushish: mavjud yangiliklar ro'yxatga olinmoqda...")
        for entry in feed.entries:
            norm = normalize_link(entry.get("link"))
            if norm:
                save_sent_link(norm)

        latest_entry = feed.entries[0]
        safe_title = html.escape(latest_entry.get("title", "").strip())
        message = f"📰 <b>{safe_title}</b>\n\n🔗 <a href='{latest_entry.link}'>Batafsil o'qish</a>"
        print(f"Eng so'nggi yangilik yuborilmoqda: {latest_entry.title}")
        if send_to_telegram(message):
            print("✅ Dastlabki yangilik yuborildi va saqlandi.\n")
        return

    # Yangi xabarlarni saralash (avval yuborilmaganlari)
    new_entries = []
    for entry in feed.entries:
        norm = normalize_link(entry.get("link"))
        if norm and norm not in sent_links:
            new_entries.append((entry, norm))

    if not new_entries:
        print("Yangi yangilik yo'q.")
        return

    # Yangi xabarlarni xronologik tartibda (eskiroqdan yangiroqqa) yuborish
    for entry, norm_link in reversed(new_entries):
        safe_title = html.escape(entry.get("title", "").strip())
        message = f"📰 <b>{safe_title}</b>\n\n🔗 <a href='{entry.link}'>Batafsil o'qish</a>"
        
        # Takrorlanmasligi uchun darhol ro'yxatga saqlaymiz
        save_sent_link(norm_link)
        
        if send_to_telegram(message):
            print(f"✅ Yangi yangilik guruhga yuborildi: {entry.title}")
        time.sleep(2)  # Ketma-ket yuborilganda cheklovga tushmaslik uchun

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Bot ishga tushdi!")
    print(f"Har {CHECK_INTERVAL} sekundda Kun.uz tekshirib boriladi.")
    print("To'xtatish uchun: Ctrl + C bosing.")
    print("=" * 50)

    # Bulutli xizmatlar (Render, Railway va h.k.) 24/7 o'chmasligi uchun health server
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    # 1. Dastlabki ishga tushgandagi tekshiruv
    check_news(is_startup=True)

    # 2. Doimiy tekshiruv tsikli
    while True:
        time.sleep(CHECK_INTERVAL)
        check_news(is_startup=False)
