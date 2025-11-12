from aiogram.filters import BaseFilter
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

class ModeFilter(BaseFilter):
    def __init__(self, mode_name: str):
        self.mode_name = mode_name

    async def __call__(self, message: Message, state: FSMContext) -> bool:
        data = await state.get_data()
        return data.get("mode") == self.mode_name
