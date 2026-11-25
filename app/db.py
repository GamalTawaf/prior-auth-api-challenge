from collections.abc import Generator

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Application data schema (not Postgres' default `public`).
APP_SCHEMA = "prior_auth"

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"options": f"-csearch_path={APP_SCHEMA}"},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@event.listens_for(engine, "checkout")
def _set_app_search_path(dbapi_conn, _connection_record, _connection_proxy) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute(f"SET search_path TO {APP_SCHEMA}")
    cursor.close()


class Base(DeclarativeBase):
    metadata = MetaData(schema=APP_SCHEMA)


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
