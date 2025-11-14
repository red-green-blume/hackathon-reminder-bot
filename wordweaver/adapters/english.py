from dataclasses import dataclass
from os import PathLike
from random import sample, randint
from typing import ClassVar

from utils.basedir import BASEDIR


@dataclass
class EnglishAdapter:
    """Английский язык."""

    path: PathLike = BASEDIR / "data" / "english.txt"

    _min_letters: ClassVar[int] = 2
    _max_letters: ClassVar[int] = 4

    def __post_init__(self) -> None:
        """Инициализация объекта."""
        self._words: set[str] = set()
        with self.path.open() as file:
            for line in file:
                if word := line.strip():
                    self._words.add(word.lower())

    def __contains__(self, word: str) -> bool:
        """Проверить наличие слова."""
        return word.lower() in self._words

    def random_word(self) -> str:
        """Случайное слово."""
        target = randint(0, len(self._words) - 1)
        for index, word in enumerate(self._words):
            if index == target:
                return word

        detail = "This code must be unreachable"
        raise RuntimeError(detail)

    def random_letters(self) -> list[str]:
        """Случайные буквы."""
        word = self.random_word()
        count = randint(self._min_letters, self._max_letters)
        count = min(len(word), count)
        return sample(word, count)
