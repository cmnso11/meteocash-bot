import asyncio
import re
import requests
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = "8912083970:AAFwFsqJMIPYEsK64dVPIPe_xZgnMyGRYJk"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище последнего выбранного города
user_cities = {}

# Коды погоды WMO
WEATHER_CODES = {
    0: "☀️ Ясно", 1: "🌤 Преимущественно ясно", 2: "⛅️ Переменная облачность", 3: "☁️ Пасмурно",
    45: "🌫 Туман", 48: "🌫 Осаждающийся туман",
    51: "🌦 Легкий моросящий дождь", 53: "🌧 Моросящий дождь", 55: "🌧 Сильный моросящий дождь",
    61: "🌧 Небольшой дождь", 63: "🌧 Умеренный дождь", 65: "🌧 Сильный дождь",
    71: "🌩 Небольшой снег", 73: "❄️ Снег", 75: "❄️ Сильный снегопад",
    80: "🌦 Ливень", 81: "🌧 Сильный ливень", 82: "⛈ Очень сильный ливень",
    95: "⛈ Гроза", 96: "⛈ Гроза с небольшим градом", 99: "⛈ Гроза с сильным градом"
}

# Главное меню
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🌤 Погода сейчас"), KeyboardButton(text="📅 Почасовая на сегодня")],
        [KeyboardButton(text="🔮 Погода на завтра"), KeyboardButton(text="💱 Курс валют")],
        [KeyboardButton(text="ℹ️ О боте")]
    ],
    resize_keyboard=True
)

# Поиск координат города
def get_coordinates(city_name: str):
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=ru&format=json"
        geo_res = requests.get(geo_url).json()
        if not geo_res.get("results"):
            return None
        city_data = geo_res["results"][0]
        return {
            "lat": city_data["latitude"],
            "lon": city_data["longitude"],
            "name": f"{city_data['name']}, {city_data.get('country', '')}"
        }
    except Exception:
        return None

# Погода сейчас
def get_current_weather(city_info: dict) -> str:
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={city_info['lat']}&longitude={city_info['lon']}&current_weather=true"
        res = requests.get(url).json()["current_weather"]
        condition = WEATHER_CODES.get(res["weathercode"], "🌈 Неизвестно")
        
        return (
            f"🌍 **Погода в {city_info['name']} (Сейчас):**\n\n"
            f"Состояние: **{condition}**\n"
            f"🌡 Температура: **{res['temperature']}°C**\n"
            f"💨 Ветер: **{res['windspeed']} км/ч**"
        )
    except Exception:
        return "⚠️ Не удалось получить текущую погоду."

# Почасовая погода
def get_hourly_weather(city_info: dict) -> str:
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={city_info['lat']}&longitude={city_info['lon']}&hourly=temperature_2m,weathercode&forecast_days=1&timezone=auto"
        res = requests.get(url).json()["hourly"]
        
        times = res["time"]
        temps = res["temperature_2m"]
        codes = res["weathercode"]

        current_hour = datetime.now().hour
        lines = [f"📅 **Почасовой прогноз на сегодня ({city_info['name']}):**\n"]

        for i in range(len(times)):
            dt = datetime.fromisoformat(times[i])
            if dt.hour >= current_hour and dt.hour % 2 == 0:
                time_str = dt.strftime("%H:00")
                condition = WEATHER_CODES.get(codes[i], "🌈")
                lines.append(f"⏰ **{time_str}** — {condition}, **{temps[i]}°C**")

        return "\n".join(lines)
    except Exception:
        return "⚠️ Не удалось получить почасовой прогноз."

# Погода на завтра
def get_tomorrow_weather(city_info: dict) -> str:
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={city_info['lat']}&longitude={city_info['lon']}&daily=weathercode,temperature_2m_max,temperature_2m_min&forecast_days=2&timezone=auto"
        res = requests.get(url).json()["daily"]
        
        code = res["weathercode"][1]
        temp_max = res["temperature_2m_max"][1]
        temp_min = res["temperature_2m_min"][1]
        condition = WEATHER_CODES.get(code, "🌈 Неизвестно")

        tomorrow_date = (datetime.now() + timedelta(days=1)).strftime("%d.%m.%Y")

        return (
            f"🔮 **Прогноз на завтра ({tomorrow_date}) для {city_info['name']}:**\n\n"
            f"Состояние: **{condition}**\n"
            f"🌡 Днём: **до {temp_max}°C**\n"
            f"🌙 Ночью: **до {temp_min}°C**"
        )
    except Exception:
        return "⚠️ Не удалось получить прогноз на завтра."

# Курс валют
def get_currency_rates() -> str:
    try:
        url = "https://open.er-api.com/v6/latest/USD"
        res = requests.get(url).json()
        rates = res.get("rates", {})
        
        rub = round(rates.get("RUB", 0), 2)
        tjs = round(rates.get("TJS", 0), 2)
        eur = round(rates.get("EUR", 0), 2)
        kzt = round(rates.get("KZT", 0), 2)
        try_rate = round(rates.get("TRY", 0), 2)

        return (
            "💱 **Курсы валют к 1 USD:**\n\n"
            f"🇷🇺 RUB: **{rub} руб.**\n"
            f"🇹🇯 TJS: **{tjs} сомони**\n"
            f"🇪🇺 EUR: **{eur} €**\n"
            f"🇰🇿 KZT: **{kzt} ₸**\n"
            f"🇹🇷 TRY: **{try_rate} ₺**"
        )
    except Exception:
        return "⚠️ Не удалось загрузить курсы валют."

# Хэндлеры
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}! Я бот **MeteoCash** ⚡\n\n"
        "Пиши названия городов, проверяй погоду или конвертируй деньги (например: `1000 руб` или `100 сомони`)!",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )

@dp.message(F.text == "ℹ️ О боте")
async def about_bot(message: types.Message):
    await message.answer("Бот **MeteoCash** — погода и мгновенный конвертер валют 🌍", parse_mode="Markdown")

@dp.message(F.text == "💱 Курс валют")
async def currency_btn(message: types.Message):
    await message.answer(get_currency_rates(), parse_mode="Markdown")

@dp.message(F.text == "🌤 Погода сейчас")
async def weather_now_btn(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_cities:
        await message.answer("Сначала напиши название своего города!")
        return
    await message.answer(get_current_weather(user_cities[user_id]), parse_mode="Markdown")

@dp.message(F.text == "📅 Почасовая на сегодня")
async def weather_hourly_btn(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_cities:
        await message.answer("Сначала напиши название своего города!")
        return
    await message.answer(get_hourly_weather(user_cities[user_id]), parse_mode="Markdown")

@dp.message(F.text == "🔮 Погода на завтра")
async def weather_tomorrow_btn(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_cities:
        await message.answer("Сначала напиши название своего города!")
        return
    await message.answer(get_tomorrow_weather(user_cities[user_id]), parse_mode="Markdown")

# Универсальная обработка сообщений (Конвертер + Города)
@dp.message()
async def process_user_text(message: types.Message):
    text = message.text.lower().strip()
    
    # 1. Проверяем, ввёл ли пользователь сумму для конвертации (например: "1000руб", "500 руб", "100 сомони")
    match = re.match(r"^(\d+)\s*(руб|рублей|rub|сомони|tjs|usd|\$)$", text)
    if match:
        amount = float(match.group(1))
        currency = match.group(2)
        
        try:
            res = requests.get("https://open.er-api.com/v6/latest/USD").json()["rates"]
            rub_rate = res.get("RUB", 1)
            tjs_rate = res.get("TJS", 1)
            
            if currency in ["руб", "рублей", "rub"]:
                # Из рублей в сомони
                result_tjs = round((amount / rub_rate) * tjs_rate, 2)
                await message.answer(f"💱 **{int(amount)} RUB** = **{result_tjs} TJS** (сомони)", parse_mode="Markdown")
                return
            elif currency in ["сомони", "tjs"]:
                # Из сомони в рубли
                result_rub = round((amount / tjs_rate) * rub_rate, 2)
                await message.answer(f"💱 **{int(amount)} TJS** = **{result_rub} RUB** (рублей)", parse_mode="Markdown")
                return
        except Exception:
            await message.answer("⚠️ Ошибка при расчете курса валют.")
            return

    # 2. Если это не сумма — ищем город
    city_info = get_coordinates(message.text)
    if city_info:
        user_cities[message.from_user.id] = city_info
        text_resp = (
            f"✅ Город сохранён: **{city_info['name']}**!\n\n"
            "Теперь нажимай кнопки погоды ниже:"
        )
        await message.answer(text_resp, reply_markup=main_keyboard, parse_mode="Markdown")
    else:
        await message.answer("❌ Название города не найдено. Или напиши сумму, например: `1000 руб` или `500 сомони`", parse_mode="Markdown")

async def main():
    print("Бот MeteoCash запущен и ждет сообщений!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен")