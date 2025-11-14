from aiogram import Router

import config

from filter import ModeFilter
from spyfall import dictionary
from spyfall.database import Database
from spyfall.game import GameManager

from .handlers.callbacks import register_callbacks
from .handlers.commands import register_commands
from .handlers.messages import register_message_handlers
from .handlers.timer import GameTimer


def get_router(bot):
    router = Router()
    router.message.filter(ModeFilter("spy"))

    db = Database()
    game_manager = GameManager(db)
    timer = GameTimer(bot, db)
    dict_instance = dictionary.Dictionary(
        config.SPYFALL_DATABASE_PATH, config.SPYFALL_DICTIONARY_PATH
    )

    async def on_startup():
        await db.init_db()
        await dict_instance.init_dictionary()

    router.startup.register(on_startup)

    register_commands(router, bot, db, game_manager, dict_instance, timer)
    register_callbacks(router, bot, db, game_manager, timer)
    register_message_handlers(router, bot, db)

    return router
