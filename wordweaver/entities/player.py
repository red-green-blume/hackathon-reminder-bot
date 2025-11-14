from pydantic import BaseModel, ConfigDict, NonNegativeInt


class PlayerEntity(BaseModel):
    """Сущность участника игры."""

    id: int
    username: str
    streak: NonNegativeInt = 0
    eliminated_flg: bool = False

    model_config = ConfigDict(from_attributes=True, validate_assignment=True, validate_default=True)
