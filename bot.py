import asyncio
import datetime
import os
import asyncpg
import pytz

from aiogram import Bot, Dispatcher, types
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")

if not TOKEN:
    raise ValueError("TOKEN not set")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

bot = Bot(token=TOKEN)
dp = Dispatcher()

scheduler = AsyncIOScheduler()
pool = None

# таймзона (меняешь если нужно)
tz = pytz.timezone("Europe/Stockholm")


# --- БД ---
async def init_db():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS reminders (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            weekday INT,
            time TEXT,
            text TEXT
        )
        """)


# --- Добавление ---
@dp.message(commands=["add"])
async def add_reminder(message: types.Message):
    try:
        _, day, time, *text = message.text.split()

        days = {
            "mon": 0, "tue": 1, "wed": 2,
            "thu": 3, "fri": 4, "sat": 5, "sun": 6
        }

        weekday = days[day.lower()]
        text = " ".join(text)

        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO reminders (user_id, weekday, time, text) VALUES ($1, $2, $3, $4)",
                message.from_user.id, weekday, time, text
            )

        await message.answer("✅ Добавлено")

    except:
        await message.answer("Формат: /add mon 18:00 Текст")


# --- Список ---
@dp.message(commands=["list"])
async def list_reminders(message: types.Message):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, weekday, time, text FROM reminders WHERE user_id=$1",
            message.from_user.id
        )

    if not rows:
        await message.answer("Пусто")
        return

    days_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

    text = ""
    for r in rows:
        text += f"{r['id']} | {days_map[r['weekday']]} | {r['time']} | {r['text']}\n"

    await message.answer(text)


# --- Удаление ---
@dp.message(commands=["delete"])
async def delete_reminder(message: types.Message):
    try:
        _, rid = message.text.split()

        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM reminders WHERE id=$1 AND user_id=$2",
                int(rid), message.from_user.id
            )

        await message.answer("🗑 Удалено")

    except:
        await message.answer("Пример: /delete 1")


# --- Проверка ---
async def check_reminders():
    now = datetime.datetime.now(tz)
    weekday = now.weekday()
    current_time = now.strftime("%H:%M")

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT user_id, text FROM reminders WHERE weekday=$1 AND time=$2",
            weekday, current_time
        )

    for row in rows:
        try:
            await bot.send_message(row["user_id"], f"⏰ {row['text']}")
        except:
            pass


# --- MAIN ---
async def main():
    print("Bot started")

    await init_db()

    scheduler.add_job(check_reminders, "interval", minutes=1)
    scheduler.start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
