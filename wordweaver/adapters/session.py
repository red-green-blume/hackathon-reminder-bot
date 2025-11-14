from dataclasses import dataclass
from typing import TYPE_CHECKING

from wordweaver.executors.session import SessionExecutor


if TYPE_CHECKING:
    from wordweaver.adapters.english import EnglishAdapter


@dataclass
class SessionAdapter:
    """Адаптер сессий."""

    _english: "EnglishAdapter"

    def __post_init__(self) -> None:
        """Инициализация объекта."""
        self._executors: dict[int, SessionExecutor] = {}

    def has(self, chat_id: int) -> bool:
        """Проверить наличие сессий."""
        return chat_id in self._executors

    def get_or_create(self, chat_id: int) -> "SessionExecutor":
        """Получить исполнителя сессии для чата."""
        if chat_id in self._executors:
            return self._executors[chat_id]

        executor = SessionExecutor(_english=self._english)
        self._executors[chat_id] = executor

        return executor

    def clear(self, chat_id: int) -> None:
        """Очистить сессии для чата."""
        self._executors.pop(chat_id, None)
