import aiosqlite
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)


class Dictionary:
    def __init__(self, db_path: str, file_path: str = "slovarik.txt"):
        self.db_path = db_path
        self.file_path = file_path

    async def init_dictionary(self):
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM dictionary") as cursor:
                count = (await cursor.fetchone())[0]

            if count > 0:
                logger.info("Dictionary already loaded into DB (%d words)", count)
                return

            try:
                async with db.execute("BEGIN"):
                    with open(self.file_path, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            parts = line.split(" ", 1)
                            if len(parts) != 2:
                                continue

                            english = parts[0].strip().lower()
                            russian = parts[1].strip()
                            await db.execute(
                                "INSERT OR IGNORE INTO dictionary (english, russian) VALUES (?, ?)",
                                (english, russian),
                            )
                    await db.commit()

                logger.info("Loaded dictionary from file: %s", self.file_path)
            except FileNotFoundError:
                logger.warning("Dictionary file not found: %s", self.file_path)

    async def get_random_words(self, count: int = 5) -> List[Tuple[str, str]]:
        """Get random words from dictionary table"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT english, russian FROM dictionary ORDER BY RANDOM() LIMIT ?",
                (count,),
            ) as cursor:
                rows = await cursor.fetchall()
                return [(row["english"], row["russian"]) for row in rows]
