"""Hot-path composite indexes for member/office list queries."""

from app.prior_auth.models import PriorAuthRequest
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from tests.conftest import TEST_SCHEMA


def test_hot_path_indexes_in_metadata():
    index_cols = {
        index.name: list(index.columns.keys()) for index in PriorAuthRequest.__table__.indexes
    }
    assert index_cols["ix_pa_member_created"] == ["member_id", "created_at"]
    assert index_cols["ix_pa_practice_created"] == ["practice_id", "created_at"]


def test_hot_path_indexes_created_on_schema(engine: Engine):
    insp = inspect(engine)
    by_name = {
        idx["name"]: idx["column_names"]
        for idx in insp.get_indexes("prior_auth_requests", schema=TEST_SCHEMA)
    }
    assert by_name["ix_pa_member_created"] == ["member_id", "created_at"]
    assert by_name["ix_pa_practice_created"] == ["practice_id", "created_at"]


def test_hot_path_indexes_migration_parents_prior_auth_head():
    # Import the revision module (present in repo; mutmut may omit alembic/).
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1] / "alembic/versions/9e19ee1c2574_pa_hot_path_indexes.py"
    )
    if not path.is_file():
        return
    spec = importlib.util.spec_from_file_location("pa_hot_path_indexes", path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "9e19ee1c2574"
    assert mod.down_revision == "20261125_prior_auth"
