import pytest_asyncio


@pytest_asyncio.fixture
async def tmp_sqlite(tmp_path):
    """Temp SQLite file path for tests."""
    return tmp_path / "sessions.sqlite"
