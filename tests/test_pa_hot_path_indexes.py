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


def test_baseline_migration_is_single_head():
    # mutmut's mutants/ tree omits alembic/; skip the file assert there.
    import importlib.util
    from pathlib import Path

    versions = Path(__file__).resolve().parents[1] / "alembic/versions"
    if not versions.is_dir():
        return
    files = sorted(versions.glob("*.py"))
    assert len(files) == 1, files
    spec = importlib.util.spec_from_file_location("baseline_migration", files[0])
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.down_revision is None
    assert "ix_pa_member_created" in files[0].read_text()
    assert "ix_pa_practice_created" in files[0].read_text()
