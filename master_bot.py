import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
from handlers import mode_switch
import spyfall
import speedy_translate
import words_game

async def main():
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(mode_switch.router)

    dp.include_router(speedy_translate.get_router())
    dp.include_router(words_game.get_router(bot))
    dp.include_router(spyfall.get_router(bot))

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
