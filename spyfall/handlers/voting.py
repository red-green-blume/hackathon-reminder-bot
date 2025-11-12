import logging
from aiogram import Bot
from spyfall.database import Database
from spyfall.game import GameManager
import config

logger = logging.getLogger(__name__)


async def finish_voting(
    bot: Bot, db: Database, game_manager: GameManager, game_id: int, chat_id: int
):
    """Finish voting and show results"""
    try:
        game = await db.get_game(game_id)
        if not game:
            logger.error(f"Game {game_id} not found")
            return False

        votes = await game_manager.get_voting_results(game_id)
        players = await db.get_players(game_id)

        if not votes:
            logger.warning(f"No votes recorded for game {game_id}")
            return False

        max_votes = max(votes.values())
        suspects = [
            suspect_id for suspect_id, count in votes.items() if count == max_votes
        ]

        spy = await db.get_spy(game_id)
        spy_id = spy["user_id"] if spy else None

        result_text = "📊 Voting results:\n\n"
        for player in players:
            vote_count = votes.get(player["user_id"], 0)
            try:
                user = await bot.get_chat_member(chat_id, player["user_id"])
                player_name = user.user.first_name
            except:
                player_name = player["username"] or "Unknown"
            result_text += f"{player_name}: {vote_count} votes\n"

        result_text += "\n"

        if len(suspects) == 1 and suspects[0] == spy_id:
            result_text += "🎉 Victory! Spy found!\n"
            try:
                user = await bot.get_chat_member(chat_id, spy_id)
                spy_name = user.user.first_name
            except:
                spy_name = "Unknown"
            result_text += f"🎭 Spy: {spy_name}\n"
            result_text += f"📍 Location was: {game['location']}"
        elif len(suspects) == 1:
            result_text += "❌ Spy not found!\n"
            try:
                user = await bot.get_chat_member(chat_id, spy_id)
                spy_name = user.user.first_name
            except:
                spy_name = "Unknown"
            result_text += f"🎭 Real spy: {spy_name}\n"
            result_text += f"📍 Location was: {game['location']}"
        else:
            result_text += "🤔 Tie! Multiple suspects.\n"
            if spy_id:
                try:
                    user = await bot.get_chat_member(chat_id, spy_id)
                    spy_name = user.user.first_name
                except:
                    spy_name = "Unknown"
                result_text += f"🎭 Real spy: {spy_name}\n"
                result_text += f"📍 Location was: {game['location']}"

        await bot.send_message(chat_id, result_text)

        spy_won = False
        civilians_won = False

        if len(suspects) == 1:
            if suspects[0] == spy_id:
                civilians_won = True
            else:
                spy_won = True

            for player in players:
                was_spy = player["is_spy"] == 1
                won = False
                rating_change = 0

                if was_spy:
                    won = spy_won
                    if spy_won:
                        rating_change = 20
                    elif civilians_won:
                        rating_change = -15
                else:
                    won = civilians_won
                    if civilians_won:
                        rating_change = 15
                    elif spy_won:
                        rating_change = -10

                used_words_count = await db.get_used_words_count(
                    game_id, player["user_id"]
                )
                word_bonus = 0

                if used_words_count > 0:
                    word_bonus = used_words_count * config.SPYFALL_WORD_PENALTY_POINTS
                else:
                    word_bonus = config.SPYFALL_WORD_PENALTY_POINTS

                await db.update_bonus_points(player["user_id"], word_bonus)

                rating_change += word_bonus

                await db.update_player_stats(
                    player["user_id"],
                    player["username"] or "Unknown",
                    won,
                    was_spy,
                    rating_change,
                )

                try:
                    if used_words_count > 0:
                        await bot.send_message(
                            player["user_id"],
                            f"📚 Word usage summary:\n"
                            f"✅ Words used: {used_words_count}/5\n"
                            f"🎁 Bonus points earned: +{word_bonus}",
                        )
                    else:
                        await bot.send_message(
                            player["user_id"],
                            f"📚 Word usage summary:\n"
                            f"❌ Words used: 0/5\n"
                            f"⚠️ Penalty: {word_bonus} points",
                        )
                except Exception as e:
                    logger.error(
                        f"Error sending word summary to {player['user_id']}: {e}"
                    )

        await game_manager.finish_game(game_id)

        return True

    except Exception as e:
        logger.error(f"Error finishing vote: {e}")
        return False
