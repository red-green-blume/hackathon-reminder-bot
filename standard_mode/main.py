from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from chat_modes import DEFAULT_MODE, set_chat_mode
from filter import ModeFilter


def get_router() -> Router:
    router = Router()
    router.message.filter(ModeFilter(DEFAULT_MODE))

    @router.message(Command("start"))
    async def cmd_start(message: Message):
        set_chat_mode(message.chat.id, DEFAULT_MODE)
        await message.answer(
            "👋 Hi! This is the standard mode.\n"
            "Use the /mode command to pick another game mode.",
        )

    return router
