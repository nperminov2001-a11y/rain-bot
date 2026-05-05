import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import requests
import schedule
import time
import json
import threading
import os
import random
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

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

# --- Клавиатура геолокации ---

def location_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📍 Отправить моё текущее местоположение", request_location=True))
    return markup

# --- /start ---

@bot.message_handler(commands=["start"])
def start(msg):
    bot.send_message(
        msg.chat.id,
        "Привет! Чтобы я мог следить за погодой в нужном районе, отправьте точку на карте.\n\n"
        "Как это сделать:\n"
        "1. Нажмите на скрепку 📎 внизу экрана\n"
        "2. Выберите «Геолокация»\n"
        "3. Нажмите «Выбрать место на карте»\n"
        "4. Перетащите точку куда нужно\n"
        "5. Нажмите «Отправить»\n\n"
        "Или нажмите кнопку внизу",
        reply_markup=location_keyboard()
    )

# --- /location ---

@bot.message_handler(commands=["location"])
def change_location(msg):
    bot.send_message(
        msg.chat.id,
        "Отправьте новую точку на карте:\n\n"
        "1. Нажмите на скрепку 📎 внизу экрана\n"
        "2. Выберите «Геолокация»\n"
        "3. Нажмите «Выбрать место на карте»\n"
        "4. Перетащите точку куда нужно\n"
        "5. Нажмите «Отправить»\n\n"
        "Или нажмите кнопку внизу",
        reply_markup=location_keyboard()
    )

# --- Получение геолокации ---

def check_rain_now(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation,weathercode&timezone=auto"
    response = requests.get(url).json()
    current = response.get("current", {})
    precipitation = current.get("precipitation", 0)
    weathercode = current.get("weathercode", 0)
    # Коды дождя в Open-Meteo: 51-67 морось и дождь, 80-82 ливни, 95-99 гроза
    rain_codes = list(range(51, 68)) + list(range(80, 83)) + list(range(95, 100))
    return precipitation > 0 or weathercode in rain_codes

def check_rain_forecast(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation,weathercode&timezone=auto&forecast_hours=3"
    response = requests.get(url).json()
    hourly = response.get("hourly", {})
    precipitations = hourly.get("precipitation", [])
    weathercodes = hourly.get("weathercode", [])
    rain_codes = list(range(51, 68)) + list(range(80, 83)) + list(range(95, 100))
    for i in range(len(precipitations)):
        if precipitations[i] > 0 or weathercodes[i] in rain_codes:
            return True
    return False

@bot.message_handler(content_types=["location"])
def save_location(msg):
    lat = msg.location.latitude
    lon = msg.location.longitude

    users = load_users()
    chat_id = str(msg.chat.id)

    raining_now = check_rain_now(lat, lon)

    users[chat_id] = {"lat": lat, "lon": lon, "raining": raining_now}
    save_users(users)

    if raining_now:
        bot.send_message(
            msg.chat.id,
            "✅ Бот запущен! Буду присылать уведомления о дожде в этом месте. Кстати, дождь как раз сейчас идёт — надеюсь, вы в тепле! 🌧",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        bot.send_message(
            msg.chat.id,
            "✅ Бот запущен! Буду следить за погодой в этом месте и пришлю уведомление если будет дождь.\n\nЧтобы сменить локацию — напишите /location",
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
    bot.send_message(msg.chat.id, "Бот выключен. Напишите /start чтобы запустить снова.")

# --- Уведомления ---

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
        try:
            lat = data.get("lat")
            lon = data.get("lon")

            if not lat or not lon:
                continue

            rain = check_rain_forecast(lat, lon)
            was_raining = data.get("raining", False)

            if rain and not was_raining:
                message = random.choice(RAIN_MESSAGES)
                bot.send_message(int(chat_id), message)
                users[chat_id]["raining"] = True
                changed = True

            elif not rain and was_raining:
                users[chat_id]["raining"] = False
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