import random
from typing import Dict, Optional
from spyfall.database import Database
import config


class GameManager:
    def __init__(self, db: Database):
        self.db = db

    async def create_game(self, chat_id: int) -> int:
        """Create a new game"""
        return await self.db.create_game(chat_id)

    async def join_game(self, game_id: int, user_id: int, username: str) -> bool:
        """Join game"""

        if await self.db.is_player_in_game(game_id, user_id):
            return False

        await self.db.add_player(game_id, user_id, username)
        return True

    async def start_game(self, game_id: int, duration: int = 300) -> Optional[str]:
        """Start game: choose location and spy"""
        players = await self.db.get_players(game_id)

        if len(players) < 3:
            return None

        location = random.choice(config.SPYFALL_LOCATIONS)

        spy = random.choice(players)
        await self.db.set_spy(game_id, spy["user_id"])

        starting_player = random.choice(players)
        await self.db.set_current_player(game_id, starting_player["user_id"])

        await self.db.start_game(game_id, location, duration)

        return location

    async def get_game_info(self, game_id: int) -> Optional[Dict]:
        """Get game information"""
        game = await self.db.get_game(game_id)
        if not game:
            return None

        players = await self.db.get_players(game_id)
        spy = await self.db.get_spy(game_id)

        return {"game": game, "players": players, "spy": spy}

    async def get_location_for_player(
        self, game_id: int, user_id: int
    ) -> Optional[str]:
        """Get location for player (or None if they are spy)"""
        game = await self.db.get_game(game_id)
        if not game or game["status"] != "playing":
            return None

        spy = await self.db.get_spy(game_id)
        if spy and spy["user_id"] == user_id:
            return None

        return game["location"]

    async def vote(self, game_id: int, voter_id: int, suspect_id: int):
        """Vote for suspect"""
        await self.db.add_vote(game_id, voter_id, suspect_id)

    async def get_voting_results(self, game_id: int) -> Dict[int, int]:
        """Get voting results"""
        return await self.db.get_votes(game_id)

    async def finish_game(self, game_id: int):
        """Finish game"""
        await self.db.finish_game(game_id)
        await self.db.clear_votes(game_id)
