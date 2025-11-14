import logging

from aiogram import Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

import config

from spyfall.database import Database
from spyfall.dictionary import Dictionary
from spyfall.game import GameManager
from spyfall.handlers.timer import GameTimer


logger = logging.getLogger(__name__)

MODE_NAME = "spy"


def register_commands(
    dp,
    bot: Bot,
    db: Database,
    game_manager: GameManager,
    dictionary: Dictionary,
    timer: GameTimer = None,
):
    @dp.message(Command("start"))
    async def cmd_start(message: Message, state: FSMContext):
        """Start command"""
        await message.answer(
            "🎮 Welcome to Spyfall game!\n\n"
            "Commands:\n"
            "/newgame - create a new game\n"
            "/join - join the game\n"
            "/startgame - start the game (minimum 3 players)\n"
            "/gameinfo - game information\n"
            "/mylocation - check your location\n"
            "/ask - choose who to ask a question (when it's your turn)\n"
            "/answer - pass the turn after answering a question\n"
            "/guess - spy tries to guess the location\n"
            "/vote - start voting (creates poll)\n"
            "/endgame - end the game\n"
            "/stats - your statistics\n"
            "/leaderboard - top players rating"
        )

    @dp.message(Command("newgame"))
    async def cmd_newgame(message: Message, state: FSMContext):
        """Create a new game"""
        if message.chat.type == "private":
            await message.answer("❌ This game is designed for group chats!")
            return

        active_game = await db.get_active_game(message.chat.id)
        if active_game:
            await message.answer(
                f"⚠️ There's already an active game in this chat (ID: {active_game['game_id']}).\n"
                "Use /endgame to finish it."
            )
            return

        game_id = await game_manager.create_game(message.chat.id)
        username = message.from_user.username or "Unknown"
        await game_manager.join_game(game_id, message.from_user.id, username)
        await db.init_player_stats(message.from_user.id, username)

        await message.answer(
            f"✅ New game created! ID: {game_id}\n"
            f"👤 {message.from_user.first_name} joined the game.\n\n"
            "Use /join to join."
        )

    @dp.message(Command("join"))
    async def cmd_join(message: Message, state: FSMContext):
        """Join the game"""
        if message.chat.type == "private":
            await message.answer("❌ This game is designed for group chats!")
            return

        active_game = await db.get_active_game(message.chat.id)
        if not active_game:
            await message.answer("❌ No active game. Use /newgame to create one.")
            return

        if active_game["status"] != "waiting":
            await message.answer("❌ Game has already started!")
            return

        username = message.from_user.username or "Unknown"
        success = await game_manager.join_game(
            active_game["game_id"], message.from_user.id, username
        )

        if success:
            await db.init_player_stats(message.from_user.id, username)
            players = await db.get_players(active_game["game_id"])
            await message.answer(
                f"✅ {message.from_user.first_name} joined the game!\n"
                f"👥 Players: {len(players)}\n\n"
                "Use /startgame to start (minimum 3 players)."
            )
        else:
            await message.answer("⚠️ You're already in the game!")

    @dp.message(Command("startgame"))
    async def cmd_startgame(message: Message, state: FSMContext):
        """Start the game"""
        if message.chat.type == "private":
            await message.answer("❌ This game is designed for group chats!")
            return

        active_game = await db.get_active_game(message.chat.id)
        if not active_game:
            await message.answer("❌ No active game. Use /newgame to create one.")
            return

        if active_game["status"] != "waiting":
            await message.answer("❌ Game has already started!")
            return

        duration = config.SPYFALL_GAME_DURATION
        location = await game_manager.start_game(active_game["game_id"], duration)
        if not location:
            await message.answer("❌ Not enough players! Minimum 3 players.")
            return

        players = await db.get_players(active_game["game_id"])
        spy = await db.get_spy(active_game["game_id"])
        current_player_id = await db.get_current_player(active_game["game_id"])

        if timer:
            await timer.start_timer(active_game["game_id"], message.chat.id, duration)

        for player in players:
            try:
                words = await dictionary.get_random_words(config.SPYFALL_WORDS_PER_PLAYER)
                await db.add_player_words(active_game["game_id"], player["user_id"], words)

                words_text = "\n".join(
                    [f"  • {word} - {translation}" for word, translation in words]
                )

                if player["is_spy"]:
                    await bot.send_message(
                        player["user_id"],
                        f"🎭 You are the SPY!\n\n"
                        f"You don't know the location. Your task is to guess it "
                        f"by asking questions to other players without revealing yourself.\n\n"
                        f"📚 Words to use in the game (you'll get bonus points for using them):\n{words_text}\n\n"
                        f"💡 Try to use these words naturally in your questions and answers!",
                    )
                else:
                    await bot.send_message(
                        player["user_id"],
                        f"📍 Your location: {location}\n\n"
                        f"Your task is to find the spy by asking questions to other players.\n\n"
                        f"📚 Words to use in the game (you'll get bonus points for using them):\n{words_text}\n\n"
                        f"💡 Try to use these words naturally in your questions and answers!",
                    )
            except Exception as e:
                logger.error(f"Error sending message to player {player['user_id']}: {e}")

        current_player = next((p for p in players if p["user_id"] == current_player_id), None)
        if current_player:
            try:
                user = await bot.get_chat_member(message.chat.id, current_player_id)
                player_name = user.user.first_name
            except:
                player_name = current_player["username"] or "Unknown"

            await message.answer(
                f"🎮 Game started!\n\n"
                f"👥 Players: {len(players)}\n"
                f"⏰ Game duration: {duration // 60} minutes\n"
                f"📍 Location has been chosen and sent to each player in private messages.\n\n"
                f"🎯 It's {player_name}'s turn to ask a question!\n"
                f"Use /ask to choose who to ask."
            )
        else:
            await message.answer(
                f"🎮 Game started!\n\n"
                f"👥 Players: {len(players)}\n"
                f"⏰ Game duration: {duration // 60} minutes\n"
                f"📍 Location has been chosen and sent to each player in private messages."
            )

    @dp.message(Command("gameinfo"))
    async def cmd_gameinfo(message: Message, state: FSMContext):
        """Game information"""
        if message.chat.type == "private":
            await message.answer("❌ This game is designed for group chats!")
            return

        active_game = await db.get_active_game(message.chat.id)
        if not active_game:
            await message.answer("❌ No active game.")
            return

        players = await db.get_players(active_game["game_id"])
        spy = await db.get_spy(active_game["game_id"])

        players_list = "\n".join([f"  • {p['username'] or 'Unknown'}" for p in players])

        status_emoji = "⏳" if active_game["status"] == "waiting" else "🎮"

        await message.answer(
            f"{status_emoji} Game information:\n\n"
            f"ID: {active_game['game_id']}\n"
            f"Status: {active_game['status']}\n"
            f"Players: {len(players)}\n\n"
            f"Players:\n{players_list}"
        )

    @dp.message(Command("mylocation"))
    async def cmd_mylocation(message: Message, state: FSMContext):
        """Check your location"""
        active_game = await db.get_active_game(message.chat.id)
        if not active_game:
            await message.answer("❌ No active game.")
            return

        if active_game["status"] != "playing":
            await message.answer("❌ Game hasn't started yet.")
            return

        location = await game_manager.get_location_for_player(
            active_game["game_id"], message.from_user.id
        )

        if location is None:
            await bot.send_message(
                message.from_user.id, "🎭 You are the SPY! You don't know the location."
            )
        else:
            await bot.send_message(message.from_user.id, f"📍 Your location: {location}")

    @dp.message(Command("ask"))
    async def cmd_ask(message: Message, state: FSMContext):
        """Choose who to ask a question"""
        if message.chat.type == "private":
            await message.answer("❌ This game is designed for group chats!")
            return

        active_game = await db.get_active_game(message.chat.id)
        if not active_game:
            await message.answer("❌ No active game.")
            return

        if active_game["status"] != "playing":
            await message.answer("❌ Game hasn't started yet.")
            return

        current_player_id = await db.get_current_player(active_game["game_id"])
        if current_player_id != message.from_user.id:
            try:
                user = await bot.get_chat_member(message.chat.id, current_player_id)
                player_name = user.user.first_name
            except:
                player_name = "Unknown"
            await message.answer(f"❌ It's not your turn! It's {player_name}'s turn.")
            return

        players = await db.get_players(active_game["game_id"])

        keyboard = []
        for player in players:
            if player["user_id"] != message.from_user.id:
                try:
                    user = await bot.get_chat_member(message.chat.id, player["user_id"])
                    username = user.user.first_name or player["username"] or "Unknown"
                except:
                    username = player["username"] or "Unknown"

                keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=username,
                            callback_data=f"ask_{active_game['game_id']}_{player['user_id']}",
                        )
                    ]
                )

        if not keyboard:
            await message.answer("❌ No other players to ask.")
            return

        await message.answer(
            "❓ Choose who you want to ask a question:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        )

    @dp.message(Command("answer"))
    async def cmd_answer(message: Message, state: FSMContext):
        """Answer that you've been asked"""
        if message.chat.type == "private":
            await message.answer("❌ This game is designed for group chats!")
            return

        active_game = await db.get_active_game(message.chat.id)
        if not active_game:
            await message.answer("❌ No active game.")
            return

        if active_game["status"] != "playing":
            await message.answer("❌ Game hasn't started yet.")
            return

        target_player_id = await db.get_target_player(active_game["game_id"])
        if target_player_id != message.from_user.id:
            if target_player_id:
                try:
                    user = await bot.get_chat_member(message.chat.id, target_player_id)
                    target_name = user.user.first_name
                except:
                    target_name = "Unknown"
                await message.answer(f"❌ You weren't asked! {target_name} was asked.")
            else:
                await message.answer(
                    "❌ No one is currently being asked. Use /ask to ask someone first."
                )
            return

        await db.clear_target_player(active_game["game_id"])
        await db.set_current_player(active_game["game_id"], message.from_user.id)

        players = await db.get_players(active_game["game_id"])

        keyboard = []
        for player in players:
            if player["user_id"] != message.from_user.id:
                try:
                    user = await bot.get_chat_member(message.chat.id, player["user_id"])
                    username = user.user.first_name or player["username"] or "Unknown"
                except:
                    username = player["username"] or "Unknown"

                keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=username,
                            callback_data=f"ask_{active_game['game_id']}_{player['user_id']}",
                        )
                    ]
                )

        try:
            user = await bot.get_chat_member(message.chat.id, message.from_user.id)
            player_name = user.user.first_name
        except:
            player_name = message.from_user.username or "Unknown"

        if keyboard:
            await message.answer(
                f"✅ {player_name} answered!\n\n"
                f"🎯 Now it's {player_name}'s turn to ask a question:\n"
                f"Choose who you want to ask:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
            )
        else:
            await message.answer(f"✅ {player_name} answered!")

    @dp.message(Command("guess"))
    async def cmd_guess(message: Message, state: FSMContext):
        """Allow spy to guess the location"""
        if message.chat.type == "private":
            await message.answer("❌ This command is available only in group chats!")
            return

        active_game = await db.get_active_game(message.chat.id)
        if not active_game:
            await message.answer("❌ No active game.")
            return

        if active_game["status"] != "playing":
            await message.answer("❌ Game hasn't started yet.")
            return

        spy = await db.get_spy(active_game["game_id"])
        if not spy or spy["user_id"] != message.from_user.id:
            await message.answer("❌ Only the spy can use this command.")
            return

        keyboard = []
        row = []
        for idx, location in enumerate(config.SPYFALL_LOCATIONS):
            row.append(
                InlineKeyboardButton(
                    text=location,
                    callback_data=f"guess_{active_game['game_id']}_{idx}",
                )
            )
            if len(row) == 2:
                keyboard.append(row)
                row = []

        if row:
            keyboard.append(row)

        await message.answer(
            "🎯 Choose the location you want to name:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        )

    @dp.message(Command("vote"))
    async def cmd_vote(message: Message, state: FSMContext):
        """Start voting with poll"""
        if message.chat.type == "private":
            await message.answer("❌ This game is designed for group chats!")
            return

        active_game = await db.get_active_game(message.chat.id)
        if not active_game:
            await message.answer("❌ No active game.")
            return

        if active_game["status"] != "playing":
            await message.answer("❌ Game hasn't started yet.")
            return

        players = await db.get_players(active_game["game_id"])
        if len(players) < 2:
            await message.answer("❌ Not enough players for voting.")
            return

        if active_game.get("poll_id"):
            await message.answer(
                "⚠️ Voting poll already exists! Voting will automatically finish when all players have voted."
            )
            return

        if timer:
            await timer.stop_timer(active_game["game_id"])

        await db.clear_votes(active_game["game_id"])

        options = []
        player_map = {}

        for player in players:
            try:
                user = await bot.get_chat_member(message.chat.id, player["user_id"])
                username = user.user.first_name or player["username"] or "Unknown"
            except:
                username = player["username"] or "Unknown"

            if len(username) > 30:
                username = username[:27] + "..."

            options.append(username)
            player_map[len(options) - 1] = player["user_id"]

        if not options:
            await message.answer("❌ No players to vote for.")
            return

        try:
            poll_message = await bot.send_poll(
                chat_id=message.chat.id,
                question="🗳️ Who is the spy?",
                options=options,
                is_anonymous=False,
                allows_multiple_answers=False,
                type="regular",
            )

            poll_id = poll_message.poll.id
            await db.set_poll_id(active_game["game_id"], poll_id)

            await message.answer(
                "✅ Voting poll created!\n\n"
                "Vote in the poll above. Voting will automatically finish when all players have voted."
            )
        except Exception as e:
            logger.error(f"Error creating poll: {e}")
            await message.answer("❌ Error creating poll. Please try again.")

    @dp.message(Command("endgame"))
    async def cmd_endgame(message: Message, state: FSMContext):
        """End the game"""
        if message.chat.type == "private":
            await message.answer("❌ This game is designed for group chats!")
            return

        active_game = await db.get_active_game(message.chat.id)
        if not active_game:
            await message.answer("❌ No active game.")
            return

        if timer:
            await timer.stop_timer(active_game["game_id"])

        await game_manager.finish_game(active_game["game_id"])
        await message.answer("✅ Game finished.")

    @dp.message(Command("stats"))
    async def cmd_stats(message: Message, state: FSMContext):
        """Show player statistics"""
        stats = await db.get_player_stats(message.from_user.id)

        if not stats or stats["games_played"] == 0:
            await message.answer(
                "📊 Your Statistics:\n\n"
                "You haven't played any games yet.\n"
                "Join a game to start earning statistics!"
            )
            return

        win_rate = (
            (stats["games_won"] / stats["games_played"] * 100) if stats["games_played"] > 0 else 0
        )
        spy_win_rate = (
            (stats["spy_wins"] / (stats["spy_wins"] + stats["spy_losses"]) * 100)
            if (stats["spy_wins"] + stats["spy_losses"]) > 0
            else 0
        )
        civilian_win_rate = (
            (stats["civilian_wins"] / (stats["civilian_wins"] + stats["civilian_losses"]) * 100)
            if (stats["civilian_wins"] + stats["civilian_losses"]) > 0
            else 0
        )

        bonus_points = stats.get("bonus_points", 0)

        stats_text = (
            f"📊 Your Statistics:\n\n"
            f"🏆 Rating: {stats['rating']}\n"
            f"⭐ Bonus points: {bonus_points}\n\n"
            f"📈 Overall:\n"
            f"  • Games played: {stats['games_played']}\n"
            f"  • Wins: {stats['games_won']}\n"
            f"  • Losses: {stats['games_lost']}\n"
            f"  • Win rate: {win_rate:.1f}%\n\n"
            f"🎭 As Spy:\n"
            f"  • Wins: {stats['spy_wins']}\n"
            f"  • Losses: {stats['spy_losses']}\n"
            f"  • Win rate: {spy_win_rate:.1f}%\n\n"
            f"👤 As Civilian:\n"
            f"  • Wins: {stats['civilian_wins']}\n"
            f"  • Losses: {stats['civilian_losses']}\n"
            f"  • Win rate: {civilian_win_rate:.1f}%"
        )

        await message.answer(stats_text)

    @dp.message(Command("leaderboard"))
    async def cmd_leaderboard(message: Message, state: FSMContext):
        """Show leaderboard"""
        leaderboard = await db.get_leaderboard(limit=10)

        if not leaderboard:
            await message.answer("📊 Leaderboard is empty. Be the first to play!")
            return

        leaderboard_text = "🏆 Top Players:\n\n"

        medals = ["🥇", "🥈", "🥉"]
        for i, player in enumerate(leaderboard, 1):
            medal = medals[i - 1] if i <= 3 else f"{i}."
            username = player["username"] or "Unknown"
            rating = player["rating"]
            wins = player["games_won"]
            games = player["games_played"]

            leaderboard_text += (
                f"{medal} {username}\n   Rating: {rating} | Wins: {wins}/{games}\n\n"
            )

        await message.answer(leaderboard_text)
