from dataclasses import dataclass
from os import PathLike

import aiosqlite

from utils.basedir import BASEDIR
from wordweaver.entities.user import UserEntity


@dataclass
class UserAdapter:
    """Адаптер пользователей."""

    path: PathLike = BASEDIR / "wordweaver.db"

    def __post_init__(self) -> None:
        """Инициализация объекта."""
        self._migrated_flg = False

    async def migrate(self) -> None:
        """Накатить миграцию."""
        query = """
            CREATE TABLE IF NOT EXISTS user
            (
            id     INTEGER PRIMARY KEY,
            record INTEGER NOT NULL,
            games  INTEGER NOT NULL
            )
        """
        if not self._migrated_flg:
            self._migrated_flg = True
            async with aiosqlite.connect(self.path) as connection:
                await connection.execute(query)
                await connection.commit()

    async def get(self, id: int) -> "UserEntity":
        """Получить пользователя."""
        select_query = """
            SELECT record, games
            FROM user
            WHERE id = ?
        """
        insert_query = """
            INSERT INTO user (id, record, games)
            VALUES (?, ?, ?)
        """
        async with aiosqlite.connect(self.path) as connection:
            async with connection.execute(select_query, (id,)) as cursor:
                if scalars := await cursor.fetchone():
                    record, games = scalars
                    return UserEntity(id=id, record=record, games=games)

            user = UserEntity(id=id, record=0, games=0)
            values = (user.id, user.record, user.games)

            await connection.execute(insert_query, values)
            await connection.commit()

        return user

    async def progress(self, id: int, record: int) -> None:
        """Обновить прогресс пользователя."""
        insert_query = """
            INSERT OR IGNORE INTO user (id, record, games)
            VALUES (?, ?, 1)
        """
        update_query = """
            UPDATE user
            SET record = MAX(record, ?), games = games + 1
            WHERE id = ?
        """
        async with aiosqlite.connect(self.path) as connection:
            cursor = await connection.execute(update_query, (record, id))

            if not cursor.rowcount:
                await connection.execute(insert_query, (id, record))

            await connection.commit()
