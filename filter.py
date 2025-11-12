from aiogram.filters import BaseFilter
from aiogram.types import Message
from chat_modes import get_chat_mode

class ModeFilter(BaseFilter):
    def __init__(self, mode_name: str):
        self.mode_name = mode_name

    async def __call__(self, message: Message) -> bool:
        return get_chat_mode(message.chat.id) == self.mode_name
