import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from config.settings import settings
from bot.handlers import router, cmd_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)


async def on_startup(bot: Bot) -> None:
    """
    Execute actions on bot startup.
    """
    # Ensure temp directories exist
    settings.VOICE_TEMP_PATH.mkdir(parents=True, exist_ok=True)
    
    # Log bot info
    bot_info = await bot.get_me()
    logging.info(f"Starting bot: @{bot_info.username}")


async def on_shutdown(bot: Bot) -> None:
    """
    Execute actions on bot shutdown.
    """
    logging.warning("Bot is shutting down...")


async def main() -> None:
    """
    Main function to start the bot.
    """
    # Initialize bot and dispatcher
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    
    # Setup routers
    dp.include_router(cmd_router)
    dp.include_router(router)
    
    # Set up startup and shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Start polling
    try:
        logging.info("Starting bot polling...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logging.warning("Bot polling stopped")
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.warning("Bot stopped!")
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        sys.exit(1)
