import asyncio
import os

import uvicorn
from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from dotenv import load_dotenv

import database as db
from bot import create_dispatcher
from api import create_api_app

load_dotenv()

BOT_TOKEN = os.environ["TELEGRAM_API_TOKEN"]

DATABASE_URL = (
    f"postgresql://{os.environ['DATABASE_USER']}:{os.environ['DATABASE_PASSWORD']}"
    f"@{os.environ['DATABASE_HOST']}:{os.environ['DATABASE_PORT']}/{os.environ['DATABASE_NAME']}"
)

API_HOST = os.environ.get("API_HOST", "0.0.0.0")
API_PORT = int(os.environ.get("API_PORT", "8000"))
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()}


async def setup_bot_commands(bot: Bot):
    public_commands = [
        BotCommand(command="start", description="Записаться к мастеру"),
        BotCommand(command="mybookings", description="Мои записи"),
    ]
    await bot.set_my_commands(public_commands, scope=BotCommandScopeDefault())

    admin_commands = public_commands + [
        BotCommand(command="admin", description="Админ-панель"),
    ]
    for admin_id in ADMIN_IDS:
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))


async def run_bot(pool):
    bot = Bot(token=BOT_TOKEN)
    dp = create_dispatcher(pool, ADMIN_IDS)
    await bot.delete_webhook(drop_pending_updates=True)
    await setup_bot_commands(bot)
    await dp.start_polling(bot)


async def run_api(pool):
    app = create_api_app(pool)
    config = uvicorn.Config(app, host=API_HOST, port=API_PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    pool = await db.create_pool(DATABASE_URL)
    await db.init_db(pool)

    try:
        await asyncio.gather(
            run_bot(pool),
            run_api(pool),
        )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())