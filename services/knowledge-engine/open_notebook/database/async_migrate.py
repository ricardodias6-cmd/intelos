"""
Async migration system for SurrealDB using the official Python client.
Based on patterns from sblpy migration system.
"""

from pathlib import Path
from typing import List

from loguru import logger

from .repository import db_connection, repo_query

MIGRATIONS_DIRECTORY = Path(__file__).resolve().parent / "migrations"


class AsyncMigration:
    """Handles individual migration operations with async support."""

    def __init__(self, sql: str) -> None:
        self.sql = sql

    @classmethod
    def from_file(cls, file_path: str) -> "AsyncMigration":
        """Create a migration from a SurrealQL file."""
        with open(file_path, "r", encoding="utf-8") as file:
            lines = []
            for line in file.read().split("\n"):
                line = line.strip()
                if line and not line.startswith("--"):
                    lines.append(line)
            return cls(" ".join(lines))

    async def run(self, bump: bool = True) -> None:
        """Run the migration and update the recorded schema version."""
        try:
            async with db_connection() as connection:
                await connection.query(self.sql)

            if bump:
                await bump_version()
            else:
                await lower_version()
        except Exception as exc:
            logger.error(f"Migration failed: {exc}")
            raise


def _discover_migration_paths(*, down: bool) -> list[Path]:
    """Return a complete, ordered migration sequence.

    Migration files are discovered from the repository instead of being listed
    manually. This prevents a valid migration file from being silently omitted
    from the runtime migration manager.
    """
    migrations: dict[int, Path] = {}

    for path in MIGRATIONS_DIRECTORY.glob("*.surrealql"):
        stem = path.stem
        is_down = stem.endswith("_down")
        if is_down != down:
            continue

        version_text = stem.removesuffix("_down") if down else stem
        if not version_text.isdigit():
            continue

        version = int(version_text)
        if version in migrations:
            direction = "down" if down else "up"
            raise RuntimeError(f"Duplicate {direction} migration version {version}")
        migrations[version] = path

    if not migrations:
        direction = "down" if down else "up"
        raise RuntimeError(f"No {direction} migrations found")

    latest_version = max(migrations)
    missing = sorted(set(range(1, latest_version + 1)) - migrations.keys())
    if missing:
        direction = "down" if down else "up"
        missing_text = ", ".join(str(version) for version in missing)
        raise RuntimeError(
            f"Incomplete {direction} migration sequence; missing: {missing_text}"
        )

    return [migrations[version] for version in range(1, latest_version + 1)]


def _load_migrations(*, down: bool) -> List[AsyncMigration]:
    return [
        AsyncMigration.from_file(str(path))
        for path in _discover_migration_paths(down=down)
    ]


class AsyncMigrationRunner:
    """Run ordered up and down migrations."""

    def __init__(
        self,
        up_migrations: List[AsyncMigration],
        down_migrations: List[AsyncMigration],
    ) -> None:
        self.up_migrations = up_migrations
        self.down_migrations = down_migrations

    async def run_all(self) -> None:
        current_version = await get_latest_version()
        for index in range(current_version, len(self.up_migrations)):
            logger.info(f"Running migration {index + 1}")
            await self.up_migrations[index].run(bump=True)

    async def run_one_up(self) -> None:
        current_version = await get_latest_version()
        if current_version < len(self.up_migrations):
            logger.info(f"Running migration {current_version + 1}")
            await self.up_migrations[current_version].run(bump=True)

    async def run_one_down(self) -> None:
        current_version = await get_latest_version()
        if current_version > 0:
            logger.info(f"Rolling back migration {current_version}")
            await self.down_migrations[current_version - 1].run(bump=False)


class AsyncMigrationManager:
    """Main migration manager with async support."""

    def __init__(self) -> None:
        self.up_migrations = _load_migrations(down=False)
        self.down_migrations = _load_migrations(down=True)

        if len(self.up_migrations) != len(self.down_migrations):
            raise RuntimeError(
                "Up and down migration sequences must contain the same versions"
            )

        self.runner = AsyncMigrationRunner(
            up_migrations=self.up_migrations,
            down_migrations=self.down_migrations,
        )

    async def get_current_version(self) -> int:
        return await get_latest_version()

    async def ping(self) -> None:
        async with db_connection() as connection:
            await connection.query("RETURN true;")
        await self.get_current_version()

    async def needs_migration(self) -> bool:
        current_version = await self.get_current_version()
        return current_version < len(self.up_migrations)

    async def run_migration_up(self) -> None:
        current_version = await self.get_current_version()
        logger.info(f"Current version before migration: {current_version}")

        if await self.needs_migration():
            try:
                await self.runner.run_all()
                new_version = await self.get_current_version()
                logger.info(f"Migration successful. New version: {new_version}")
            except Exception as exc:
                logger.error(f"Migration failed: {exc}")
                raise
        else:
            logger.info("Database is already at the latest version")


async def get_latest_version() -> int:
    """Get the latest version from the migrations table."""
    try:
        versions = await get_all_versions()
        if not versions:
            return 0
        return max(version["version"] for version in versions)
    except Exception:
        return 0


async def get_all_versions() -> List[dict]:
    """Get all recorded migration versions."""
    try:
        return await repo_query("SELECT * FROM _sbl_migrations ORDER BY version;")
    except Exception:
        return []


async def bump_version() -> None:
    """Record the next migration version."""
    current_version = await get_latest_version()
    new_version = current_version + 1
    await repo_query(
        "CREATE type::thing('_sbl_migrations', $version) "
        "SET version = $version, applied_at = time::now();",
        {"version": new_version},
    )


async def lower_version() -> None:
    """Remove the latest recorded migration version."""
    current_version = await get_latest_version()
    if current_version > 0:
        await repo_query(
            "DELETE type::thing('_sbl_migrations', $version);",
            {"version": current_version},
        )
