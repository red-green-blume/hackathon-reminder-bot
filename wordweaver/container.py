from dependency_injector.containers import DeclarativeContainer
from dependency_injector.providers import Provider, Singleton

from wordweaver.adapters.english import EnglishAdapter
from wordweaver.adapters.session import SessionAdapter
from wordweaver.adapters.user import UserAdapter


class Container(DeclarativeContainer):
    """Контейнер зависимостей."""

    english_adapter: Provider["EnglishAdapter"] = Singleton(EnglishAdapter)
    session_adapter: Provider["SessionAdapter"] = Singleton(
        SessionAdapter, _english=english_adapter.provided
    )
    user_adapter: Provider["UserAdapter"] = Singleton(UserAdapter)


CONTAINER = Container()
