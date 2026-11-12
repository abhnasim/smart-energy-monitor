"""
Application service: the glue between web routes, database, pipeline and AI.

Routes stay thin - they call EnergyService, which
    * validates input with the domain classes,
    * pushes readings through the stream pipeline,
    * stores the results in the database,
    * builds dashboard summaries and asks the AI coach.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from .analytics import CarbonCalculator, EnergyAnalyzer, SustainabilityScorer
from .coach import SustainabilityCoach
from .domain import Building, EnergyReading
from .errors import (AICoachError, BuildingNotFoundError, InvalidReadingError,
                     MeterNotFoundError, ValidationError)
from .models import AdviceModel, BuildingModel, MeterModel, ReadingModel, db
from .pipeline import LoadBalanceTracker, Pipeline
from .simulator import simulate_readings

logger = logging.getLogger(__name__)


class EnergyService:

    def __init__(self, pipeline: Pipeline, coach: SustainabilityCoach,
                 calculator: CarbonCalculator | None = None) -> None:
        self.pipeline = pipeline
        self.coach = coach
        self.analyzer = EnergyAnalyzer(calculator or CarbonCalculator())
        self.scorer = SustainabilityScorer()

    # ---- buildings --------------------------------------------------------
    def list_buildings(self) -> list[BuildingModel]:
        return BuildingModel.query.order_by(BuildingModel.id).all()

    def get_building(self, building_id: int) -> BuildingModel:
        building = db.session.get(BuildingModel, building_id)
        if building is None:
            raise BuildingNotFoundError(building_id)
        return building

    def create_building(self, name: str, building_type: str, area_m2,
                        city: str = "Dortmund", history_days: int = 7) -> BuildingModel:
        try:
            domain = Building(name, building_type, area_m2, city)   # validation
        except (ValueError, TypeError) as error:
            raise ValidationError(str(error)) from error

        row = BuildingModel(name=domain.name, building_type=domain.building_type.value,
                            area_m2=domain.area_m2, city=domain.city)
        for meter in domain.configure_default_meters():
            row.meters.append(MeterModel(label=meter.label, meter_type=meter.meter_type.value,
                                         rated_power_kw=meter.rated_power_kw))
        db.session.add(row)
        db.session.commit()
        if history_days:
            self.simulate_history(row.id, days=history_days)
        return row

    def delete_building(self, building_id: int) -> None:
        db.session.delete(self.get_building(building_id))
        db.session.commit()

    # ---- ingestion (stream pipeline -> database) --------------------------
    def ingest(self, readings) -> dict:
        """Run readings through the pipeline and store the ones that pass."""
        received_before = self.pipeline.received
        stored = 0
        for reading in self.pipeline(readings):
            db.session.add(ReadingModel.from_domain(reading))
            stored += 1
        db.session.commit()
        received = self.pipeline.received - received_before
        return {"received": received, "stored": stored, "dropped": received - stored}

    def ingest_json(self, payload) -> dict:
        """Ingest readings sent by an IoT device as JSON (one object or a list)."""
        items = payload if isinstance(payload, list) else [payload]
        if not items or not all(isinstance(item, dict) for item in items):
            raise InvalidReadingError("Body must be a JSON object or a list of objects")
        readings = []
        for index, item in enumerate(items):
            try:
                meter = db.session.get(MeterModel, int(item.get("meter_id", -1)))
            except (TypeError, ValueError):
                raise InvalidReadingError("meter_id must be an integer",
                                          {"index": index}) from None
            if meter is None:
                raise MeterNotFoundError(item.get("meter_id"))
            data = {**item, "meter_type": meter.meter_type, "building_id": meter.building_id,
                    "is_meter_active": item.get("is_meter_active", meter.is_active)}
            try:
                readings.append(EnergyReading.from_dict(data))
            except (ValueError, TypeError) as error:
                raise InvalidReadingError(str(error), {"index": index}) from error
        return self.ingest(readings)

    def simulate_history(self, building_id: int, days: int = 7) -> dict:
        """Generate `days` of hourly readings ending now (demo data)."""
        building = self.get_building(building_id).to_domain()
        end = datetime.now().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=days) + timedelta(hours=1)
        return self.ingest(simulate_readings(building.meters, start, 60, ticks=days * 24))

    def live_tick(self, building_id: int) -> dict:
        """One real-time step: every meter sends a 1-minute reading now."""
        building = self.get_building(building_id).to_domain()
        now = datetime.now().replace(microsecond=0)
        readings = list(simulate_readings(building.meters, now, interval_minutes=1, ticks=1))
        result = self.ingest(readings)
        tracker = self.pipeline.find(LoadBalanceTracker)
        return {
            **result,
            "timestamp": now.isoformat(),
            "meters": [{"meter_id": r.meter_id, "meter_type": r.meter_type.value,
                        "power_kw": round(r.power_kw, 2), "online": r.is_meter_active}
                       for r in readings],
            "net_load_kw": round(tracker.net_load_kw(building_id), 2) if tracker else None,
        }

    # ---- analytics ---------------------------------------------------------
    def summary(self, building_id: int, days: int = 7):
        if not 1 <= int(days) <= 365:
            raise ValidationError("days must be between 1 and 365")
        row = self.get_building(building_id)
        building = row.to_domain()
        since = datetime.now() - timedelta(days=days)
        readings = row.readings.filter(ReadingModel.timestamp > since).all()
        summary = self.analyzer.summarize(readings, building, days)
        score = self.scorer.score(summary, building)
        return building, summary, score

    def recent_readings(self, building_id: int, limit: int = 15) -> list[ReadingModel]:
        row = self.get_building(building_id)
        return row.readings.order_by(ReadingModel.timestamp.desc(),
                                     ReadingModel.id.desc()).limit(limit).all()

    # ---- AI coach -----------------------------------------------------------
    def ask_coach(self, building_id: int, question: str | None = None) -> AdviceModel:
        building, summary, score = self.summary(building_id)
        question = (question or "").strip()[:500] or None
        try:
            answer, source = self.coach.advise(building, summary, score, question)
        except AICoachError as error:
            # Graceful degradation: the user still gets useful advice.
            logger.warning("AI coach failed, using rule-based advice: %s", error)
            answer = ("(AI service unavailable - rule-based advice shown)\n"
                      + self.coach.rule_based_advice(summary, score))
            source = "rules"
        advice = AdviceModel(building_id=building_id, question=question,
                             answer=answer, source=source)
        db.session.add(advice)
        db.session.commit()
        return advice

    def advice_history(self, building_id: int, limit: int = 10) -> list[AdviceModel]:
        row = self.get_building(building_id)
        return row.advice.order_by(AdviceModel.created_at.desc()).limit(limit).all()
