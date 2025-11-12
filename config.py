import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

SPYFALL_DATABASE_PATH = "spyfall/spy_game.db"
SPYFALL_GAME_DURATION = 300
SPYFALL_DICTIONARY_PATH = "spyfall/slovarik.txt"
SPYFALL_WORDS_PER_PLAYER = 5
SPYFALL_WORD_BONUS_POINTS = 5
SPYFALL_WORD_PENALTY_POINTS = -10
SPYFALL_LOCATIONS = [
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
