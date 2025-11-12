
from typing import Dict, Optional

chat_modes: Dict[int, str] = {}

def set_chat_mode(chat_id: int, mode: str):
    chat_modes[chat_id] = mode

def get_chat_mode(chat_id: int) -> Optional[str]:
    return chat_modes.get(chat_id)
