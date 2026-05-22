from sqlmodel import create_engine, SQLModel, Session
from src.utils.config import settings


def _create_engine():
    connect_args = {}
    if settings.database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    return create_engine(settings.database_url, echo=False, connect_args=connect_args)


engine = _create_engine()


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Session:
    return Session(engine)
