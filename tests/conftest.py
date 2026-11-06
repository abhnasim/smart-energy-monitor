"""Shared pytest fixtures: a fresh app with an in-memory database per test."""

import pytest

from energy_app.models import db
from energy_app.webapp import create_app, get_service


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite://",     # in-memory database
        "SEED_DEMO_DATA": False,
        "OPENAI_API_KEY": None,
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def service(app):
    return get_service()


@pytest.fixture
def building(service):
    """An office building with 5 meters and 1 day of simulated readings."""
    return service.create_building("Test Office", "office", 1000, "Dortmund", history_days=1)
