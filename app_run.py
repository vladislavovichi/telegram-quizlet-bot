import asyncio
from app.factory import create_app
import logging

logging.basicConfig(level=logging.INFO)


async def main():
    app = await create_app()
    bot = app.bot
    dp = app.dp

    print("Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass
        try:
            await app.engine.dispose()
        except Exception:
            pass
        print("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
