import asyncio

from asyncio import Task
from collections.abc import Coroutine
from datetime import timedelta
from typing import TYPE_CHECKING, Any, ClassVar, Final

from aiogram import F, Router
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from filter import ModeFilter
from wordweaver.container import CONTAINER
from wordweaver.entities.player import PlayerEntity


if TYPE_CHECKING:
    from wordweaver.executors.session import SessionExecutor


MODE: Final[int] = "wordweaver"

LOBBY_TIMEOUT: Final[timedelta] = timedelta(seconds=30.0)
ROUND_TIMEOUT: Final[timedelta] = timedelta(seconds=15.0)


router = Router()


class Background:
    """Задний фон."""

    _tasks: ClassVar[set[Task]] = set()

    @classmethod
    def create_task(cls, coroutine: Coroutine[Any, Any, Any]) -> None:
        """Добавить задачу."""
        task = asyncio.create_task(coroutine)
        cls._tasks.add(task)
        task.add_done_callback(cls._tasks.discard)

    @classmethod
    async def start(
        cls,
        executor: "SessionExecutor",
        message: "Message",
        *,
        delay: timedelta = timedelta(),
    ) -> None:
        """Начать игру."""
        await asyncio.sleep(delay.total_seconds())
        executor.start()
        await cls.notify(executor, message)

    @classmethod
    async def notify(cls, executor: "SessionExecutor", message: "Message") -> None:
        """Оповестить про новый раунд."""
        coroutine = cls.timer(executor, executor.iteration, message)
        cls.create_task(coroutine)

        player = executor.who()
        letters = ", ".join(repr(letter) for letter in executor.what())

        lines = [
            f"🕹 <b>Player</b>: @{player.username}",
            f"📍 <b>Letters</b>: {letters}",
        ]

        text = "\n".join(lines)
        await message.answer(text, parse_mode=ParseMode.HTML)

    @classmethod
    async def timer(cls, executor: "SessionExecutor", iteration: int, message: "Message") -> None:
        """Установить таймер на раунд."""
        session_adapter = CONTAINER.session_adapter()
        user_adapter = CONTAINER.user_adapter()

        await asyncio.sleep(ROUND_TIMEOUT.total_seconds())

        if executor.iteration != iteration:
            return

        player = executor.who()
        executor.eliminate(player.id)

        await user_adapter.progress(player.id, player.streak)

        text = f"☠ You time is up, @{player.username}!"
        await message.answer(text)

        if executor.is_alive():
            await cls.notify(executor, message)
            return

        if len(executor.usernames) > 1:
            text = "✔ <b>The Game is Over</b>"
            await message.answer(text, parse_mode=ParseMode.HTML)

        session_adapter.clear(message.chat.id)


@router.startup.register
async def startup() -> None:
    """Начало жизненного цикла."""
    user_adapter = CONTAINER.user_adapter()

    await user_adapter.migrate()


@router.message(ModeFilter(MODE), Command("me", ignore_case=True))
async def me(message: "Message") -> None:
    """Отобразить статистику пользователя."""
    user_adapter = CONTAINER.user_adapter()

    if message.from_user:
        user = await user_adapter.get(message.from_user.id)

        lines = [
            "```markdown",
            "+ ═══════════════════════ +",
            "║      📊 STATISTICS      ║",
            "+ ─────────────────────── +",
            f"║ 🔥 Record Streak: {user.record:>5} ║",
            f"║ 🎮 Games Played:  {user.games:>5} ║",
            "+ ═══════════════════════ +",
            "```",
        ]

        text = "\n".join(lines)
        await message.reply(text, parse_mode=ParseMode.MARKDOWN)


@router.message(ModeFilter(MODE), Command("help", ignore_case=True))
async def help(message: "Message") -> None:
    """Отобразить подсказку по игре."""
    instruction = (
        "- You receive a set of random letters. Your task is to find and submit *any word* that "
        "contains *ALL* of the given letters. The challenge continues indefinitely, but you have "
        "only 15 seconds for each word combination."
    )

    lines = [
        "📍 *Word Weaver* - Can You Remember?",
        "",
        "📃 *How to Play*",
        "",
        instruction,
        "",
        "💡 *Examples*",
        "",
        "-> Letters: 'a', 't', 'c', 'b'",
        "-> OK: 'bacteria'",
        "-> NO: 'cat', 'bank', 'bakery'",
        "",
        "🕹️ *Commands*",
        "",
        "/help - Show this guide",
        "/me - Show the statistics",
        "/start - Start the game",
        "/join - Join the session",
    ]

    text = "\n".join(lines)
    await message.answer(text, parse_mode=ParseMode.MARKDOWN)


@router.message(ModeFilter(MODE), Command("start", ignore_case=True))
async def start(message: "Message") -> None:
    """Начать игру."""
    session_adapter = CONTAINER.session_adapter()

    if not message.from_user:
        return

    executor = session_adapter.get_or_create(message.chat.id)
    if executor.is_started():
        text = "❌ The game has already started. Please, wait..."
        await message.reply(text)
        return

    username = str(message.from_user.username)
    if username in executor.usernames:
        return

    if not executor.empty():
        text = "🔜 The session already exists. Use /join"
        await message.reply(text)
        return

    player = PlayerEntity(id=message.from_user.id, username=username)
    executor.join(player)

    if message.chat.type == ChatType.PRIVATE:
        await Background.start(executor, message)
        return

    lines = [
        "📋 <b>+1 Participant</b> (/join)",
        "",
        f"-> @{player.username}",
        "",
        f"PS We'll start in <b>{int(LOBBY_TIMEOUT.total_seconds())}</b> seconds!",
    ]

    text = "\n".join(lines)
    await message.reply(text, parse_mode=ParseMode.HTML)

    coroutine = Background.start(executor, message, delay=LOBBY_TIMEOUT)
    Background.create_task(coroutine)


@router.message(ModeFilter(MODE), Command("join", ignore_case=True))
async def join(message: "Message") -> None:
    """Присоединиться к игре."""
    session_adapter = CONTAINER.session_adapter()

    if not message.from_user:
        return

    if message.chat.type == ChatType.PRIVATE:
        text = "❌ It's not a group chat. Let's invite some friends!"
        await message.reply(text)
        return

    executor = session_adapter.get_or_create(message.chat.id)
    if executor.is_started():
        text = "❌ The game has already started. Please, wait..."
        await message.reply(text)
        return

    if executor.empty():
        text = "🔜 There is no active session. Use /start"
        await message.reply(text)
        return

    player = PlayerEntity(id=message.from_user.id, username=str(message.from_user.username))
    if not executor.join(player):
        return

    lines = ["📋 <b>+1 Participant</b> (/join)", ""]
    for username in executor.usernames:
        lines.append(f"-> @{username}")

    text = "\n".join(lines)
    await message.reply(text, parse_mode=ParseMode.HTML)


@router.message(ModeFilter(MODE), F.text.startswith("/"))
async def unknown_command(message: Message):
    text = "❌ I don't know this command... (/help)"
    await message.reply(text)


@router.message(ModeFilter(MODE), F.text)
async def handle(message: "Message") -> None:
    """Обработать текстовое сообщение."""
    english = CONTAINER.english_adapter()
    session_adapter = CONTAINER.session_adapter()

    if not message.from_user:
        return

    if not session_adapter.has(message.chat.id):
        return

    executor = session_adapter.get_or_create(message.chat.id)
    if not executor.is_started():
        text = "⏳ We'll start soon! Please, wait a bit"
        await message.reply(text)
        return

    if not executor.has_player(message.from_user.id):
        text = "❌ You are not participating in the current session. Please, wait!"
        await message.reply(text)
        return

    if executor.is_eliminated(message.from_user.id):
        text = "☠ You've already been eliminated. Wait for the next session..."
        await message.reply(text)
        return

    player = executor.who()
    if player.id != message.from_user.id:
        text = "⏳ It's not your turn. Please, wait a bit"
        await message.reply(text)
        return

    if not (word := str(message.text).strip()):
        text = "🚫 Why is your message empty?.."
        await message.reply(text)
        return

    if len(word.split()) > 1:
        text = "🚫 Only words... no sentences..."
        await message.reply(text)
        return

    if word not in english:
        text = "🙅‍♂️ This is definitely not an English word!"
        await message.reply(text)
        return

    if executor.was_used(word):
        text = "🙅‍♂️ This word has already been used! Try another one!"
        await message.reply(text)
        return

    if not executor.guess(word):
        text = "🙅‍♂️ Nope! This word doesn't fit"
        await message.reply(text)
        return

    await Background.notify(executor, message)
