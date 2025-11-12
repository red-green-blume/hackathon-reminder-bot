import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_PATH = "spy_game.db"
GAME_DURATION = 300
DICTIONARY_PATH = "slovarik.txt"
WORDS_PER_PLAYER = 5
WORD_BONUS_POINTS = 5
WORD_PENALTY_POINTS = -10


LOCATIONS = [
    "Beach (Пляж)",
    "Hospital (Больница)",
    "School (Школа)",
    "Restaurant (Ресторан)",
    "Airport (Аэропорт)",
    "Bank (Банк)",
    "Cinema (Кинотеатр)",
    "Office (Офис)",
    "Hotel (Отель)",
    "Supermarket (Супермаркет)",
    "Library (Библиотека)",
    "Gym (Спортзал)",
    "Park (Парк)",
    "Museum (Музей)",
    "Cafe (Кафе)",
    "Train Station (Железнодорожный вокзал)",
    "Theater (Театр)",
    "Circus (Цирк)",
    "Zoo (Зоопарк)",
    "Police Station (Полицейский участок)",
]
