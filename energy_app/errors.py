"""
Custom exceptions of the Energy Monitoring subsystem.

    EnergySystemError            base class of all our errors (status 500)
    ├── ValidationError          wrong user / device input        (400)
    │   └── InvalidReadingError  a smart-meter reading is invalid (400)
    ├── BuildingNotFoundError    unknown building id              (404)
    ├── MeterNotFoundError       unknown meter id                 (404)
    └── AICoachError             OpenAI not reachable             (503)
"""

from __future__ import annotations


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
