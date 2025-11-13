
from typing import Dict

DEFAULT_MODE = "standard"

chat_modes: Dict[int, str] = {}


def set_chat_mode(chat_id: int, mode: str):
    chat_modes[chat_id] = mode


def get_chat_mode(chat_id: int) -> str:
    return chat_modes.get(chat_id, DEFAULT_MODE)
