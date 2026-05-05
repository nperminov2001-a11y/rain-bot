import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import requests
import schedule
import time
import json
import threading
import os
import random
from datetime import datetime, timedelta

BOT_TOKEN = "8715940830:AAGUiG4h1_lyXsV30GFahjIqrxgOVN73mnA"
WEATHER_KEY = "02c6e80f0555fed3b5af48438ceedaa2"

bot = telebot.TeleBot(BOT_TOKEN)

# --- База пользователей ---

def load_users():
    if os.path.exists("users.json"):
        with open("users.json") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open("users.json", "w") as f:
        json.dump(users, f)

# --- Клавиатура выбора локации ---

def location_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("🏙 Выбрать город"))
    markup.add(KeyboardButton("📍 Точка на карте"))
    return markup

# --- /start ---

@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(msg.chat.id, "Привет! Как определить ваше местоположение?", reply_markup=location_keyboard())

# --- /location ---

@bot.message_handler(commands=["location"])
def change_location(msg):
    bot.send_message(msg.chat.id, "Выберите новый способ определения местоположения:", reply_markup=location_keyboard())

# --- Пользователь выбрал город ---

@bot.message_handler(func=lambda msg: msg.text == "🏙 Выбрать город")
def ask_city(msg):
    bot.send_message(msg.chat.id, "Напишите название вашего города:", reply_markup=ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, save_city)

def save_city(msg):
    city = msg.text.strip()
    
    # Проверяем существует ли город
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_KEY}"
    response = requests.get(url).json()
    
    if response.get("cod") == "404":
        bot.send_message(msg.chat.id, f"❌ Город «{city}» не найден. Попробуйте ещё раз — напишите название на английском или проверьте написание.")
        bot.register_next_step_handler(msg, save_city)  # даём попробовать снова
        return
    
    users = load_users()
    chat_id = str(msg.chat.id)
    users[chat_id] = {"type": "city", "city": city}
    save_users(users)
    bot.send_message(
        msg.chat.id,
        f"✅ Бот запущен! Буду следить за погодой в городе {city} и пришлю уведомление если будет дождь.\n\nЧтобы сменить локацию — напишите /location"
    )
# --- Пользователь выбрал точку на карте ---

@bot.message_handler(func=lambda msg: msg.text == "📍 Точка на карте")
def ask_location(msg):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📍 Отправить геолокацию", request_location=True))
    bot.send_message(
        msg.chat.id,
        "Как выбрать точку на карте:\n\n"
        "1. Нажмите на скрепку 📎 внизу экрана\n"
        "2. Выберите «Геолокация»\n"
        "3. Нажмите «Выбрать место на карте»\n"
        "4. Перетащите точку куда нужно\n"
        "5. Нажмите «Отправить»\n\n"
        "Или нажмите кнопку ниже чтобы отправить текущее местоположение:",
        reply_markup=markup
    )

@bot.message_handler(content_types=["location"])
def save_location(msg):
    lat = msg.location.latitude
    lon = msg.location.longitude
    users = load_users()
    chat_id = str(msg.chat.id)
    users[chat_id] = {"type": "coords", "lat": lat, "lon": lon}
    save_users(users)
    bot.send_message(
        msg.chat.id,
        "✅ Отлично! Буду следить за погодой в этом месте и пришлю уведомление если будет дождь.\n\nЧтобы сменить локацию — напишите /location",
        reply_markup=ReplyKeyboardRemove()
    )

# --- /stop ---

@bot.message_handler(commands=["stop"])
def stop(msg):
    users = load_users()
    chat_id = str(msg.chat.id)
    if chat_id in users:
        del users[chat_id]
        save_users(users)
    bot.send_message(msg.chat.id, "❌ Бот выключен. Напишите /start чтобы запустить снова.)

# --- Проверка погоды ---

def check_rain_by_city(city):
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&appid={WEATHER_KEY}&cnt=4&units=metric&lang=ru"
    response = requests.get(url).json()
    for period in response.get("list", []):
        if period["weather"][0]["main"] in ("Rain", "Drizzle", "Thunderstorm"):
            return True
    return False

def check_rain_by_coords(lat, lon):
    url = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_KEY}&cnt=4&units=metric&lang=ru"
    response = requests.get(url).json()
    for period in response.get("list", []):
        if period["weather"][0]["main"] in ("Rain", "Drizzle", "Thunderstorm"):
            return True
    return False
RAIN_MESSAGES = [
    "☔ Скоро дождь! Не забудьте зонтик.",
    "🌧 Дождь на подходе. Зонтик лучше взять с собой!",
    "💧 Кажется, небо собирается поплакать. Зонтик в руки!",
    "🌂 Захватите зонтик — дождь уже близко.",
    "⛈ Тучи сгущаются! Самое время достать зонтик.",
    "🌦 Без зонтика сегодня никуда — дождь скоро будет.",
    "💦 Дождик торопится к вам. Будьте готовы!",
    "🌩 Небо хмурится, надеюсь, что вы нет. Зонтик не забудьте!",
    "Ожидается дождь. Зонтик пригодится!",
    "🌧 Дождь будет скоро. Хорошего дня и сухих ног!",
    "💧 Осадки ожидаются в вашем районе. Будьте готовы!",
    "Небо плаки плаки, скоро будет мокро",
    "🌂 Зонтик сегодня ваш лучший друг — дождь близко.",
    "⛅ Небо затягивается тучами. Дождь уже в пути!",
    "🌧 Скоро польёт! Не промокните.",
    "💦 Дождливая погода не за горами. Одевайтесь теплее!",
    "🌩 Гроза приближается! Лучше остаться под крышей.",
    "☔ Дождь стучится в ваш район. Зонтик наготове!",
    "🌦 Капли уже в пути — зонтик с собой!",
    "Дождь ожидает вас, оденьтесь соответствующе",
]
def check_rain():
    users = load_users()
    changed = False

    for chat_id, data in users.items():
        last_notified = data.get("last_notified")
        if last_notified:
            last_time = datetime.fromisoformat(last_notified)
            if datetime.now() - last_time < timedelta(hours=3):
                continue

        try:
            rain = False

            if data.get("type") == "city":
                city = data.get("city", "Москва")
                rain = check_rain_by_city(city)

            elif data.get("type") == "coords":
                lat = data.get("lat")
                lon = data.get("lon")
                rain = check_rain_by_coords(lat, lon)

            if rain:
                message = random.choice(RAIN_MESSAGES)
                bot.send_message(int(chat_id), message)
                users[chat_id]["last_notified"] = datetime.now().isoformat()
                changed = True

        except Exception as e:
            print(f"Ошибка для {chat_id}: {e}")

    if changed:
        save_users(users)

schedule.every(30).minutes.do(check_rain)

threading.Thread(target=bot.polling, daemon=True).start()

while True:
    schedule.run_pending()
    time.sleep(60)