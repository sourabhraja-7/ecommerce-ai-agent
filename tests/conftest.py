import pytest

from src.config import settings
from src.services.database import init_db


@pytest.fixture(scope="session", autouse=True)
def _isolated_db(tmp_path_factory):
    """Point every test at a fresh, throwaway SQLite database."""
    settings.db_path = str(tmp_path_factory.mktemp("db") / "test.db")
    init_db(reset=True)
