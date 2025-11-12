import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
import os

from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime
from filter import ModeFilter
from words_game.work_with_dp import *


MODE_NAME = "words"


class GameStates(StatesGroup):
    waiting_players = State()
    game_started = State()


DB_NAME = "words_game/words_game.db"
load_dotenv()
BOT_TOKEN = "8530593033:AAEU-qlMM28wSsboRZtr6mnwkU-TbAEsBm8"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

active_games = {}


async def update_lobby_message(chat_id, game):
    players_list = "\n".join([f"👤 {name}" for name in game["players"].values()])
    message_text = (
        f"🎮 Игра #{game['session_id']} создана!\n"
        f"Ожидаем игроков...\n\n"
        f"Участники ({len(game['players'])}):\n{players_list}\n\n"
        f"Другие игроки могут присоединиться командой /2_join\n"
        f"Создатель может запустить игру командой /2_startgame"
    )

    try:
        if game.get("lobby_message_id"):
            await bot.edit_message_text(
                chat_id=chat_id, message_id=game["lobby_message_id"], text=message_text
            )
        else:
            message = await bot.send_message(chat_id, message_text)
            game["lobby_message_id"] = message.message_id

    except Exception as e:
        # print(f"Ошибка при обновлении лобби: {e}")
        message = await bot.send_message(chat_id, message_text)
        game["lobby_message_id"] = message.message_id


async def announce_winner(db_name, session_id, current_chat_id, bot):
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT last_word_user_id, chat_id 
            FROM game_session 
            WHERE id = ? AND session_status = 'finished'
        """,
            (session_id,),
        )
        game_data = cursor.fetchone()

        if not game_data:
            await bot.send_message(
                current_chat_id, "❌ Не удалось найти данные об игре."
            )
            return

        last_word_user_id, db_chat_id = game_data

        update_games_played_for_all_players(db_name, session_id, db_chat_id)

        if last_word_user_id:
            cursor.execute(
                "SELECT username FROM users WHERE tg_id = ?", (last_word_user_id,)
            )
            winner_name = cursor.fetchone()
            winner_name = (
                winner_name[0] if winner_name else f"Игрок {last_word_user_id}"
            )

            cursor.execute(
                """
                UPDATE leaders 
                SET score = score + 1
                WHERE chat_id = ? AND user_id = ?
            """,
                (db_chat_id, last_word_user_id),
            )

            conn.commit()

            await bot.send_message(
                current_chat_id,
                f"🏆 Игра завершена!\n\n"
                f"Победитель: {winner_name} 🎉\n"
                f"Последний назвавший слово становится чемпионом!",
            )
        else:
            await bot.send_message(
                current_chat_id, "К сожалению, победитель не определен."
            )

    except Exception as e:
        # print(f"Ошибка при объявлении победителя: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_router(bot):
    global active_games
    active_games = {}
    logging.basicConfig(level=logging.INFO)

    asyncio.ensure_future(check_expired_games_periodically())
    router = Router()
    router.message.filter(ModeFilter("words"))

    @router.message(Command("/start"))
    async def cmd_start(message: types.Message, state: FSMContext):

        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        add_or_update_user(DB_NAME, user_id, username)

        help_text = (
            "Привет! Я бот для игры в слова! 🎮\n\n"
            "📋 Доступные команды:\n"
            "/2_newgame - Создать новую игру\n"
            "/2_join - Присоединиться к игре\n"
            "/2_startgame - Запустить игру (только создатель игры)\n"
            "/2_stop - Завершить игру (только создатель игры)\n"
            "/2_rating - Показать рейтинг\n"
            "/2_leave - Покинуть игру\n\n"
            "Как играть:\n"
            "1. Создатель пишет /2_newgame\n"
            "2. Другие игроки пишут /2_join\n"
            "3. Создатель пишет /2_startgame\n"
            "4. Игроки по очереди называют слова\n"
            "5. Слово должно начинаться на последнюю букву предыдущего\n"
            "6. Создатель пишет /2_stop чтобы завершить игру\n"
            "7. Игра автоматически завершается через 10 минут после начала\n"
        )

        await message.answer(help_text)

    @router.message(Command("2_newgame"))
    async def cmd_newgame(message: types.Message, state: FSMContext):

        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name

        add_or_update_user(DB_NAME, user_id, username)

        if chat_id in active_games:
            await message.answer("❌ В этом чате уже есть активная игра!")
            return

        await state.clear()

        session_id = add_game_session("words_game.db", chat_id, user_id)

        active_games[chat_id] = {
            "creator_id": user_id,
            "players": {user_id: message.from_user.full_name},
            "created_at": datetime.now(),
            "session_id": session_id,
            "current_player": None,
            "last_word": None,
            "lobby_message_id": None,
        }

        game = active_games[chat_id]
        await update_lobby_message(chat_id, game)

    @router.message(Command("2_join"))
    async def cmd_join(message: types.Message, state: FSMContext):

        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name

        add_or_update_user(DB_NAME, user_id, username)

        try:
            await message.delete()
        except Exception as e:
            # print(f"Не удалось удалить сообщение: {e}")
            pass

        if chat_id not in active_games:
            response = await message.answer(
                "❌ В этом чате нет активной игры. Создайте игру командой /2_newgame"
            )
            await asyncio.sleep(3)
            try:
                await response.delete()
            except:
                pass
            return

        game = active_games[chat_id]

        if user_id in active_games[chat_id]["players"]:
            return

        session_id = game["session_id"]

        game["players"][user_id] = message.from_user.full_name

        order_join = len(game["players"])
        add_game_player("words_game.db", session_id, user_id, order_join)

        confirmation = await message.answer(
            f"✅ {message.from_user.full_name} присоединился к игре!"
        )

        await asyncio.sleep(1.5)
        try:
            await confirmation.delete()
        except:
            pass

        await update_lobby_message(chat_id, game)

    @router.message(Command("2_startgame"))
    async def cmd_startgame(message: types.Message, state: FSMContext):

        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name

        add_or_update_user(DB_NAME, user_id, username)

        if chat_id not in active_games:
            await message.answer("❌ Игра не найдена!")
            return

        game = active_games[chat_id]

        if user_id != game["creator_id"]:
            await message.answer("❌ Только создатель игры может запустить её.")
            return

        session_id = game["session_id"]

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_status FROM game_session WHERE id = ?", (session_id,)
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            await message.answer("❌ Ошибка: игра не найдена в базе")
            return

        status = result[0]

        if status == "started":
            await message.answer("❌ Игра уже запущена!")
            return

        update_game_start(DB_NAME, session_id)

        start_word, translation = get_random_word(DB_NAME)

        active_games[chat_id]["last_word"] = start_word

        next_player_id = get_next_player(DB_NAME, session_id, user_id)
        next_player_name = get_player_name(DB_NAME, next_player_id)

        if game.get("lobby_message_id"):
            try:
                await bot.delete_message(chat_id, game["lobby_message_id"])
            except Exception as e:
                # print(f"Не удалось удалить сообщение лобби: {e}")
                pass

        await message.answer(
            f"🚀 Игра началась!\n\n"
            f"Первое слово: {start_word} - {translation}\n\n"
            f"🎯 Следующий ход: {next_player_name}\n\n"
            f"Игроки пишут слова в чат. Слово должно начинаться на последнюю букву предыдущего слова."
        )

        active_games[chat_id]["current_player"] = next_player_id

    @router.message(Command("2_stop"))
    async def cmd_stop(message: types.Message, state: FSMContext):

        chat_id = message.chat.id
        user_id = message.from_user.id

        if chat_id not in active_games:
            await message.answer("❌ В этом чате нет активной игры.")
            return

        game = active_games[chat_id]

        if user_id != game["creator_id"]:
            await message.answer("❌ Только создатель игры может завершить её.")
            return

        session_id = game["session_id"]

        session_status = get_session_status(DB_NAME, session_id)
        if session_status == "finished":
            await message.answer("❌ Игра уже завершена.")
            return

        update_game_finish("words_game.db", session_id)

        await announce_winner("words_game.db", session_id, chat_id, bot)

        del active_games[chat_id]

        await message.answer("🛑 Игра завершена создателем.")

    @router.message(Command("2_rating"))
    async def cmd_rating(message: types.Message, state: FSMContext):

        chat_id = message.chat.id

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                SELECT u.username, l.score, l.game_played 
                FROM leaders l
                JOIN users u ON l.user_id = u.tg_id
                WHERE l.chat_id = ?
                ORDER BY l.score DESC, l.game_played DESC
                LIMIT 10
            """,
                (chat_id,),
            )

            leaders = cursor.fetchall()

            if leaders:
                rating_text = "🏆 Топ игроков этого чата:\n\n"

                for i, (username, score, games_played) in enumerate(leaders, 1):
                    win_rate = (score / games_played * 100) if games_played > 0 else 0
                    rating_text += f"{i}. {username} - {score} побед ({games_played} игр, {win_rate:.1f}%)\n"

            else:
                rating_text = "📊 Рейтинг пуст\n\nВ этом чате еще не было игр."

            await message.answer(rating_text)

        except Exception as e:
            # print(f"Ошибка при загрузке рейтинга: {e}")
            await message.answer("❌ Ошибка при загрузке рейтинга.")
        finally:
            conn.close()

    @router.message(Command("2_leave"))
    async def cmd_leave(message: types.Message, state: FSMContext):

        chat_id = message.chat.id
        user_id = message.from_user.id
        try:
            await message.delete()
        except Exception as e:
            # print(f"Не удалось удалить сообщение: {e}")
            pass

        if chat_id not in active_games:
            response = await message.answer("❌ В этом чате нет активной игры.")
            await asyncio.sleep(3)
            try:
                await response.delete()
            except:
                pass
            return

        if user_id not in active_games[chat_id]["players"]:
            response = await message.answer("❌ Вы не участвуете в этой игре.")
            await asyncio.sleep(3)
            try:
                await response.delete()
            except:
                pass
            return

        game = active_games[chat_id]
        session_id = game["session_id"]
        session_status = get_session_status(DB_NAME, session_id)

        await message.answer(f"🚪 {message.from_user.full_name} вышел из игры")

        deactivate_game_player("words_game.db", session_id, user_id)

        del game["players"][user_id]

        if session_status == "started" and game.get("current_player") == user_id:
            next_player_id = get_next_player(DB_NAME, session_id, user_id)
            game["current_player"] = next_player_id

            if next_player_id:
                next_player_name = get_player_name(DB_NAME, next_player_id)
                await message.answer(
                    f"🎯 Игрок вышел из игры. Следующий ход: {next_player_name}"
                )

        if len(game["players"]) == 0:
            if session_status == "started":
                update_game_finish("words_game.db", session_id)

            del active_games[chat_id]

            await message.answer("🛑 Игра завершена (все игроки вышли)")

        else:
            if session_status == "waiting":
                await update_lobby_message(chat_id, game)

    async def handle_game_message(message: types.Message, state: FSMContext):

        chat_id = message.chat.id
        user_id = message.from_user.id

        if chat_id not in active_games:
            await message.answer("Игра не активна")
            return

        game = active_games[chat_id]
        session_status = get_session_status(DB_NAME, game["session_id"])
        if session_status != "started":
            await message.answer("Игра еще не начата или уже завершена")
            return

        if user_id != game.get("current_player"):
            await message.answer(f"Сейчас не ваш ход! Ждите своей очереди.")
            return

        word = message.text.strip().lower()

        if game.get("last_word"):
            last_letter = game["last_word"][-1]
            if not word.startswith(last_letter):
                await message.answer(
                    f"❌ Слово должно начинаться на букву '{last_letter.upper()}'!"
                )
                return

        translation = check_word_exists(DB_NAME, word)
        if not translation:
            await message.answer(
                "❌ Это слово не найдено в словаре! Попробуйте другое слово."
            )
            return

        session_id = game["session_id"]

        game["last_word"] = word
        update_last_word(DB_NAME, session_id, user_id, word)

        next_player_id = get_next_player(DB_NAME, session_id, user_id)
        next_player_name = get_player_name(DB_NAME, next_player_id)

        game["current_player"] = next_player_id

        await message.answer(
            f"✅ Слово принято: {word} - {translation}\n\n"
            f"🎯 Следующий ход: {next_player_name}"
        )

    @router.message()
    async def handle_messages(message: types.Message, state: FSMContext):
        if not await ensure_mode(message, state, False):
            return

        chat_id = message.chat.id

        if not message.text:
            return

        if message.text.startswith("/"):
            return

        if chat_id not in active_games:
            return

        game = active_games[chat_id]
        session_id = game["session_id"]

        session_status = get_session_status(DB_NAME, session_id)

        if session_status == "started":
            await handle_game_message(message)
            return
        else:
            return

    return router


async def check_expired_games_periodically():
    while True:
        try:
            finished_games = check_and_finish_expired_games(DB_NAME)

            for game_id, chat_id, last_word_user_id in finished_games:
                if chat_id in active_games:
                    del active_games[chat_id]

                winner_name = get_winner_and_update_leaders(DB_NAME, game_id)
                if winner_name:
                    await bot.send_message(
                        chat_id,
                        f"⏰ Время вышло! Игра автоматически завершена.\n\n"
                        f"Победитель: {winner_name} 🎉\n"
                        f"Игра длилась более 10 минут.",
                    )
                else:
                    await bot.send_message(
                        chat_id,
                        "⏰ Время вышло! Игра автоматически завершена.\n\n"
                        "Игра длилась более 10 минут.",
                    )

        except Exception as e:
            # print(f"Ошибка в проверке просроченных игр: {e}")
            pass

        await asyncio.sleep(60)


async def main():
    global active_games
    active_games = {}
    logging.basicConfig(level=logging.INFO)

    asyncio.ensure_future(check_expired_games_periodically())

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
