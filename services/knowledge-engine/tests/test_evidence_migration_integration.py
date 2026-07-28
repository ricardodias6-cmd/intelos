"""Integration test for the Evidence Core SurrealDB migration.

This test requires a disposable SurrealDB instance configured through the
standard SURREAL_* environment variables. The dedicated GitHub Actions job
provides that instance.
"""

import pytest

from open_notebook.database.async_migrate import AsyncMigrationManager
from open_notebook.database.repository import repo_query

EVIDENCE_TABLES = {
    "document_version",
    "evidence_block",
    "claim",
    "claim_evidence",
}
EVIDENCE_ANALYZER = "intelos_evidence_analyzer"


async def _database_schema() -> str:
    """Return a stable textual representation of the database schema."""
    return repr(await repo_query("INFO FOR DB;"))


def _assert_evidence_schema_present(schema: str) -> None:
    for table in EVIDENCE_TABLES:
        assert table in schema
    assert EVIDENCE_ANALYZER in schema


def _assert_evidence_schema_absent(schema: str) -> None:
    for table in EVIDENCE_TABLES:
        assert table not in schema
    assert EVIDENCE_ANALYZER not in schema


@pytest.mark.asyncio
async def test_migration_24_up_down_and_reapply_against_real_surrealdb() -> None:
    manager = AsyncMigrationManager()

    assert len(manager.up_migrations) == 24
    assert len(manager.down_migrations) == 24

    await manager.run_migration_up()
    assert await manager.get_current_version() == 24
    assert not await manager.needs_migration()
    _assert_evidence_schema_present(await _database_schema())

    await manager.runner.run_one_down()
    assert await manager.get_current_version() == 23
    assert await manager.needs_migration()
    _assert_evidence_schema_absent(await _database_schema())

    await manager.runner.run_one_up()
    assert await manager.get_current_version() == 24
    assert not await manager.needs_migration()
    _assert_evidence_schema_present(await _database_schema())
