import asyncio
from app.factory import create_app
import logging

logging.basicConfig(level=logging.INFO)


async def main():
    app = await create_app()
    bot = app.bot
    dp = app.dp
    redis = app.redis_client

    print("Starting polling...")
    try:
        await dp.start_polling(bot)
    finally:
        try:
            await bot.session.close()
        except Exception as e:
            print("Bot close failed: %s", e)
        try:
            await app.engine.dispose()
        except Exception as e:
            print("Engine close failed: %s", e)
        try:
            await redis.aclose()
        except Exception as e:
            print("Redis close failed: %s", e)
        print("Shutdown complete.")


if __name__ == "__main__":
    asyncio.run(main())
