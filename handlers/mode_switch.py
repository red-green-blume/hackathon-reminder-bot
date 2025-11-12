from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

router = Router()

@router.message(Command("mode"))
async def choose_mode(message: types.Message):
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🎮 Шпион")],
            [types.KeyboardButton(text="📚 Слова")],
            [types.KeyboardButton(text="❓ Кто быстрее")],
        ],
        resize_keyboard=True
    )
    await message.answer("Выбери режим:", reply_markup=keyboard)


@router.message(lambda m: m.text in ["🎮 Шпион", "📚 Слова", "❓ Кто быстрее"])
async def set_mode(message: types.Message, state: FSMContext):
    mode = None
    if "Шпион" in message.text:
        mode = "spy"
    elif "Слова" in message.text:
        mode = "words"
    elif "Кто быстрее" in message.text:
        mode = "speedy_poll"
    await state.update_data(mode=mode)
    await message.answer(f"✅ Режим переключен на {message.text}")
