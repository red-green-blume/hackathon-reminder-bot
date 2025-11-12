import aiosqlite
import logging
from typing import Optional, List, Dict
from datetime import datetime
import config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = config.DATABASE_PATH):
        self.db_path = db_path

    async def init_db(self):
        """Initialize database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS games (
                    game_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    location TEXT,
                    status TEXT DEFAULT 'waiting',
                    poll_id TEXT,
                    current_player_id INTEGER,
                    target_player_id INTEGER,
                    game_start_time TIMESTAMP,
                    game_duration INTEGER DEFAULT 300,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS players (
                    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    username TEXT,
                    is_spy INTEGER DEFAULT 0,
                    FOREIGN KEY (game_id) REFERENCES games(game_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    voter_id INTEGER NOT NULL,
                    suspect_id INTEGER NOT NULL,
                    FOREIGN KEY (game_id) REFERENCES games(game_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS player_stats (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    games_played INTEGER DEFAULT 0,
                    games_won INTEGER DEFAULT 0,
                    games_lost INTEGER DEFAULT 0,
                    spy_wins INTEGER DEFAULT 0,
                    spy_losses INTEGER DEFAULT 0,
                    civilian_wins INTEGER DEFAULT 0,
                    civilian_losses INTEGER DEFAULT 0,
                    rating INTEGER DEFAULT 1000,
                    bonus_points INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS player_words (
                    word_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    word TEXT NOT NULL,
                    translation TEXT NOT NULL,
                    used INTEGER DEFAULT 0,
                    FOREIGN KEY (game_id) REFERENCES games(game_id)
                )
            """)

            await db.execute("""
                CREATE TABLE IF NOT EXISTS dictionary (
                    word_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    english TEXT NOT NULL UNIQUE,
                    russian TEXT NOT NULL
                )
            """)

            await db.commit()

        await self._migrate_database()

    async def _migrate_database(self):
        """Migrate database: add new columns if they don't exist"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("PRAGMA table_info(games)") as cursor:
                    columns = await cursor.fetchall()
                    column_names = [col[1] for col in columns]

                    if "poll_id" not in column_names:
                        await db.execute("ALTER TABLE games ADD COLUMN poll_id TEXT")
                        logger.info("Added poll_id column to games table")

                    if "current_player_id" not in column_names:
                        await db.execute(
                            "ALTER TABLE games ADD COLUMN current_player_id INTEGER"
                        )
                        logger.info("Added current_player_id column to games table")

                    if "game_start_time" not in column_names:
                        await db.execute(
                            "ALTER TABLE games ADD COLUMN game_start_time TIMESTAMP"
                        )
                        logger.info("Added game_start_time column to games table")

                    if "game_duration" not in column_names:
                        await db.execute(
                            "ALTER TABLE games ADD COLUMN game_duration INTEGER DEFAULT 300"
                        )
                        logger.info("Added game_duration column to games table")

                    if "target_player_id" not in column_names:
                        await db.execute(
                            "ALTER TABLE games ADD COLUMN target_player_id INTEGER"
                        )
                        logger.info("Added target_player_id column to games table")

                async with db.execute("PRAGMA table_info(player_stats)") as cursor:
                    columns = await cursor.fetchall()
                    column_names = [col[1] for col in columns]

                    if "bonus_points" not in column_names:
                        await db.execute(
                            "ALTER TABLE player_stats ADD COLUMN bonus_points INTEGER DEFAULT 0"
                        )
                        logger.info("Added bonus_points column to player_stats table")

                await db.commit()
        except Exception as e:
            logger.error(f"Error migrating database: {e}")

    async def create_game(self, chat_id: int) -> int:
        """Create a new game"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO games (chat_id, status) VALUES (?, ?)",
                (chat_id, "waiting"),
            )
            await db.commit()
            return cursor.lastrowid

    async def get_game(self, game_id: int) -> Optional[Dict]:
        """Get game information"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM games WHERE game_id = ?", (game_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def get_active_game(self, chat_id: int) -> Optional[Dict]:
        """Get active game in chat"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM games WHERE chat_id = ? AND status != 'finished' ORDER BY created_at DESC LIMIT 1",
                (chat_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def start_game(self, game_id: int, location: str, duration: int = 300):
        """Start game with location"""
        from datetime import datetime

        async with aiosqlite.connect(self.db_path) as db:
            start_time = datetime.now().isoformat()
            await db.execute(
                """UPDATE games SET status = 'playing', location = ?, 
                   game_start_time = ?, game_duration = ? WHERE game_id = ?""",
                (location, start_time, duration, game_id),
            )
            await db.commit()

    async def set_current_player(self, game_id: int, player_id: int):
        """Set current player for turn"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE games SET current_player_id = ? WHERE game_id = ?",
                (player_id, game_id),
            )
            await db.commit()

    async def get_current_player(self, game_id: int) -> Optional[int]:
        """Get current player ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT current_player_id FROM games WHERE game_id = ?", (game_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row and row[0] else None

    async def set_target_player(self, game_id: int, player_id: int):
        """Set target player (who was asked)"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE games SET target_player_id = ? WHERE game_id = ?",
                (player_id, game_id),
            )
            await db.commit()

    async def get_target_player(self, game_id: int) -> Optional[int]:
        """Get target player ID"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT target_player_id FROM games WHERE game_id = ?", (game_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row and row[0] else None

    async def clear_target_player(self, game_id: int):
        """Clear target player"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE games SET target_player_id = NULL WHERE game_id = ?", (game_id,)
            )
            await db.commit()

    async def set_poll_id(self, game_id: int, poll_id: str):
        """Set poll ID for game"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE games SET poll_id = ? WHERE game_id = ?", (poll_id, game_id)
            )
            await db.commit()

    async def get_game_by_poll_id(self, poll_id: str) -> Optional[Dict]:
        """Get game by poll ID"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM games WHERE poll_id = ?", (poll_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def finish_game(self, game_id: int):
        """Finish game"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE games SET status = 'finished' WHERE game_id = ?", (game_id,)
            )
            await db.commit()

    async def add_player(
        self, game_id: int, user_id: int, username: str, is_spy: bool = False
    ):
        """Add player to game"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO players (game_id, user_id, username, is_spy) VALUES (?, ?, ?, ?)",
                (game_id, user_id, username, 1 if is_spy else 0),
            )
            await db.commit()

    async def set_spy(self, game_id: int, user_id: int):
        """Set player as spy"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE players SET is_spy = 0 WHERE game_id = ?", (game_id,)
            )

            await db.execute(
                "UPDATE players SET is_spy = 1 WHERE game_id = ? AND user_id = ?",
                (game_id, user_id),
            )
            await db.commit()

    async def get_players(self, game_id: int) -> List[Dict]:
        """Get list of players"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM players WHERE game_id = ? ORDER BY player_id", (game_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def get_spy(self, game_id: int) -> Optional[Dict]:
        """Get spy in game"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM players WHERE game_id = ? AND is_spy = 1", (game_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def is_player_in_game(self, game_id: int, user_id: int) -> bool:
        """Check if player is in game"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM players WHERE game_id = ? AND user_id = ?",
                (game_id, user_id),
            ) as cursor:
                count = await cursor.fetchone()
                return count[0] > 0

    async def add_vote(self, game_id: int, voter_id: int, suspect_id: int):
        """Add vote"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM votes WHERE game_id = ? AND voter_id = ?",
                (game_id, voter_id),
            )

            await db.execute(
                "INSERT INTO votes (game_id, voter_id, suspect_id) VALUES (?, ?, ?)",
                (game_id, voter_id, suspect_id),
            )
            await db.commit()

    async def get_votes(self, game_id: int) -> Dict[int, int]:
        """Get voting results (suspect_id -> vote count)"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT suspect_id, COUNT(*) as votes FROM votes WHERE game_id = ? GROUP BY suspect_id",
                (game_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                return {row[0]: row[1] for row in rows}

    async def get_all_voters(self, game_id: int) -> List[int]:
        """Get list of all voters"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT DISTINCT voter_id FROM votes WHERE game_id = ?", (game_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]

    async def clear_votes(self, game_id: int):
        """Clear votes for game"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM votes WHERE game_id = ?", (game_id,))
            await db.commit()

    async def get_player_stats(self, user_id: int) -> Optional[Dict]:
        """Get player statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM player_stats WHERE user_id = ?", (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def init_player_stats(self, user_id: int, username: str):
        """Initialize player statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT OR IGNORE INTO player_stats 
                   (user_id, username, games_played, games_won, games_lost, 
                    spy_wins, spy_losses, civilian_wins, civilian_losses, rating)
                   VALUES (?, ?, 0, 0, 0, 0, 0, 0, 0, 1000)""",
                (user_id, username),
            )
            await db.commit()

    async def update_player_stats(
        self,
        user_id: int,
        username: str,
        won: bool,
        was_spy: bool,
        rating_change: int = 0,
    ):
        """Update player statistics after game"""
        async with aiosqlite.connect(self.db_path) as db:
            await self.init_player_stats(user_id, username)

            await db.execute(
                "UPDATE player_stats SET username = ? WHERE user_id = ?",
                (username, user_id),
            )

            if won:
                if was_spy:
                    await db.execute(
                        """UPDATE player_stats SET 
                           games_played = games_played + 1,
                           games_won = games_won + 1,
                           spy_wins = spy_wins + 1,
                           rating = rating + ?,
                           updated_at = CURRENT_TIMESTAMP
                           WHERE user_id = ?""",
                        (rating_change, user_id),
                    )
                else:
                    await db.execute(
                        """UPDATE player_stats SET 
                           games_played = games_played + 1,
                           games_won = games_won + 1,
                           civilian_wins = civilian_wins + 1,
                           rating = rating + ?,
                           updated_at = CURRENT_TIMESTAMP
                           WHERE user_id = ?""",
                        (rating_change, user_id),
                    )
            else:
                if was_spy:
                    await db.execute(
                        """UPDATE player_stats SET 
                           games_played = games_played + 1,
                           games_lost = games_lost + 1,
                           spy_losses = spy_losses + 1,
                           rating = rating + ?,
                           updated_at = CURRENT_TIMESTAMP
                           WHERE user_id = ?""",
                        (rating_change, user_id),
                    )
                else:
                    await db.execute(
                        """UPDATE player_stats SET 
                           games_played = games_played + 1,
                           games_lost = games_lost + 1,
                           civilian_losses = civilian_losses + 1,
                           rating = rating + ?,
                           updated_at = CURRENT_TIMESTAMP
                           WHERE user_id = ?""",
                        (rating_change, user_id),
                    )
            await db.commit()

    async def get_leaderboard(self, limit: int = 10) -> List[Dict]:
        """Get top players by rating"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT * FROM player_stats 
                   WHERE games_played > 0 
                   ORDER BY rating DESC, games_won DESC 
                   LIMIT ?""",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def add_player_words(self, game_id: int, user_id: int, words: List[tuple]):
        """Add words to player for a game"""
        async with aiosqlite.connect(self.db_path) as db:
            for word, translation in words:
                await db.execute(
                    "INSERT INTO player_words (game_id, user_id, word, translation, used) VALUES (?, ?, ?, ?, 0)",
                    (game_id, user_id, word, translation),
                )
            await db.commit()

    async def get_player_words(self, game_id: int, user_id: int) -> List[Dict]:
        """Get player's words for a game"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM player_words WHERE game_id = ? AND user_id = ?",
                (game_id, user_id),
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def mark_word_used(self, game_id: int, user_id: int, word: str):
        """Mark word as used"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE player_words SET used = 1 WHERE game_id = ? AND user_id = ? AND word = ?",
                (game_id, user_id, word),
            )
            await db.commit()

    async def get_used_words_count(self, game_id: int, user_id: int) -> int:
        """Get count of used words for a player"""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT COUNT(*) FROM player_words WHERE game_id = ? AND user_id = ? AND used = 1",
                (game_id, user_id),
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0

    async def update_bonus_points(self, user_id: int, bonus_points: int):
        """Update bonus points for a player"""
        async with aiosqlite.connect(self.db_path) as db:
            await self.init_player_stats(user_id, "Unknown")

            await db.execute(
                "UPDATE player_stats SET bonus_points = bonus_points + ? WHERE user_id = ?",
                (bonus_points, user_id),
            )
            await db.commit()
