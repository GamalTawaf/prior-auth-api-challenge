"""Hot-path composite indexes for member/office list queries."""

import inspect as py_inspect

from alembic.config import Config
from alembic.script import ScriptDirectory
from app.prior_auth.models import PriorAuthRequest
from sqlalchemy import inspect
from sqlalchemy.engine import Engine


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
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision("9e19ee1c2574")
    assert rev is not None
    assert rev.down_revision == "ac515227436d"

    upgrade_src = py_inspect.getsource(rev.module.upgrade)
    downgrade_src = py_inspect.getsource(rev.module.downgrade)
    assert "ix_pa_member_created" in upgrade_src
    assert "ix_pa_practice_created" in upgrade_src
    assert "ix_pa_member_created" in downgrade_src
    assert "ix_pa_practice_created" in downgrade_src
