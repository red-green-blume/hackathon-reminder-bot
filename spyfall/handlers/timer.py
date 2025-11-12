import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import Bot
from spyfall.database import Database

logger = logging.getLogger(__name__)


class GameTimer:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self.running_timers = {}

    async def start_timer(self, game_id: int, chat_id: int, duration: int):
        """Start timer for a game"""
        if game_id in self.running_timers:
            return

        task = asyncio.create_task(self._timer_loop(game_id, chat_id, duration))
        self.running_timers[game_id] = task

    async def stop_timer(self, game_id: int):
        """Stop timer for a game"""
        if game_id in self.running_timers:
            self.running_timers[game_id].cancel()
            del self.running_timers[game_id]

    async def _timer_loop(self, game_id: int, chat_id: int, duration: int):
        """Timer loop that sends updates every minute"""
        try:
            game = await self.db.get_game(game_id)
            if not game or not game.get("game_start_time"):
                return

            start_time_str = game["game_start_time"]
            if isinstance(start_time_str, str):
                try:
                    start_time = datetime.fromisoformat(
                        start_time_str.replace("Z", "+00:00")
                    )
                except:
                    try:
                        start_time = datetime.strptime(
                            start_time_str, "%Y-%m-%d %H:%M:%S.%f"
                        )
                    except:
                        start_time = datetime.strptime(
                            start_time_str, "%Y-%m-%d %H:%M:%S"
                        )
            else:
                start_time = start_time_str

            end_time = start_time + timedelta(seconds=duration)

            while True:
                await asyncio.sleep(60)

                game = await self.db.get_game(game_id)
                if not game or game["status"] != "playing":
                    await self.stop_timer(game_id)
                    return

                now = datetime.now()
                remaining = end_time - now

                if remaining.total_seconds() <= 0:
                    await self.bot.send_message(
                        chat_id,
                        "⏰ Time's up! The game has ended.\n"
                        "Use /vote to start voting for the spy.",
                    )
                    await self.stop_timer(game_id)
                    return

                minutes = int(remaining.total_seconds() // 60)
                seconds = int(remaining.total_seconds() % 60)

                await self.bot.send_message(
                    chat_id, f"⏰ Time remaining: {minutes} minutes {seconds} seconds"
                )

        except asyncio.CancelledError:
            logger.info(f"Timer for game {game_id} was cancelled")
        except Exception as e:
            logger.error(f"Error in timer loop for game {game_id}: {e}")
            await self.stop_timer(game_id)
