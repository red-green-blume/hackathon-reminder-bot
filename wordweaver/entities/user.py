from pydantic import BaseModel, ConfigDict, NonNegativeInt


class UserEntity(BaseModel):
    """Сущность пользователя."""

    id: int
    record: NonNegativeInt = 0
    games: NonNegativeInt = 0

    model_config = ConfigDict(from_attributes=True, validate_assignment=True, validate_default=True)
