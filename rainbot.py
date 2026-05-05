import telebot
import requests
import schedule
import time
import json
import threading
import os

BOT_TOKEN = "8715940830:AAGUiG4h1_lyXsV30GFahjIqrxgOVN73mnA"
WEATHER_KEY = "02c6e80f0555fed3b5af48438ceedaa2"

bot = telebot.TeleBot(BOT_TOKEN)

# --- База пользователей (простой JSON-файл) ---

def load_users():
    if os.path.exists("users.json"):
        with open("users.json") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f)

# --- Команды ---

@bot.message_handler(commands=["start"])
def start(msg):
    users = load_users()
    chat_id = str(msg.chat.id)
    if chat_id not in users:
        users[chat_id] = {"city": "Moscow"}  # город по умолчанию
        save_users(users)
        bot.send_message(msg.chat.id, "✅ Подписка оформлена! Буду предупреждать о дожде.\n\nЧтобы сменить город: /city Санкт-Петербург")
    else:
        bot.send_message(msg.chat.id, "Вы уже подписаны!")

@bot.message_handler(commands=["stop"])
def stop(msg):
    users = load_users()
    chat_id = str(msg.chat.id)
    if chat_id in users:
        del users[chat_id]
        save_users(users)
    bot.send_message(msg.chat.id, "❌ Подписка отменена.")

@bot.message_handler(commands=["city"])
def set_city(msg):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(msg.chat.id, "Укажите город: /city Москва")
        return
    city = parts[1]
    users = load_users()
    chat_id = str(msg.chat.id)
    if chat_id in users:
        users[chat_id]["city"] = city
        save_users(users)
        bot.send_message(msg.chat.id, f"🏙 Город изменён на: {city}")

# --- Проверка погоды ---

def check_rain():
    users = load_users()
    for chat_id, data in users.items():
        city = data.get("city", "Moscow")
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_KEY}&cnt=4&units=metric&lang=ru"
        try:
            response = requests.get(url).json()
            for period in response.get("list", []):
                weather = period["weather"][0]["main"]
                if weather in ("Rain", "Drizzle", "Thunderstorm"):
                    bot.send_message(int(chat_id), f"☔ В городе {city} скоро дождь! Возьмите зонтик 🌂")
                    break
        except Exception as e:
            print(f"Ошибка для {chat_id}: {e}")

schedule.every(30).minutes.do(check_rain)

threading.Thread(target=bot.polling, daemon=True).start()

while True:
    schedule.run_pending()
    time.sleep(60)