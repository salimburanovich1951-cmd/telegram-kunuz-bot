import os
import time
import threading
import html
import re
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

def get_article_image(link):
    """Maqola sahifasidan asosiy rasm havolasini ajratib olish"""
    try:
        resp = session.get(link, timeout=7)
        if resp.status_code == 200:
            # 1. Kun.uz Next.js storage rasmlarini qidirish
            matches = re.findall(r'https://storage\.kun\.uz/source/[^"\'\s\\,]+\.(?:jpg|jpeg|png|webp)', resp.text)
            if matches:
                return matches[0]
            # 2. og:image orqali tekshirish
            og = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', resp.text)
            if og and "og-default" not in og.group(1):
                return og.group(1)
    except Exception as e:
        print(f"⚠️ Rasm yuklashda ogohlantirish: {e}")
    return None

def format_news_message(entry):
    """Yangilik uchun sarlavha, mazmun, rukn va havolani chiroyli formatlash"""
    title = html.escape(entry.get("title", "").strip())
    summary = html.escape(entry.get("summary", "").strip())
    link = entry.get("link", "")

    # Rukn / Teg
    tags = entry.get("tags", [])
    tag_str = ""
    if tags and isinstance(tags, list) and tags[0].get("term"):
        term = tags[0].get("term").replace("-", "_").replace(" ", "_")
        tag_str = f"🏷 #{term}\n"

    # Telegram sendPhoto caption chegarasi 1024 belgi bo'lgani uchun matnni qisqartirish
    max_summary_len = 650
    if len(summary) > max_summary_len:
        summary = summary[:max_summary_len] + "..."

    if summary:
        message = f"📰 <b>{title}</b>\n\n{summary}\n\n{tag_str}🔗 <a href='{link}'>Batafsil o'qish (Kun.uz)</a>"
    else:
        message = f"📰 <b>{title}</b>\n\n{tag_str}🔗 <a href='{link}'>Batafsil o'qish (Kun.uz)</a>"

    return message

def send_to_telegram(caption, image_url=None):
    """Telegram guruhiga yoki kanaliga rasm va mazmuni bilan xabar yuborish funksiyasi"""
    if not TOKEN or TOKEN == "SIZNING_BOT_TOKENINGIZ":
        print("\n⚠️ DIQQAT: BOT_TOKEN ko'rsatilmagan!")
        return False

    target_chat_id = str(GROUP_CHAT_ID).strip()
    if target_chat_id.startswith("100"):
        target_chat_id = f"-{target_chat_id}"

    # 1. Agar rasm bo'lsa, avval rasm bilan yuborib ko'ramiz (sendPhoto)
    if image_url:
        photo_url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
        photo_payload = {
            "chat_id": target_chat_id,
            "photo": image_url,
            "caption": caption,
            "parse_mode": "HTML"
        }
        try:
            res = session.post(photo_url, json=photo_payload, timeout=15)
            data = res.json()
            if data.get("ok"):
                return True
            else:
                print(f"⚠️ sendPhoto xatosi ({data.get('description')}), matn sifatida yuboriladi...")
        except Exception as e:
            print(f"⚠️ sendPhoto ulanish xatosi: {e}, matn sifatida yuboriladi...")

    # 2. Rasm bo'lmasa yoki sendPhoto xato bersa, sendMessage orqali matn yuborish
    msg_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    msg_payload = {
        "chat_id": target_chat_id,
        "text": caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        response = session.post(msg_url, json=msg_payload, timeout=15)
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
        resp = session.get(RSS_URL, timeout=10)
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"❌ RSS o'qishda xatolik: {e}")
        return

    if not feed.entries:
        print("Yangiliklar topilmadi.")
        return

    # Agar bot mutlaqo birinchi marta ishga tushayotgan bo'lsa (sent_links bo'sh):
    if is_startup and not sent_links:
        print("ℹ️ Dastlabki ishga tushish: mavjud yangiliklar ro'yxatga olinmoqda...")
        for entry in feed.entries:
            norm = normalize_link(entry.get("link"))
            if norm:
                save_sent_link(norm)

        latest_entry = feed.entries[0]
        caption = format_news_message(latest_entry)
        image_url = get_article_image(latest_entry.get("link"))
        print(f"Eng so'nggi yangilik yuborilmoqda: {latest_entry.title}")
        if send_to_telegram(caption, image_url):
            print("✅ Dastlabki yangilik rasm va mazmuni bilan yuborildi.\n")
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
        save_sent_link(norm_link)
        caption = format_news_message(entry)
        image_url = get_article_image(entry.get("link"))
        
        if send_to_telegram(caption, image_url):
            print(f"✅ Yangi yangilik rasm va mazmuni bilan guruhga yuborildi: {entry.title}")
        time.sleep(2)  # Ketma-ket yuborilganda cheklovga tushmaslik uchun

if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Bot ishga tushdi!")
    print(f"Har {CHECK_INTERVAL} sekundda Kun.uz tekshirib boriladi.")
    print("Yangiliklar fotosurati, qisqacha mazmuni va havolasi bilan yuboriladi.")
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
