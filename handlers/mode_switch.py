from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from chat_modes import set_chat_mode, DEFAULT_MODE, get_chat_mode

router = Router()


def _get_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(
            text=("✅ " if current_mode == DEFAULT_MODE else "") + "💬 Standard",
            callback_data=f"mode_{DEFAULT_MODE}",
        ),
        InlineKeyboardButton(
            text=("✅ " if current_mode == "spy" else "") + "🎮 Spyfall",
            callback_data="mode_spy",
        ),
        InlineKeyboardButton(
            text=("✅ " if current_mode == "words" else "") + "📚 Word Chain",
            callback_data="mode_words",
        ),
        InlineKeyboardButton(
            text=("✅ " if current_mode == "speedy_poll" else "") + "❓ Speedy Translate",
            callback_data="mode_speedy_poll",
        ),
    ]

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [buttons[0]],
            [buttons[1]],
            [buttons[2]],
            [buttons[3]],
        ]
    )


@router.message(Command("mode"))
async def choose_mode(message: types.Message):
    current_mode = get_chat_mode(message.chat.id)
    await message.answer(
        "Choose a mode:",
        reply_markup=_get_mode_keyboard(current_mode),
    )


@router.callback_query(F.data.startswith("mode_"))
async def set_mode(callback: CallbackQuery):
    mode = callback.data.replace("mode_", "")
    set_chat_mode(callback.message.chat.id, mode)

    await callback.message.edit_text(
        "✅ Chat mode updated!",
        reply_markup=_get_mode_keyboard(mode),
    )
    await callback.answer("Mode changed!")
