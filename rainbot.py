import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import requests
import schedule
import time
import json
import threading
import os
import random
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

# --- /stop ---

@bot.message_handler(commands=["stop"])
def stop(msg):
    users = load_users()
    chat_id = str(msg.chat.id)
    if chat_id in users:
        del users[chat_id]
        save_users(users)
    bot.send_message(msg.chat.id, "Бот выключен. Напишите /start чтобы запустить снова.")

# --- Проверка погоды ---

RAIN_CODES = list(range(51, 68)) + list(range(80, 83)) + list(range(95, 100))

def check_rain_now(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation,weathercode&timezone=auto"
    response = requests.get(url).json()
    current = response.get("current", {})
    precipitation = current.get("precipitation", 0)
    weathercode = current.get("weathercode", 0)
    return precipitation > 0 or weathercode in RAIN_CODES

def check_rain_soon(lat, lon):
    # Прогноз на ближайшие 2 часа — смотрим следующие 2 слота по 30 минут
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&minutely_15=precipitation,weathercode&timezone=auto&forecast_minutely_15=8"
    response = requests.get(url).json()
    minutely = response.get("minutely_15", {})
    precipitations = minutely.get("precipitation", [])
    weathercodes = minutely.get("weathercode", [])
    # Смотрим слоты с 4 по 8 — это примерно 30-60 минут вперёд
    for i in range(4, min(8, len(precipitations))):
        if precipitations[i] > 0 or weathercodes[i] in RAIN_CODES:
            return True
    return False

# --- Сохранение локации ---

@bot.message_handler(content_types=["location"])
def save_location(msg):
    lat = msg.location.latitude
    lon = msg.location.longitude

    raining_now = check_rain_now(lat, lon)

    users = load_users()
    chat_id = str(msg.chat.id)
    users[chat_id] = {
        "lat": lat,
        "lon": lon,
        "raining": raining_now,
        "warned": False
    }
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

# --- Тексты уведомлений ---

RAIN_SOON_MESSAGES = [
    "🌂 Через полчаса ожидается дождь — самое время достать зонтик!",
    "⛅ Дождь на подходе! Успейте подготовиться.",
    "🌧 Скоро польёт — зонтик лучше взять заранее.",
    "💧 Дождевые тучи уже близко. Зонтик наготове?",
    "⛈ Через полчаса дождь. Не говорите что не предупреждали!",
    "🌦 Дождь скоро будет — хорошее время достать зонтик.",
    "☁️ Тучи сгущаются, дождь совсем рядом!",
    "🌂 Успейте добраться до укрытия — дождь уже в пути!",
    "💦 До дождя осталось совсем немного. Зонтик с собой?",
    "🌧 Дождь приближается к вашему району!",
    "⛅ Небо хмурится — скоро прольёт. Будьте готовы!",
    "🌩 Гроза на подходе! Лучше остаться под крышей.",
    "💧 Дождик уже спешит к вам — встречайте с зонтиком!",
    "☔ Скоро дождь! Лучше выйти пораньше или прихватить зонт.",
    "🌦 Осадки ожидаются в ближайшие полчаса!",
    "⛈ Тучи уже над головой — дождь вот-вот начнётся.",
    "🌧 Дождливая погода уже близко. Одевайтесь соответственно!",
    "💦 Через полчаса мокро — зонтик ваш лучший друг сегодня.",
    "☁️ Дождь приближается! Самое время проверить зонтик.",
    "🌂 Не забудьте зонтик — дождь будет совсем скоро!",
]

RAIN_NOW_MESSAGES = [
    "☔ Дождь уже начался! Надеюсь, зонтик под рукой.",
    "🌧 Ой, дождь уже идёт! Поскорее под крышу!",
    "💧 Капли уже падают — бегите за зонтиком!",
    "🌩 Дождь застал врасплох? Ищите укрытие!",
    "⛈ Дождь уже здесь — и он не шутит!",
    "💦 Мокро на улице! Зонтик бы не помешал.",
    "🌧 Дождь пришёл без предупреждения. Берегите себя!",
    "☔ Льёт! Надеюсь, вы уже в тепле.",
    "🌦 Дождь начался — куртку в руки и вперёд!",
    "💧 Небо открылось! Срочно доставайте зонтик.",
    "⛅ Дождь уже идёт в вашем районе. Не промокните!",
    "🌩 Началось! Дождь уже поливает вовсю.",
    "💦 Дождь пришёл — и выглядит серьёзно. Зонтик наготове?",
    "🌧 Мокрая погода уже здесь. Одевайтесь теплее!",
    "☔ Дождь идёт прямо сейчас — берегите причёску!",
    "🌂 Льёт как из ведра! Лучше остаться дома.",
    "💧 Дождь уже барабанит по крышам. Зонтик с собой?",
    "⛈ Внимание — дождь уже начался! Будьте осторожны.",
    "🌦 Дождь застал вас на улице? Ищите навес!",
    "🌧 Всё, началось! Дождь уже идёт в вашем районе.",
]

# --- Основная проверка ---

def check_rain():
    users = load_users()
    changed = False

    for chat_id, data in users.items():
        try:
            lat = data.get("lat")
            lon = data.get("lon")
            if not lat or not lon:
                continue

            raining = check_rain_now(lat, lon)
            was_raining = data.get("raining", False)
            was_warned = data.get("warned", False)

            if raining and not was_raining and not was_warned:
                # Дождь пришёл внезапно без предупреждения
                bot.send_message(int(chat_id), random.choice(RAIN_NOW_MESSAGES))
                users[chat_id]["raining"] = True
                users[chat_id]["warned"] = True
                changed = True

            elif raining and not was_raining and was_warned:
                # Дождь начался — но мы уже предупреждали, молчим
                users[chat_id]["raining"] = True
                changed = True

            elif not raining and was_raining:
                # Дождь закончился
                users[chat_id]["raining"] = False
                users[chat_id]["warned"] = False
                changed = True

            elif not raining and not was_raining and not was_warned:
                # Дождя нет — проверяем прогноз на ближайшие 30-60 минут
                rain_soon = check_rain_soon(lat, lon)
                if rain_soon:
                    bot.send_message(int(chat_id), random.choice(RAIN_SOON_MESSAGES))
                    users[chat_id]["warned"] = True
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