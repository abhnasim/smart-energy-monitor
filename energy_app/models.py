"""
Database layer (Flask-SQLAlchemy ORM).

Tables:  buildings 1--* meters 1--* readings
         buildings 1--* coach_advice

The same code works with MySQL (Docker) and SQLite (local development);
only the DATABASE_URL changes.
"""

from __future__ import annotations

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

from .domain import Building, EnergyReading, SmartMeter

db = SQLAlchemy()


class BuildingModel(db.Model):
    __tablename__ = "buildings"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    building_type = db.Column(db.String(20), nullable=False)
    area_m2 = db.Column(db.Float, nullable=False)
    city = db.Column(db.String(80), default="Dortmund")
    created_at = db.Column(db.DateTime, default=datetime.now)

    meters = db.relationship("MeterModel", back_populates="building",
                             cascade="all, delete-orphan", lazy=True)
    readings = db.relationship("ReadingModel", back_populates="building",
                               cascade="all, delete-orphan", lazy="dynamic")
    advice = db.relationship("AdviceModel", back_populates="building",
                             cascade="all, delete-orphan", lazy="dynamic")

    def to_domain(self) -> Building:
        """Convert the database row into the domain object (with meters)."""
        building = Building(self.name, self.building_type, self.area_m2,
                            self.city, building_id=self.id)
        for meter in self.meters:
            building.add_meter(meter.to_domain())
        return building

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "building_type": self.building_type,
                "area_m2": self.area_m2, "city": self.city,
                "meters": [m.to_dict() for m in self.meters]}


class MeterModel(db.Model):
    __tablename__ = "meters"

    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), nullable=False)
    label = db.Column(db.String(40), nullable=False)
    meter_type = db.Column(db.String(20), nullable=False)
    rated_power_kw = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    building = db.relationship("BuildingModel", back_populates="meters")

    def to_domain(self) -> SmartMeter:
        return SmartMeter(self.label, self.meter_type, self.rated_power_kw,
                          self.is_active, meter_id=self.id)

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "meter_type": self.meter_type,
                "rated_power_kw": self.rated_power_kw, "is_active": self.is_active}


class ReadingModel(db.Model):
    __tablename__ = "readings"

    id = db.Column(db.Integer, primary_key=True)
    meter_id = db.Column(db.Integer, db.ForeignKey("meters.id"), nullable=False)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"),
                            nullable=False, index=True)
    meter_type = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, index=True)
    power_kw = db.Column(db.Float, nullable=False)
    interval_minutes = db.Column(db.Integer, default=60)
    energy_kwh = db.Column(db.Float)
    carbon_kg = db.Column(db.Float)
    cost_eur = db.Column(db.Float)
    is_peak = db.Column(db.Boolean, default=False)

    building = db.relationship("BuildingModel", back_populates="readings")

    @classmethod
    def from_domain(cls, reading: EnergyReading) -> "ReadingModel":
        """Create a database row from a processed domain reading."""
        return cls(meter_id=reading.meter_id, building_id=reading.building_id,
                   meter_type=reading.meter_type.value, timestamp=reading.timestamp,
                   power_kw=reading.power_kw, interval_minutes=reading.interval_minutes,
                   energy_kwh=reading.energy_kwh, carbon_kg=reading.carbon_kg,
                   cost_eur=reading.cost_eur, is_peak=reading.is_peak)


class AdviceModel(db.Model):
    """History of AI Sustainability Coach answers."""

    __tablename__ = "coach_advice"

    id = db.Column(db.Integer, primary_key=True)
    building_id = db.Column(db.Integer, db.ForeignKey("buildings.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)
    question = db.Column(db.Text)
    answer = db.Column(db.Text, nullable=False)
    source = db.Column(db.String(20), nullable=False)   # "openai", "gemini" or "rules"

    building = db.relationship("BuildingModel", back_populates="advice")
