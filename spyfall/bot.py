import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from database import Database
import dictionary
from game import GameManager
from handlers.commands import register_commands
from handlers.callbacks import register_callbacks
from handlers.messages import register_message_handlers
from handlers.timer import GameTimer
import config


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database()
game_manager = GameManager(db)
timer = GameTimer(bot, db)
dictionary = dictionary.Dictionary(config.DATABASE_PATH, config.DICTIONARY_PATH)


register_commands(dp, bot, db, game_manager, dictionary, timer)
register_callbacks(dp, bot, db, game_manager)
register_message_handlers(dp, bot, db)


async def main():
    await dictionary.init_dictionary()
    logger.info("Dictionary initialized")

    await db.init_db()
    logger.info("Database initialized")

    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
