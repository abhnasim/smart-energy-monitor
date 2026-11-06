"""
Flask application factory.

    create_app()          -> normal start (reads settings from .env)
    create_app(config)    -> tests pass their own settings
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, current_app

from .analytics import CarbonCalculator
from .coach import SustainabilityCoach
from .errors import ErrorHandler
from .models import BuildingModel, db
from .pipeline import build_default_pipeline
from .services import EnergyService

DEMO_BUILDINGS = [
    ("FH Dortmund - Campus Building", "university", 8000, "Dortmund"),
    ("GreenTech Office", "office", 2500, "Dortmund"),
    ("Family Home Schmidt", "home", 140, "Bochum"),
]


def create_app(test_config: dict | None = None) -> Flask:
    load_dotenv()
    app = Flask(__name__)
    default_db = "sqlite:///" + str(Path(app.instance_path) / "energy.db")
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-me"),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", default_db),
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY"),
        OPENAI_MODEL=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        SEED_DEMO_DATA=os.getenv("SEED_DEMO_DATA", "1") == "1",
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    db.init_app(app)
    ErrorHandler(app)

    # One shared pipeline + coach for the whole application
    calculator = CarbonCalculator()
    app.extensions["pipeline"] = build_default_pipeline(calculator)
    app.extensions["coach"] = SustainabilityCoach(app.config["OPENAI_API_KEY"],
                                                  app.config["OPENAI_MODEL"])
    app.extensions["calculator"] = calculator

    from .routes import api, pages
    app.register_blueprint(pages)
    app.register_blueprint(api)

    @app.cli.command("seed")
    def seed_command():
        """flask --app app seed : (re)create the demo buildings."""
        db.drop_all()
        db.create_all()
        seed_demo_data()
        print("Demo data created.")

    with app.app_context():
        db.create_all()
        if app.config["SEED_DEMO_DATA"] and BuildingModel.query.count() == 0:
            seed_demo_data()
    return app


def get_service() -> EnergyService:
    """Create the service for the current request."""
    return EnergyService(current_app.extensions["pipeline"],
                         current_app.extensions["coach"],
                         current_app.extensions["calculator"])


def seed_demo_data() -> None:
    service = get_service()
    for name, building_type, area, city in DEMO_BUILDINGS:
        service.create_building(name, building_type, area, city, history_days=7)
