"""
Error handling for the Energy Monitoring subsystem (Hometask 4).

    EnergySystemError            base class of all our errors (status 500)
    ├── ValidationError          wrong user / device input        (400)
    │   └── InvalidReadingError  a smart-meter reading is invalid (400)
    ├── BuildingNotFoundError    unknown building id              (404)
    ├── MeterNotFoundError       unknown meter id                 (404)
    └── AICoachError             OpenAI not reachable             (503)

ErrorHandler registers one Flask handler for all of them and returns JSON
for /api/... requests and a friendly HTML page for browser requests.
"""

from __future__ import annotations

import logging

from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException


class EnergySystemError(Exception):
    status_code = 500
    error_code = "internal_error"

    def __init__(self, message: str = "Unexpected error", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        data = {"error": self.error_code, "message": self.message}
        if self.details:
            data["details"] = self.details
        return data


class ValidationError(EnergySystemError):
    status_code = 400
    error_code = "validation_error"


class InvalidReadingError(ValidationError):
    error_code = "invalid_reading"


class BuildingNotFoundError(EnergySystemError):
    status_code = 404
    error_code = "building_not_found"

    def __init__(self, building_id: int):
        super().__init__(f"Building {building_id} does not exist",
                         {"building_id": building_id})


class MeterNotFoundError(EnergySystemError):
    status_code = 404
    error_code = "meter_not_found"

    def __init__(self, meter_id: int):
        super().__init__(f"Meter {meter_id} does not exist", {"meter_id": meter_id})


class AICoachError(EnergySystemError):
    status_code = 503
    error_code = "ai_coach_unavailable"


class ErrorHandler:
    """Central error handling for the Flask application."""

    def __init__(self, app=None, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger("energy_app.errors")
        self.error_count = 0
        if app is not None:
            self.init_app(app)

    def init_app(self, app) -> None:
        app.register_error_handler(EnergySystemError, self.handle_system_error)
        app.register_error_handler(HTTPException, self.handle_http_error)
        app.register_error_handler(Exception, self.handle_unexpected_error)
        app.extensions["error_handler"] = self

    @staticmethod
    def wants_json() -> bool:
        return request.path.startswith("/api/")

    def respond(self, status: int, payload: dict):
        self.error_count += 1
        if self.wants_json():
            return jsonify(payload), status
        return render_template("error.html", status=status, payload=payload), status

    def handle_system_error(self, error: EnergySystemError):
        self.logger.warning("%s: %s", error.error_code, error.message)
        return self.respond(error.status_code, error.to_dict())

    def handle_http_error(self, error: HTTPException):
        payload = {"error": (error.name or "error").lower().replace(" ", "_"),
                   "message": error.description}
        return self.respond(error.code or 500, payload)

    def handle_unexpected_error(self, error: Exception):
        self.logger.exception("Unexpected error")
        return self.respond(500, {"error": "internal_error",
                                  "message": "Something went wrong on the server."})
