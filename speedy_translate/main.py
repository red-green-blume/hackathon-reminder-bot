import csv
import random

from collections import defaultdict

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from filter import ModeFilter


dictionary = []
current_word = None
current_answers = []
game_active = False
scores = defaultdict(int)
chat_id = None

MODE_NAME = "speedy_poll"


def load_dictionary():
    global dictionary
    with open("speedy_translate/dictionary.csv", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        dictionary = [{"eng": row[0].strip(), "rus": row[1].strip()} for row in reader]


def new_round():
    global current_word, current_answers
    current_word = random.choice(dictionary)
    current_answers = [d["rus"] for d in dictionary if d["eng"] == current_word["eng"]]


def get_router() -> Router:
    router = Router()
    router.message.filter(ModeFilter("speedy_poll"))

    @router.message(Command("start"))
    async def start_game(message: Message):
        global game_active, scores, chat_id
        if game_active:
            await message.reply("The game is already running!")
            return

        load_dictionary()
        game_active = True
        scores = defaultdict(int)
        chat_id = message.chat.id
        new_round()

        await message.answer(
            f"The game has started!\nTranslate the word: <b>{current_word['eng']}</b>",
            parse_mode="HTML",
        )

    @router.message(Command("stop"))
    async def stop_game(message: Message):
        global game_active

        if not game_active:
            await message.reply("The game is not active.")
            return

        game_active = False

        if scores:
            stats = sorted(scores.items(), key=lambda x: -x[1])
            res = []
            for user_id, score in stats:
                try:
                    member = await message.bot.get_chat_member(chat_id, user_id)
                    res.append(f"{member.user.first_name}: {score}")
                except Exception:
                    res.append(f"Player {user_id}: {score}")

            result_text = "\n".join(res)
            await message.bot.send_message(
                chat_id,
                f"The game has been stopped.\n\n<b>Leaderboard:</b>\n{result_text}",
                parse_mode="HTML",
            )
        else:
            await message.bot.send_message(
                chat_id, "The game has been stopped. Nobody earned any points.", parse_mode="HTML"
            )

    @router.message(F.text)
    async def handle_message(message: Message):
        global game_active

        if not game_active or not current_word:
            return

        if message.text.strip().lower() in [ans.lower() for ans in current_answers]:
            scores[message.from_user.id] += 1

            leaderboard = []
            for uid, score in scores.items():
                try:
                    member = await message.bot.get_chat_member(chat_id, uid)
                    leaderboard.append(f"{member.user.first_name}: {score}")
                except Exception:
                    leaderboard.append(f"Player {uid}: {score}")

            leaderboard_text = "\n".join(leaderboard)

            await message.bot.send_message(
                chat_id,
                f"✅ <b>{message.from_user.first_name}</b> scores a point!\n"
                f"Correct translation: <b>{current_word['eng']}</b> — <b>{current_word['rus']}</b>\n\n"
                f"Current standings:\n{leaderboard_text}",
                parse_mode="HTML",
            )

            new_round()

            await message.bot.send_message(
                chat_id, f"Next word:\nTranslate: <b>{current_word['eng']}</b>", parse_mode="HTML"
            )

    return router
