import pytest

from raee_reverse.store import Store


@pytest.fixture
def store(tmp_path):
    opened = Store(tmp_path / "ledger")
    yield opened
    opened.verify_integrity()
    opened.close()
