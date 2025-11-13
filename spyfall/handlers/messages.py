import logging
import re
from aiogram import Bot, F
from aiogram.types import Message
from spyfall.database import Database
import config

logger = logging.getLogger(__name__)


def register_message_handlers(dp, bot: Bot, db: Database):
    """Register message handlers for word tracking"""

    @dp.message(F.chat.type.in_(["group", "supergroup"]))
    async def track_word_usage(message: Message):
        """Track word usage in game messages"""

        if message.text and message.text.startswith("/"):
            return

        active_game = await db.get_active_game(message.chat.id)
        if not active_game or active_game["status"] != "playing":
            return

        players = await db.get_players(active_game["game_id"])
        player_ids = [p["user_id"] for p in players]
        if message.from_user.id not in player_ids:
            return

        curr_player = await db.get_current_player(active_game["game_id"])
        target_player = await db.get_target_player(active_game["game_id"])

        if message.from_user.id not in [curr_player, target_player]:
            return

        player_words = await db.get_player_words(
            active_game["game_id"], message.from_user.id
        )

        if not player_words:
            return

        if not message.text:
            return

        text_lower = message.text.lower()

        for word_data in player_words:
            if word_data["used"] == 1:
                continue

            word = word_data["word"].lower()
            translation = word_data["translation"]

            pattern = r"\b" + re.escape(word) + r"\b"
            if re.search(pattern, text_lower):
                await db.mark_word_used(
                    active_game["game_id"], message.from_user.id, word
                )

                try:
                    await bot.send_message(
                        message.chat.id,
                        f"✅ Great! You used the word '{word_data['word']}'\n"
                        f"📖 Translation: {translation}\n"
                        f"🎁 You earned {config.SPYFALL_WORD_BONUS_POINTS} bonus points!",
                    )
                except Exception as e:
                    logger.error(
                        f"Error sending word notification to {message.from_user.id}: {e}"
                    )
