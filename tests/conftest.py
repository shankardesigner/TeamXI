from datetime import datetime
from pathlib import Path

import pytest

from teamxi import XISelector

FIXTURE_ROOT = Path(__file__).parent / "fixtures"

# Pinned so the rolling form window never slides off the fixture data.
AS_OF = datetime(2025, 10, 31)


@pytest.fixture(scope="session")
def selector() -> XISelector:
    return XISelector(root_dir=FIXTURE_ROOT)


@pytest.fixture(scope="session")
def client(selector):
    from fastapi.testclient import TestClient

    import server

    server.app.dependency_overrides[server.get_selector] = lambda: selector
    with TestClient(server.app) as c:
        yield c
    server.app.dependency_overrides.clear()
