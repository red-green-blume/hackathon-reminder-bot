import logging

from aiogram import Bot, F
from aiogram.types import CallbackQuery, PollAnswer

import config

from spyfall.database import Database
from spyfall.game import GameManager
from spyfall.handlers.voting import apply_game_results, finish_voting


logger = logging.getLogger(__name__)


def register_callbacks(dp, bot: Bot, db: Database, game_manager: GameManager, timer=None):
    """Register callback handlers"""

    @dp.poll_answer()
    async def process_poll_answer(poll_answer: PollAnswer):
        """Process poll answer (vote)"""
        poll_id = poll_answer.poll_id
        user_id = poll_answer.user.id

        game = await db.get_game_by_poll_id(poll_id)
        if not game:
            logger.warning(f"Game not found for poll_id: {poll_id}")
            return

        if game["status"] != "playing":
            logger.warning(f"Game {game['game_id']} is not in playing status")
            return

        players = await db.get_players(game["game_id"])

        if not poll_answer.option_ids:
            return

        selected_option_index = poll_answer.option_ids[0]

        if selected_option_index < len(players):
            suspect = players[selected_option_index]
            suspect_id = suspect["user_id"]

            await game_manager.vote(game["game_id"], user_id, suspect_id)

            logger.info(f"User {user_id} voted for {suspect_id} in game {game['game_id']}")

            all_voters = await db.get_all_voters(game["game_id"])
            if len(all_voters) >= len(players):
                logger.info(
                    f"All players voted in game {game['game_id']}, finishing voting automatically"
                )
                await finish_voting(
                    bot,
                    db,
                    game_manager,
                    game["game_id"],
                    game["chat_id"],
                    timer=timer,
                )

    @dp.callback_query(F.data.startswith("ask_"))
    async def process_ask(callback: CallbackQuery):
        """Process ask question selection"""
        parts = callback.data.split("_")
        game_id = int(parts[1])
        target_id = int(parts[2])

        active_game = await db.get_active_game(callback.message.chat.id)
        if not active_game or active_game["game_id"] != game_id:
            await callback.answer("❌ Game not found.", show_alert=True)
            return

        if active_game["status"] != "playing":
            await callback.answer("❌ Game is not active.", show_alert=True)
            return

        current_player_id = await db.get_current_player(game_id)
        if current_player_id != callback.from_user.id:
            await callback.answer("❌ It's not your turn!", show_alert=True)
            return

        try:
            asker_user = await bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
            asker_name = asker_user.user.first_name
        except:
            asker_name = callback.from_user.username or "Unknown"

        try:
            target_user = await bot.get_chat_member(callback.message.chat.id, target_id)
            target_name = target_user.user.first_name
        except:
            target_name = "Unknown"

        await db.set_target_player(game_id, target_id)

        await bot.send_message(
            callback.message.chat.id,
            f"❓ {asker_name} is asking {target_name} a question!\n\n"
            f"{target_name}, please answer the question. When you're done, use /answer to pass the turn.",
        )

        await callback.message.edit_text(f"✅ You chose to ask {target_name}!")
        await callback.answer()

    @dp.callback_query(F.data.startswith("guess_"))
    async def process_guess(callback: CallbackQuery):
        """Process spy location guess"""
        try:
            parts = callback.data.split("_")
            if len(parts) != 3:
                await callback.answer("❌ Invalid data.", show_alert=True)
                return

            game_id = int(parts[1])
            location_idx = int(parts[2])

            active_game = await db.get_active_game(callback.message.chat.id)
            if not active_game or active_game["game_id"] != game_id:
                await callback.answer("❌ Game not found.", show_alert=True)
                return

            if active_game["status"] != "playing":
                await callback.answer("❌ Game is not active.", show_alert=True)
                return

            spy = await db.get_spy(game_id)
            if not spy or spy["user_id"] != callback.from_user.id:
                await callback.answer("❌ Only the spy can guess!", show_alert=True)
                return

            if location_idx < 0 or location_idx >= len(config.SPYFALL_LOCATIONS):
                await callback.answer("❌ Unknown location.", show_alert=True)
                return

            game = await db.get_game(game_id)
            if not game or game["status"] != "playing":
                await callback.answer("❌ Game is not active.", show_alert=True)
                return

            guessed_location = config.SPYFALL_LOCATIONS[location_idx]
            actual_location = game["location"]

            try:
                user = await bot.get_chat_member(callback.message.chat.id, callback.from_user.id)
                spy_name = user.user.first_name
            except Exception:
                spy_name = callback.from_user.username or "Unknown"

            guess_correct = guessed_location == actual_location

            result_text = (
                f"🎭 Spy {spy_name} decided to guess the location!\n"
                f"🗺️ Guess: {guessed_location}\n"
            )

            if guess_correct:
                result_text += "✅ Correct guess! The spy wins!\n"
            else:
                result_text += "❌ Wrong guess! Civilians win!\n"

            result_text += f"📍 Actual location: {actual_location}"

            await callback.message.edit_text(f"✅ You selected: {guessed_location}")
            await bot.send_message(callback.message.chat.id, result_text)

            await apply_game_results(
                bot,
                db,
                game_manager,
                game_id,
                spy_won=guess_correct,
                civilians_won=not guess_correct,
                timer=timer,
            )

            await callback.answer("✅ Guess processed!")

        except Exception as e:
            logger.error(f"Error processing guess callback: {e}")
            await callback.answer("❌ Error processing guess.", show_alert=True)
