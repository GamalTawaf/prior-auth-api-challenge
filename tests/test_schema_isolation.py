"""Dev `public` schema must stay untouched by the pytest engine fixture."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from tests.conftest import DEV_SCHEMA, TEST_SCHEMA


def test_pytest_uses_test_prefixed_schema():
    assert TEST_SCHEMA.startswith("test_")
    assert TEST_SCHEMA.removeprefix("test_") == DEV_SCHEMA
    assert TEST_SCHEMA == "test_public"


def test_engine_search_path_is_test_schema(engine: Engine):
    with engine.connect() as conn:
        path = conn.execute(text("SHOW search_path")).scalar_one()
    parts = {p.strip().strip('"') for p in path.split(",")}
    assert TEST_SCHEMA in parts


def test_orm_tables_created_in_test_schema(engine: Engine):
    from app.db import Base

    assert Base.metadata.schema == TEST_SCHEMA
    with engine.connect() as conn:
        schemas = (
            conn.execute(
                text(
                    "SELECT table_schema FROM information_schema.tables "
                    "WHERE table_name = 'users' ORDER BY table_schema"
                )
            )
            .scalars()
            .all()
        )
    assert TEST_SCHEMA in schemas


def test_public_schema_still_exists(engine: Engine):
    with engine.connect() as conn:
        name = conn.execute(
            text("SELECT nspname FROM pg_namespace WHERE nspname = :name"),
            {"name": DEV_SCHEMA},
        ).scalar_one()
    assert name == DEV_SCHEMA
