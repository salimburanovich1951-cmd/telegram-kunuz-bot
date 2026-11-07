# Telegram Kun.uz RSS Bot 📰🤖

Kun.uz saytidagi yangiliklarni avtomatik ravishda kuzatib boruvchi va Telegram guruh yoki kanallarga tezkorlik bilan yuboruvchi bot.

## 🚀 O'rnatish va Ishga tushirish

1. Kutubxonalarni o'rnatish:
```bash
pip install -r requirements.txt
```

2. `.env` faylida o'zgaruvchilarni sozlash:
```env
BOT_TOKEN=your_bot_token_here
GROUP_CHAT_ID=-100xxxxxxxxxx
CHECK_INTERVAL=60
```

3. Botni ishga tushirish:
```bash
python bot.py
```

## ☁️ Serverda (Render / Railway / Heroku) ishga tushirish
1. Ushbu repozitoriyni GitHub'ga joylang.
2. Render.com yoki Railway.app'ga ulab, Environment Variables bo'limida `BOT_TOKEN` va `GROUP_CHAT_ID` parametrlarini kiriting.
3. Bot avtomatik 24/7 ishlaydi.
