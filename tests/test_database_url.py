"""Database URL normalization regression tests."""

from pathlib import Path

from sqlalchemy.engine import make_url

from shogun.config import PROJECT_ROOT, normalize_database_url


def test_relative_sqlite_database_is_anchored_to_installation() -> None:
    normalized = normalize_database_url("sqlite+aiosqlite:///./data/shogun.db")

    assert Path(make_url(normalized).database) == PROJECT_ROOT / "data" / "shogun.db"


def test_absolute_sqlite_database_is_preserved(tmp_path: Path) -> None:
    database = (tmp_path / "custom.db").resolve()
    supplied = f"sqlite+aiosqlite:///{database.as_posix()}"

    assert make_url(normalize_database_url(supplied)).database == database.as_posix()


def test_memory_and_non_sqlite_urls_are_preserved() -> None:
    memory = "sqlite+aiosqlite:///:memory:"
    postgres = "postgresql+asyncpg://shogun:secret@example.invalid/shogun"

    assert normalize_database_url(memory) == memory
    assert normalize_database_url(postgres) == postgres
