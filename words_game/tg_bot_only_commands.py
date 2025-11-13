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

bott = None

class GameStates(StatesGroup):
    waiting_players = State()
    game_started = State()


DB_NAME = "words_game/words_game.db"
active_games = {}


async def update_lobby_message(chat_id, game):
    players_list = "\n".join([f"👤 {name}" for name in game["players"].values()])
    message_text = (
        f"🎮 Game #{game['session_id']} created!\n"
        f"Waiting for players...\n\n"
        f"Players ({len(game['players'])}):\n{players_list}\n\n"
        f"Others can join with /join\n"
        f"The creator can start the game with /startgame"
    )

    try:
        if game.get("lobby_message_id"):
            await bott.edit_message_text(
                chat_id=chat_id, message_id=game["lobby_message_id"], text=message_text
            )
        else:
            message = await bott.send_message(chat_id, message_text)
            game["lobby_message_id"] = message.message_id

    except Exception as e:
        # print(f"Failed to update lobby message: {e}")
        message = await bott.send_message(chat_id, message_text)
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
                current_chat_id, "❌ Unable to find game data."
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
                winner_name[0] if winner_name else f"Player {last_word_user_id}"
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
                f"🏆 Game finished!\n\n"
                f"Winner: {winner_name} 🎉\n"
                f"The last player to give a word becomes the champion!",
            )
        else:
            await bot.send_message(
                current_chat_id, "Unfortunately, no winner was determined."
            )

    except Exception as e:
        # print(f"Failed to announce winner: {e}")
        conn.rollback()
    finally:
        conn.close()


def get_router(bot):
    global active_games
    global bott
    bott = bot
    # active_games = {}
    logging.basicConfig(level=logging.INFO)

    asyncio.ensure_future(check_expired_games_periodically())
    router = Router()
    router.message.filter(ModeFilter("words"))

    create_database("words_game/words_game.db")
    create_tables("words_game/words_game.db")

    @router.message(Command("start"))
    async def cmd_start(message: types.Message):

        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name
        add_or_update_user(DB_NAME, user_id, username)

        help_text = (
            "Hi! I'm the word chain bot 🎮\n\n"
            "📋 Available commands:\n"
            "/newgame - Create a new game\n"
            "/join - Join the current game\n"
            "/startgame - Start the game (creator only)\n"
            "/stop - End the game (creator only)\n"
            "/rating - Show the leaderboard\n"
            "/leave - Leave the game\n\n"
            "How to play:\n"
            "1. The creator runs /newgame\n"
            "2. Others join with /join\n"
            "3. The creator runs /startgame\n"
            "4. Players take turns naming words\n"
            "5. Each word must start with the last letter of the previous word\n"
            "6. The creator can end the game with /stop\n"
            "7. The game auto-ends 10 minutes after it starts\n"
        )

        await message.answer(help_text)

    @router.message(Command("newgame"))
    async def cmd_newgame(message: types.Message, state: FSMContext):

        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name

        add_or_update_user(DB_NAME, user_id, username)

        if chat_id in active_games:
            await message.answer("❌ There is already an active game in this chat!")
            return

        await state.clear()

        session_id = add_game_session("words_game/words_game.db", chat_id, user_id)

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

    @router.message(Command("join"))
    async def cmd_join(message: types.Message):

        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name

        add_or_update_user(DB_NAME, user_id, username)

        try:
            await message.delete()
        except Exception as e:
            # print(f"Could not delete message: {e}")
            pass

        if chat_id not in active_games:
            response = await message.answer(
                "❌ No active game in this chat. Create one with /newgame."
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
        add_game_player("words_game/words_game.db", session_id, user_id, order_join)

        confirmation = await message.answer(
            f"✅ {message.from_user.full_name} joined the game!"
        )

        await asyncio.sleep(1.5)
        try:
            await confirmation.delete()
        except:
            pass

        await update_lobby_message(chat_id, game)

    @router.message(Command("startgame"))
    async def cmd_startgame(message: types.Message):

        chat_id = message.chat.id
        user_id = message.from_user.id
        username = message.from_user.username or message.from_user.full_name

        add_or_update_user(DB_NAME, user_id, username)

        if chat_id not in active_games:
            await message.answer("❌ Game not found!")
            return

        game = active_games[chat_id]

        if user_id != game["creator_id"]:
            await message.answer("❌ Only the game creator can start the game.")
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
            await message.answer("❌ Error: game not found in the database.")
            return

        status = result[0]

        if status == "started":
            await message.answer("❌ The game is already running!")
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
                # print(f"Could not delete lobby message: {e}")
                pass

        await message.answer(
            f"🚀 The game has started!\n\n"
            f"First word: {start_word} - {translation}\n\n"
            f"🎯 Next turn: {next_player_name}\n\n"
            f"Players type words in the chat. Each word must start with the final letter of the previous word."
        )

        active_games[chat_id]["current_player"] = next_player_id

    @router.message(Command("stop"))
    async def cmd_stop(message: types.Message):

        chat_id = message.chat.id
        user_id = message.from_user.id

        if chat_id not in active_games:
            await message.answer("❌ There is no active game in this chat.")
            return

        game = active_games[chat_id]

        if user_id != game["creator_id"]:
            await message.answer("❌ Only the game creator can end the game.")
            return

        session_id = game["session_id"]

        session_status = get_session_status(DB_NAME, session_id)
        if session_status == "finished":
            await message.answer("❌ The game has already finished.")
            return

        update_game_finish("words_game/words_game.db", session_id)

        await announce_winner("words_game/words_game.db", session_id, chat_id, bot)

        del active_games[chat_id]

        await message.answer("🛑 The game was ended by the creator.")

    @router.message(Command("rating"))
    async def cmd_rating(message: types.Message):

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
                rating_text = "🏆 Top players in this chat:\n\n"

                for i, (username, score, games_played) in enumerate(leaders, 1):
                    win_rate = (score / games_played * 100) if games_played > 0 else 0
                    rating_text += f"{i}. {username} - {score} wins ({games_played} games, {win_rate:.1f}%)\n"

            else:
                rating_text = "📊 Leaderboard is empty.\n\nNo games have been played in this chat yet."

            await message.answer(rating_text)

        except Exception as e:
            # print(f"Failed to load leaderboard: {e}")
            await message.answer("❌ Failed to load the leaderboard.")
        finally:
            conn.close()

    @router.message(Command("leave"))
    async def cmd_leave(message: types.Message):

        chat_id = message.chat.id
        user_id = message.from_user.id
        try:
            await message.delete()
        except Exception as e:
            # print(f"Could not delete message: {e}")
            pass

        if chat_id not in active_games:
            response = await message.answer("❌ There is no active game in this chat.")
            await asyncio.sleep(3)
            try:
                await response.delete()
            except:
                pass
            return

        if user_id not in active_games[chat_id]["players"]:
            response = await message.answer("❌ You are not part of this game.")
            await asyncio.sleep(3)
            try:
                await response.delete()
            except:
                pass
            return

        game = active_games[chat_id]
        session_id = game["session_id"]
        session_status = get_session_status(DB_NAME, session_id)

        await message.answer(f"🚪 {message.from_user.full_name} left the game.")

        deactivate_game_player("words_game/words_game.db", session_id, user_id)

        del game["players"][user_id]

        if session_status == "started" and game.get("current_player") == user_id:
            next_player_id = get_next_player(DB_NAME, session_id, user_id)
            game["current_player"] = next_player_id

            if next_player_id:
                next_player_name = get_player_name(DB_NAME, next_player_id)
                await message.answer(
                    f"🎯 Player left the game. Next turn: {next_player_name}"
                )

        if len(game["players"]) == 0:
            if session_status == "started":
                update_game_finish("words_game/words_game.db", session_id)

            del active_games[chat_id]

            await message.answer("🛑 Game ended (all players left).")

        else:
            if session_status == "waiting":
                await update_lobby_message(chat_id, game)

    async def handle_game_message(message: types.Message):

        chat_id = message.chat.id
        user_id = message.from_user.id

        if chat_id not in active_games:
            await message.answer("The game is not active.")
            return

        game = active_games[chat_id]
        session_status = get_session_status(DB_NAME, game["session_id"])
        if session_status != "started":
            await message.answer("The game hasn't started yet or is already finished.")
            return

        if user_id != game.get("current_player"):
            await message.answer("It's not your turn! Please wait for your turn.")
            return

        word = message.text.strip().lower()

        if game.get("last_word"):
            last_letter = game["last_word"][-1]
            if not word.startswith(last_letter):
                await message.answer(
                    f"❌ The word must start with the letter '{last_letter.upper()}'."
                )
                return

        translation = check_word_exists(DB_NAME, word)
        if not translation:
            await message.answer(
                "❌ This word is not in the dictionary. Try another one."
            )
            return

        session_id = game["session_id"]

        game["last_word"] = word
        update_last_word(DB_NAME, session_id, user_id, word)

        next_player_id = get_next_player(DB_NAME, session_id, user_id)
        next_player_name = get_player_name(DB_NAME, next_player_id)

        game["current_player"] = next_player_id

        await message.answer(
            f"✅ Word accepted: {word} - {translation}\n\n"
            f"🎯 Next turn: {next_player_name}"
        )

    @router.message()
    async def handle_messages(message: types.Message):
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
                    await bott.send_message(
                        chat_id,
                        f"⏰ Time is up! The game ended automatically.\n\n"
                        f"Winner: {winner_name} 🎉\n"
                        f"The game lasted more than 10 minutes.",
                    )
                else:
                    await bott.send_message(
                        chat_id,
                        "⏰ Time is up! The game ended automatically.\n\n"
                        "The game lasted more than 10 minutes.",
                    )

        except Exception as e:
            # print(f"Error while checking expired games: {e}")
            pass

        await asyncio.sleep(60)


async def main():
    # global active_games
    # active_games = {}
    # logging.basicConfig(level=logging.INFO)
    #
    # asyncio.ensure_future(check_expired_games_periodically())
    #
    # await dp.start_polling(bot)
    pass


if __name__ == "__main__":
    asyncio.run(main())
