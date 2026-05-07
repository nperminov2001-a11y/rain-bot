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
from zoneinfo import ZoneInfo
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

# --- Клавиатуры ---

def location_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(KeyboardButton("📍 Отправить моё текущее местоположение", request_location=True))
    return markup

def time_keyboard():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    row = []
    for hour in range(24):
        row.append(KeyboardButton(f"{hour:02d}:00"))
        if len(row) == 4:
            markup.row(*row)
            row = []
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

# --- /time ---

@bot.message_handler(commands=["time"])
def change_time(msg):
    bot.send_message(
        msg.chat.id,
        "В какое время хотите получать сводку погоды?",
        reply_markup=time_keyboard()
    )
    bot.register_next_step_handler(msg, save_time)

def save_time(msg):
    text = msg.text.strip()
    if not text or not text.endswith(":00") or not text[:-3].isdigit():
        bot.send_message(msg.chat.id, "Пожалуйста, выберите время из кнопок.")
        bot.register_next_step_handler(msg, save_time)
        return
    hour = int(text[:-3])
    users = load_users()
    chat_id = str(msg.chat.id)
    if chat_id in users:
        users[chat_id]["hour"] = hour
        save_users(users)
        bot.send_message(
            msg.chat.id,
            f"✅ Время обновлено! Буду присылать сводку погоды каждый день в {text}.",
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

# --- /prikol ---

@bot.message_handler(commands=["prikol"])
def prikol(msg):
    bot.send_message(
        msg.chat.id,
        "Местная газета послала репортёра на молочную ферму задать пару вопросов хозяину.\n\n"
        "Журналист спрашивает у фермера:\n"
        "— Сколько молока дают коровы?\n"
        "— Какая именно, чёрная или коричневая?\n"
        "— Чёрная.\n"
        "— Несколько литров в день.\n"
        "— А коричневая?\n"
        "— Несколько литров в день.\n\n"
        "Немного смутившись, репортёр продолжает:\n"
        "— А чем вы их кормите?\n"
        "— Какую, чёрную или коричневую?\n"
        "— Коричневую.\n"
        "— Она ест траву.\n"
        "— А вторую?\n"
        "— Она тоже ест траву.\n\n"
        "Разозлившийся репортёр говорит:\n"
        "— Если они обе дают одинаковое количество молока и обе едят одно и то же, почему вы всё время спрашиваете «какая»?\n"
        "— Потому что чёрная корова — моя.\n"
        "— А коричневая?\n"
        "— Тоже моя. 🐄"
    )

# --- Получение геолокации ---

@bot.message_handler(content_types=["location"])
def save_location(msg):
    lat = msg.location.latitude
    lon = msg.location.longitude

    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=weathercode&timezone=auto"
    response = requests.get(url).json()
    timezone = response.get("timezone", "UTC")

    users = load_users()
    chat_id = str(msg.chat.id)
    existing = users.get(chat_id, {})

    users[chat_id] = {
        "lat": lat,
        "lon": lon,
        "timezone": timezone,
        "hour": existing.get("hour")
    }
    save_users(users)

    if existing.get("hour") is not None:
        bot.send_message(
            msg.chat.id,
            "✅ Локация обновлена! Часовой пояс определён автоматически.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        bot.send_message(
            msg.chat.id,
            "✅ Отлично! Теперь выберите время — каждый день в это время буду присылать сводку погоды:",
            reply_markup=time_keyboard()
        )
        bot.register_next_step_handler(msg, save_hour_after_location)

def save_hour_after_location(msg):
    text = msg.text.strip()
    if not text or not text.endswith(":00") or not text[:-3].isdigit():
        bot.send_message(msg.chat.id, "Пожалуйста, выберите время из кнопок.")
        bot.register_next_step_handler(msg, save_hour_after_location)
        return
    hour = int(text[:-3])
    users = load_users()
    chat_id = str(msg.chat.id)
    users[chat_id]["hour"] = hour
    save_users(users)
    bot.send_message(
        msg.chat.id,
        f"✅ Готово! Каждый день в {text} буду присылать вам сводку погоды. Хорошего дня!\n\n"
        f"Чтобы сменить локацию — /location\n"
        f"Чтобы сменить время — /time",
        reply_markup=ReplyKeyboardRemove()
    )

# --- Получение прогноза ---

WIND_LEVELS = [
    (0, 20, "слабый"),
    (20, 40, "средний"),
    (40, float("inf"), "сильный"),
]

WEATHER_CODES = {
    "rain": list(range(51, 68)) + list(range(80, 83)),
    "snow": list(range(71, 78)) + [85, 86],
    "storm": list(range(95, 100)),
}

def get_wind_label(speed):
    for low, high, label in WIND_LEVELS:
        if low <= speed < high:
            return label
    return "сильный"

def get_forecast(lat, lon, timezone):
    url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,precipitation,weathercode,windspeed_10m"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&timezone={timezone}"
        f"&forecast_days=1"
    )
    return requests.get(url).json()

def format_periods(hours, codes, target_codes):
    periods = []
    start = None
    for i, (hour, code) in enumerate(zip(hours, codes)):
        if code in target_codes:
            if start is None:
                start = hour
            end = hour
        else:
            if start is not None:
                periods.append(f"с {start} до {end}")
                start = None
    if start is not None:
        periods.append(f"с {start} до {end}")
    return ", ".join(periods) if periods else None

def build_forecast_message(lat, lon, timezone):
    data = get_forecast(lat, lon, timezone)
    hourly = data.get("hourly", {})
    daily = data.get("daily", {})

    hours = hourly.get("time", [])
    hours_short = [h.split("T")[1][:5] for h in hours]
    weathercodes = hourly.get("weathercode", [])
    windspeeds = hourly.get("windspeed_10m", [])

    temp_max = round(daily.get("temperature_2m_max", [0])[0])
    temp_min = round(daily.get("temperature_2m_min", [0])[0])
    avg_wind = sum(windspeeds) / len(windspeeds) if windspeeds else 0
    wind_label = get_wind_label(avg_wind)

    rain_periods = format_periods(hours_short, weathercodes, WEATHER_CODES["rain"])
    snow_periods = format_periods(hours_short, weathercodes, WEATHER_CODES["snow"])
    storm_periods = format_periods(hours_short, weathercodes, WEATHER_CODES["storm"])

    is_winter = temp_max < 0
    header = "❄️ Доброе утро! Сводка погоды на сегодня:" if is_winter else "🌤 Доброе утро! Сводка погоды на сегодня:"

    msg = f"{header}\n"
    msg += f"🌡 Температура: {temp_min:+}°..{temp_max:+}°\n"
    msg += f"💨 Ветер: {wind_label}\n"

    if not rain_periods and not snow_periods and not storm_periods:
        msg += "✅ Осадков не ожидается"
    else:
        if rain_periods:
            msg += f"🌧 Дождь: {rain_periods}\n"
        if snow_periods:
            msg += f"🌨 Снегопад: {snow_periods}\n"
        if storm_periods:
            msg += f"⛈ Гроза: {storm_periods}\n"

    return msg.strip()

# --- Отправка сводки ---

def send_daily_forecasts():
    users = load_users()
    for chat_id, data in users.items():
        lat = data.get("lat")
        lon = data.get("lon")
        hour = data.get("hour")
        timezone = data.get("timezone", "UTC")
        if not lat or not lon or hour is None:
            continue
        try:
            tz = ZoneInfo(timezone)
            now = datetime.now(tz)
            if now.hour == hour:
                msg = build_forecast_message(lat, lon, timezone)
                bot.send_message(int(chat_id), msg)
        except Exception as e:
            print(f"Ошибка для {chat_id}: {e}")

schedule.every().hour.do(send_daily_forecasts)

threading.Thread(target=bot.polling, daemon=True).start()

while True:
    schedule.run_pending()
    time.sleep(60)