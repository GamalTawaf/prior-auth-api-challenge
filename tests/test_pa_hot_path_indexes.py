"""Hot-path composite indexes for member/office list queries."""

from pathlib import Path

from app.prior_auth.models import PriorAuthRequest
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

_REPO_ROOT = Path(__file__).resolve().parents[1]
_MIGRATION = _REPO_ROOT / "alembic/versions/9e19ee1c2574_pa_hot_path_indexes.py"


def test_hot_path_indexes_in_metadata():
    index_cols = {
        index.name: list(index.columns.keys()) for index in PriorAuthRequest.__table__.indexes
    }
    assert index_cols["ix_pa_member_created"] == ["member_id", "created_at"]
    assert index_cols["ix_pa_practice_created"] == ["practice_id", "created_at"]


def test_hot_path_indexes_created_on_schema(engine: Engine):
    insp = inspect(engine)
    by_name = {idx["name"]: idx["column_names"] for idx in insp.get_indexes("prior_auth_requests")}
    assert by_name["ix_pa_member_created"] == ["member_id", "created_at"]
    assert by_name["ix_pa_practice_created"] == ["practice_id", "created_at"]


def test_hot_path_indexes_migration_revision():
    # Read the file directly — Alembic Config("alembic.ini") breaks under mutmut's
    # mutants/ working directory copy.
    src = _MIGRATION.read_text()
    assert 'revision: str = "9e19ee1c2574"' in src
    assert 'down_revision: Union[str, None] = "ac515227436d"' in src
    assert "ix_pa_member_created" in src
    assert "ix_pa_practice_created" in src
    assert src.index("def upgrade") < src.index("def downgrade")
    downgrade = src[src.index("def downgrade") :]
    assert "ix_pa_member_created" in downgrade
    assert "ix_pa_practice_created" in downgrade
