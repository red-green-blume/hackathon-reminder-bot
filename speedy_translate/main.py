import asyncio
import random
import csv
import os
from dotenv import load_dotenv
from collections import defaultdict
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message

load_dotenv()

bot = Bot(token=os.environ["BOT_TOKEN"])
dp = Dispatcher()

dictionary = []
current_word = None
current_answers = []
game_active = False
scores = defaultdict(int)
chat_id = None


def load_dictionary():
    global dictionary
    with open('dictionary.csv', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        dictionary = [{'eng': row[0].strip(), 'rus': row[1].strip()} for row in reader]


def new_round():
    global current_word, current_answers
    current_word = random.choice(dictionary)
    current_answers = [d['rus'] for d in dictionary if d['eng'] == current_word['eng']]


@dp.message(Command('poll_start'))
async def start_game(message: Message):
    global game_active, scores, chat_id
    if game_active:
        await message.reply("Игра уже идет!")
        return

    load_dictionary()
    game_active = True
    scores = defaultdict(int)
    chat_id = message.chat.id
    new_round()

    await message.answer(
        f"Игра началась!\nПереведите слово: <b>{current_word['eng']}</b>",
        parse_mode='HTML'
    )


@dp.message(Command('poll_stop'))
async def stop_game(message: Message):
    global game_active
    if not game_active:
        await message.reply("Сейчас игра не активна.")
        return

    game_active = False

    if scores:
        stats = sorted(scores.items(), key=lambda x: -x[1])
        res = []
        for user_id, score in stats:
            try:
                member = await bot.get_chat_member(chat_id, user_id)
                res.append(f"{member.user.first_name}: {score}")
            except:
                res.append(f"Пользователь {user_id}: {score}")

        result_text = "\n".join(res)
        await bot.send_message(
            chat_id,
            f"Игра остановлена.\n\n<b>Статистика:</b>\n{result_text}",
            parse_mode='HTML'
        )
    else:
        await bot.send_message(
            chat_id,
            "Игра остановлена. Никто не успел набрать баллы.",
            parse_mode='HTML'
        )


@dp.message(F.text)
async def handle_message(message: Message):
    global game_active

    if not game_active or not current_word:
        return

    if message.text.strip().lower() in [ans.lower() for ans in current_answers]:
        scores[message.from_user.id] += 1

        leaderboard = []
        for uid, score in scores.items():
            try:
                member = await bot.get_chat_member(chat_id, uid)
                leaderboard.append(f"{member.user.first_name}: {score}")
            except:
                leaderboard.append(f"Пользователь {uid}: {score}")

        leaderboard_text = "\n".join(leaderboard)

        await bot.send_message(
            chat_id,
            f"✅ <b>{message.from_user.first_name}</b> получает балл!\n"
            f"Правильный перевод: <b>{current_word['eng']}</b> — <b>{current_word['rus']}</b>\n\n"
            f"Текущее лидерство:\n{leaderboard_text}",
            parse_mode='HTML'
        )

        new_round()

        await bot.send_message(
            chat_id,
            f"Следующее слово:\nПереведите: <b>{current_word['eng']}</b>",
            parse_mode='HTML'
        )


async def main():
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
