from aiogram import Router
from filter import ModeFilter
from .handlers.commands import register_commands
from .handlers.callbacks import register_callbacks
from .handlers.messages import register_message_handlers
from .handlers.timer import GameTimer
from spyfall.database import Database
from spyfall.game import GameManager
import spyfall.dictionary as dictionary
import config as config


def get_router(bot):
    router = Router()
    router.message.filter(ModeFilter("spy"))

    db = Database()
    game_manager = GameManager(db)
    timer = GameTimer(bot, db)
    dict_instance = dictionary.Dictionary(config.SPYFALL_DATABASE_PATH, config.SPYFALL_DICTIONARY_PATH)

    async def on_startup():
        await db.init_db()
        await dict_instance.init_dictionary()

    router.startup.register(on_startup)

    register_commands(router, bot, db, game_manager, dict_instance, timer)
    register_callbacks(router, bot, db, game_manager)
    register_message_handlers(router, bot, db)

    return router