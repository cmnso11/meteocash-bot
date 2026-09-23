import os
import re
import asyncio
import threading
import requests
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8912083970:AAFwFsqJMIPYEsK64dVPIPe_xZgnMyGRYJk"

bot = Bot(token=TOKEN)
dp = Dispatcher()

user_cities = {}

WEATHER_CODES = {
    0: "☀️ Ясно", 1: "🌤 Преимущественно ясно", 2: "⛅️ Переменная облачность", 3: "☁️ Пасмурно",
    45: "🌫 Туман", 48: "🌫 Осаждающийся туман",
    51: "🌧 Легкий моросящий дождь", 53: "🌧 Моросящий дождь", 55: "🌧 Сильный моросящий дождь",
    61: "🌧 Небольшой дождь", 63: "🌧 Умеренный дождь", 65: "🌧 Сильный дождь",
    71: "🌨 Небольшой снег", 73: "🌨 Снег", 75: "❄️ Сильный снегопад",
    80: "🌧 Ливень", 81: "🌧 Сильный ливень", 82: "🌧 Очень сильный ливень",
}

def get_main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🌤 Погода сейчас"), KeyboardButton(text="📅 Погода на завтра")],
            [KeyboardButton(text="💵 Курсы валют")]
        ],
        resize_keyboard=True
    )

def get_coordinates(city_name):
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=ru&format=json"
    try:
        res = requests.get(url, timeout=5).json()
        if "results" in res and len(res["results"]) > 0:
            city_data = res["results"][0]
            return city_data["latitude"], city_data["longitude"], city_data.get("name", city_name), city_data.get("country", "")
    except Exception as e:
        print(f"Ошибка геокодирования: {e}")
    return None, None, None, None

def get_weather_data(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=temperature_2m_max,temperature_2m_min,weathercode&timezone=auto"
    try:
        return requests.get(url, timeout=5).json()
    except Exception as e:
        print(f"Ошибка погоды: {e}")
        return None

def get_exchange_rates():
    url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        data = requests.get(url, timeout=5).json()
        rates = data.get("rates", {})
        usd_tjs = rates.get("TJS", 0)
        usd_rub = rates.get("RUB", 0)
        rub_tjs = usd_tjs / usd_rub if usd_rub else 0
        return {"USD_TJS": usd_tjs, "USD_RUB": usd_rub, "RUB_TJS": rub_tjs}
    except Exception as e:
        print(f"Ошибка валют: {e}")
        return None

# --- МГНОВЕННЫЙ ВЕБ-СЕРВЕР В ПОТОКЕ ---
def run_web_server():
    app = web.Application()
    app.router.add_get("/", lambda req: web.Response(text="MeteoCash Bot is active!"))
    port = int(os.environ.get("PORT", 8080))
    web.run_app(app, host="0.0.0.0", port=port, print=None)

# Запускаем веб-сервер СРАЗУ, до старта бота, чтобы Render поймал открытый порт
threading.Thread(target=run_web_server, daemon=True).start()

@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! Я бот **MeteoCash** ⚡️\n\n"
        "Пиши названия городов, проверяй погоду или конвертируй деньги (например: `1000 руб` или `100 сомони`)!",
        reply_markup=get_main_keyboard()
    )

@dp.message(F.text == "💵 Курсы валют")
async def send_currency(message: types.Message):
    rates = get_exchange_rates()
    if not rates:
        await message.answer("⚠️ Не удалось получить данные о валютах.")
        return
    text = (
        "📊 **Текущие курсы валют:**\n\n"
        f"🇺🇸 1 USD = **{rates['USD_TJS']:.2f} TJS** (сомони)\n"
        f"🇺🇸 1 USD = **{rates['USD_RUB']:.2f} RUB** (рубли)\n"
        f"🇷🇺 1000 RUB = **{rates['RUB_TJS'] * 1000:.2f} TJS** (сомони)"
    )
    await message.answer(text)

@dp.message(F.text.in_(["🌤 Погода сейчас", "📅 Погода на завтра"]))
async def send_weather(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_cities:
        await message.answer("Сначала напиши название своего города!")
        return

    city_info = user_cities[user_id]
    lat, lon, city_name, country = city_info["lat"], city_info["lon"], city_info["name"], city_info["country"]
    
    weather = get_weather_data(lat, lon)
    if not weather:
        await message.answer("⚠️ Не удалось получить текущую погоду.")
        return

    if message.text == "🌤 Погода сейчас":
        current = weather.get("current_weather", {})
        temp = current.get("temperature", "N/A")
        code = current.get("weathercode", 0)
        desc = WEATHER_CODES.get(code, "Неизвестно")
        text = f"📍 **{city_name}, {country}**\n\n{desc}\n🌡 Температура: **{temp}°C**"
    else:
        daily = weather.get("daily", {})
        if "temperature_2m_max" in daily and len(daily["temperature_2m_max"]) > 1:
            t_max = daily["temperature_2m_max"][1]
            t_min = daily["temperature_2m_min"][1]
            code = daily["weathercode"][1]
            desc = WEATHER_CODES.get(code, "Неизвестно")
            text = f"📍 **{city_name}, {country}** (Завтра)\n\n{desc}\n🌡 Мин: **{t_min}°C** | Макс: **{t_max}°C**"
        else:
            text = "⚠️ Не удалось получить прогноз на завтра."

    await message.answer(text)

@dp.message()
async def handle_text(message: types.Message):
    text = message.text.strip()
    
    match = re.search(r"(\d+)\s*(руб|сомони|доллар|\$|rub|tjs|usd)", text.lower())
    if match:
        amount = float(match.group(1))
        curr = match.group(2)
        rates = get_exchange_rates()
        if rates:
            if curr in ["руб", "rub"]:
                res = amount * rates["RUB_TJS"]
                await message.answer(f"💱 **{amount:.0f} RUB** = **{res:.2f} TJS** (сомони)")
            elif curr in ["сомони", "tjs"]:
                res = amount / rates["RUB_TJS"]
                await message.answer(f"💱 **{amount:.0f} TJS** = **{res:.2f} RUB** (рублей)")
            elif curr in ["доллар", "$", "usd"]:
                res_tjs = amount * rates["USD_TJS"]
                res_rub = amount * rates["USD_RUB"]
                await message.answer(f"💱 **{amount:.0f} USD** = **{res_tjs:.2f} TJS** | **{res_rub:.2f} RUB**")
            return

    lat, lon, city_name, country = get_coordinates(text)
    if lat and lon:
        user_cities[message.from_user.id] = {
            "lat": lat, "lon": lon, "name": city_name, "country": country
        }
        await message.answer(
            f"✅ Город сохранён: **{city_name}, {country}**!\n\n"
            "Теперь нажимай кнопки погоды ниже:",
            reply_markup=get_main_keyboard()
        )
    else:
        await message.answer("Я не нашел такой город или команду. Попробуй еще раз!")

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    print("Бот MeteoCash запущен и ждет сообщений!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
