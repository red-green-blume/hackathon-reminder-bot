import logging
from aiogram import Bot, F
from aiogram.types import CallbackQuery, PollAnswer
from spyfall.database import Database
from spyfall.handlers.voting import finish_voting
from spyfall.game import GameManager

logger = logging.getLogger(__name__)


def register_callbacks(dp, bot: Bot, db: Database, game_manager: GameManager):
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

            logger.info(
                f"User {user_id} voted for {suspect_id} in game {game['game_id']}"
            )

            all_voters = await db.get_all_voters(game["game_id"])
            if len(all_voters) >= len(players):
                logger.info(
                    f"All players voted in game {game['game_id']}, finishing voting automatically"
                )
                await finish_voting(
                    bot, db, game_manager, game["game_id"], game["chat_id"]
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
            asker_user = await bot.get_chat_member(
                callback.message.chat.id, callback.from_user.id
            )
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
            f"{target_name}, please answer the question. When you're done, use /spy_answer to pass the turn.",
        )

        await callback.message.edit_text(f"✅ You chose to ask {target_name}!")
        await callback.answer()
