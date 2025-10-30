import pytest
from src.app import app as flask_app, USERS_BY_EMAIL, USERS_BY_ID, EVENTS

@pytest.fixture(autouse=True)
def clear_state():
    # Clear in-memory DB before each test
    USERS_BY_EMAIL.clear()
    USERS_BY_ID.clear()
    EVENTS.clear()
    flask_app.config["TESTING"] = True

@pytest.fixture
def client():
    with flask_app.test_client() as client:
        yield client