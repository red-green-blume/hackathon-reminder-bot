from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wordweaver.adapters.english import EnglishAdapter
    from wordweaver.entities.player import PlayerEntity


@dataclass
class SessionExecutor:
    """Исполнитель сессий."""

    _english: "EnglishAdapter"

    def __post_init__(self) -> None:
        """Инициализация объекта."""
        self._players: dict[int, "PlayerEntity"] = {}
        self._started_flg: bool = False
        self._iteration: int = 0
        self._letters = self._english.random_letters()
        self._used_words: set[str] = set()

    def is_started(self) -> bool:
        """Проверить, начата игра.  """
        return self._started_flg

    def join(self, player: "PlayerEntity") -> bool:
        """Присоединить игрока, если возможно."""
        if self._started_flg:
            return False

        if player.id in self._players:
            return False

        self._players[player.id] = player
        return True

    def empty(self) -> bool:
        """Проверить сессию на пустоту."""
        return not bool(self._players)

    def has_player(self, user_id: int) -> bool:
        """Проверить, участвует ли пользователь в игре."""
        return user_id in self._players

    def is_eliminated(self, user_id: int) -> bool:
        """Проверить, устранен ли игрок."""
        player = self._players[user_id]
        return player.eliminated_flg

    def who(self) -> "PlayerEntity":
        """Узнать, кто сейчас отвечает."""
        players = [player for player in self._players.values() if not player.eliminated_flg]
        index = self._iteration % len(players)
        player = players[index]
        return player

    def what(self) -> list[str]:
        """Узнать, что отгадывают."""
        return self._letters

    def start(self) -> None:
        """Начать игру."""
        self._started_flg = True

    def eliminate(self, id: int) -> None:
        """Выбить участника."""
        player = self._players[id]
        player.eliminated_flg = True

    def is_alive(self) -> bool:
        """Проверить, есть ли живые."""
        players = [player for player in self._players.values() if not player.eliminated_flg]
        return bool(players)

    def was_used(self, word: str) -> bool:
        """Проверить, было ли использовано слово."""
        return word.lower() in self._used_words

    def guess(self, word: str) -> bool:
        """Проверить слово на правильность."""
        word = word.lower()

        if word not in self._english:
            return False

        if word in self._used_words:
            return False

        wordcount = Counter(word)
        randcount = Counter(self._letters)

        for letter, count in randcount.items():
            if wordcount.get(letter, 0) < count:
                return False

        self._iteration += 1
        self._letters = self._english.random_letters()
        self._used_words.add(word)

        player = self.who()
        player.streak += 1

        return True

    @property
    def iteration(self) -> int:
        """Получить номер итерации."""
        return self._iteration

    @property
    def usernames(self) -> list[str]:
        """List the usernames."""
        return [player.username for player in self._players.values()]
