"""
Domain model of the Real-Time Energy Monitoring subsystem.

Three core classes describe the "real world" of the system:

    Building      - an office, university building or home that we monitor
    SmartMeter    - an IoT meter installed in a building (HVAC, solar, ...)
    EnergyReading - one measurement sent by a smart meter

Every class has
    * a constructor (__init__) that initialises its state,
    * an initialisation / setup method (e.g. configure_default_meters),
    * getters and setters implemented with @property, which validate data
      before it is stored (encapsulation).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum


class BuildingType(str, Enum):
    """Kinds of buildings the system supports."""

    OFFICE = "office"
    UNIVERSITY = "university"
    HOME = "home"


class MeterType(str, Enum):
    """Kinds of smart meters.

    Consumers use energy, SOLAR produces energy and BATTERY stores energy
    (positive power = discharging into the building, negative = charging).
    """

    HVAC = "hvac"
    LIGHTING = "lighting"
    PLUG_LOADS = "plug_loads"
    SOLAR = "solar"
    BATTERY = "battery"

    @property
    def is_consumer(self) -> bool:
        return self in (MeterType.HVAC, MeterType.LIGHTING, MeterType.PLUG_LOADS)

    @property
    def is_generator(self) -> bool:
        return self is MeterType.SOLAR


# Default meter set-up per building type: (meter type, rated power in kW)
# for a building of the reference size below. Used by
# Building.configure_default_meters(), which scales it to the real floor area.
DEFAULT_METERS: dict[BuildingType, list[tuple[MeterType, float]]] = {
    BuildingType.OFFICE: [
        (MeterType.HVAC, 60.0),
        (MeterType.LIGHTING, 20.0),
        (MeterType.PLUG_LOADS, 15.0),
        (MeterType.SOLAR, 40.0),
        (MeterType.BATTERY, 30.0),
    ],
    BuildingType.UNIVERSITY: [
        (MeterType.HVAC, 250.0),
        (MeterType.LIGHTING, 80.0),
        (MeterType.PLUG_LOADS, 70.0),
        (MeterType.SOLAR, 120.0),
        (MeterType.BATTERY, 100.0),
    ],
    BuildingType.HOME: [
        (MeterType.HVAC, 3.0),
        (MeterType.LIGHTING, 0.6),
        (MeterType.PLUG_LOADS, 1.2),
        (MeterType.SOLAR, 6.0),
        (MeterType.BATTERY, 3.0),
    ],
}

# Floor area (m²) that the ratings in DEFAULT_METERS were sized for.
REFERENCE_AREA_M2: dict[BuildingType, float] = {
    BuildingType.OFFICE: 2500.0,
    BuildingType.UNIVERSITY: 8000.0,
    BuildingType.HOME: 140.0,
}


class Building:
    """A monitored building."""

    def __init__(self, name: str, building_type: BuildingType | str,
                 area_m2: float, city: str = "Dortmund",
                 building_id: int | None = None) -> None:
        self._id = building_id
        # Assigning through the setters runs the validation logic.
        self.name = name
        self.building_type = building_type
        self.area_m2 = area_m2
        self.city = city
        self._meters: list[SmartMeter] = []

    # ---- initialisation / setup -------------------------------------------
    def configure_default_meters(self) -> list["SmartMeter"]:
        """Install the standard set of meters for this building type.

        The ratings grow with the floor area, so a small library and a large
        campus building both get a realistic consumption per m².
        """
        self._meters = []
        scale = self.area_m2 / REFERENCE_AREA_M2[self.building_type]
        for number, (meter_type, rated_kw) in enumerate(
                DEFAULT_METERS[self.building_type], start=1):
            label = f"{meter_type.value.upper()}-{number:02d}"
            rated = max(round(rated_kw * scale, 2), 0.01)
            self.add_meter(SmartMeter(label, meter_type, rated))
        return self._meters

    def add_meter(self, meter: "SmartMeter") -> None:
        if not isinstance(meter, SmartMeter):
            raise TypeError("meter must be a SmartMeter")
        meter.building = self
        self._meters.append(meter)

    # ---- getters & setters ------------------------------------------------
    @property
    def id(self) -> int | None:
        return self._id

    @id.setter
    def id(self, value: int | None) -> None:
        self._id = value

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Building name must be a non-empty string")
        self._name = value.strip()

    @property
    def building_type(self) -> BuildingType:
        return self._building_type

    @building_type.setter
    def building_type(self, value: BuildingType | str) -> None:
        try:
            self._building_type = BuildingType(value)
        except ValueError:
            allowed = ", ".join(t.value for t in BuildingType)
            raise ValueError(f"Building type must be one of: {allowed}") from None

    @property
    def area_m2(self) -> float:
        return self._area_m2

    @area_m2.setter
    def area_m2(self, value: float) -> None:
        value = float(value)
        if value <= 0:
            raise ValueError("Area must be greater than 0 m²")
        self._area_m2 = value

    @property
    def city(self) -> str:
        return self._city

    @city.setter
    def city(self, value: str) -> None:
        self._city = (value or "").strip() or "Unknown"

    @property
    def meters(self) -> list["SmartMeter"]:
        """Read-only copy, so the list cannot be changed from outside."""
        return list(self._meters)

    def __repr__(self) -> str:
        return (f"Building(name={self.name!r}, type={self.building_type.value}, "
                f"area={self.area_m2:.0f} m², meters={len(self._meters)})")


class SmartMeter:
    """An IoT smart meter that measures power in kW."""

    def __init__(self, label: str, meter_type: MeterType | str,
                 rated_power_kw: float, is_active: bool = True,
                 meter_id: int | None = None) -> None:
        self._id = meter_id
        self.label = label
        self.meter_type = meter_type
        self.rated_power_kw = rated_power_kw
        self._is_active = bool(is_active)
        self._building: Building | None = None

    # ---- initialisation / setup -------------------------------------------
    def activate(self) -> None:
        self._is_active = True

    def deactivate(self) -> None:
        """Simulates a meter that is switched off or offline."""
        self._is_active = False

    def create_reading(self, power_kw: float, timestamp: datetime | None = None,
                       interval_minutes: int = 60) -> "EnergyReading":
        """Factory method: build a reading that belongs to this meter."""
        return EnergyReading(
            meter_id=self.id if self.id is not None else 0,
            meter_type=self.meter_type,
            power_kw=power_kw,
            timestamp=timestamp or datetime.now(),
            interval_minutes=interval_minutes,
            building_id=self.building.id if self.building else None,
            is_meter_active=self.is_active,
        )

    # ---- getters & setters ------------------------------------------------
    @property
    def id(self) -> int | None:
        return self._id

    @id.setter
    def id(self, value: int | None) -> None:
        self._id = value

    @property
    def label(self) -> str:
        return self._label

    @label.setter
    def label(self, value: str) -> None:
        if not value or not str(value).strip():
            raise ValueError("Meter label must not be empty")
        self._label = str(value).strip()

    @property
    def meter_type(self) -> MeterType:
        return self._meter_type

    @meter_type.setter
    def meter_type(self, value: MeterType | str) -> None:
        try:
            self._meter_type = MeterType(value)
        except ValueError:
            allowed = ", ".join(t.value for t in MeterType)
            raise ValueError(f"Meter type must be one of: {allowed}") from None

    @property
    def rated_power_kw(self) -> float:
        return self._rated_power_kw

    @rated_power_kw.setter
    def rated_power_kw(self, value: float) -> None:
        value = float(value)
        if value <= 0:
            raise ValueError("Rated power must be greater than 0 kW")
        self._rated_power_kw = value

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def building(self) -> Building | None:
        return self._building

    @building.setter
    def building(self, value: Building | None) -> None:
        self._building = value

    def __repr__(self) -> str:
        state = "active" if self.is_active else "inactive"
        return (f"SmartMeter({self.label!r}, {self.meter_type.value}, "
                f"{self.rated_power_kw} kW, {state})")


class EnergyReading:
    """One measurement from a smart meter.

    The stream pipeline (pipeline.py) fills in the calculated fields:
    energy_kwh, carbon_kg, cost_eur and is_peak.
    """

    def __init__(self, meter_id: int, meter_type: MeterType | str,
                 power_kw: float, timestamp: datetime,
                 interval_minutes: int = 60, building_id: int | None = None,
                 is_meter_active: bool = True) -> None:
        self.meter_id = meter_id
        self.meter_type = meter_type
        self.power_kw = power_kw
        self.timestamp = timestamp
        self.interval_minutes = interval_minutes
        self.building_id = building_id
        self.is_meter_active = is_meter_active
        self.reset_calculations()

    # ---- initialisation / setup -------------------------------------------
    def reset_calculations(self) -> None:
        """Clear the fields that the pipeline calculates."""
        self.energy_kwh: float | None = None
        self.carbon_kg: float | None = None
        self.cost_eur: float | None = None
        self.is_peak: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "EnergyReading":
        """Create a reading from JSON data (e.g. sent by an IoT device)."""
        required = ("meter_id", "meter_type", "power_kw")
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"Missing field(s): {', '.join(missing)}")
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return cls(
            meter_id=int(data["meter_id"]),
            meter_type=data["meter_type"],
            power_kw=float(data["power_kw"]),
            timestamp=timestamp or datetime.now(),
            interval_minutes=int(data.get("interval_minutes", 60)),
            building_id=data.get("building_id"),
            is_meter_active=bool(data.get("is_meter_active", True)),
        )

    def to_dict(self) -> dict:
        return {
            "meter_id": self.meter_id,
            "building_id": self.building_id,
            "meter_type": self.meter_type.value,
            "timestamp": self.timestamp.isoformat(timespec="seconds"),
            "power_kw": round(self.power_kw, 3),
            "interval_minutes": self.interval_minutes,
            "energy_kwh": None if self.energy_kwh is None else round(self.energy_kwh, 3),
            "carbon_kg": None if self.carbon_kg is None else round(self.carbon_kg, 3),
            "cost_eur": None if self.cost_eur is None else round(self.cost_eur, 3),
            "is_peak": self.is_peak,
        }

    # ---- getters & setters ------------------------------------------------
    @property
    def meter_type(self) -> MeterType:
        return self._meter_type

    @meter_type.setter
    def meter_type(self, value: MeterType | str) -> None:
        self._meter_type = MeterType(value)

    @property
    def power_kw(self) -> float:
        return self._power_kw

    @power_kw.setter
    def power_kw(self, value: float) -> None:
        value = float(value)
        # Only a battery may report negative power (= charging).
        if value < 0 and self.meter_type is not MeterType.BATTERY:
            raise ValueError("Power cannot be negative for this meter type")
        self._power_kw = value

    @property
    def timestamp(self) -> datetime:
        return self._timestamp

    @timestamp.setter
    def timestamp(self, value: datetime) -> None:
        if not isinstance(value, datetime):
            raise ValueError("timestamp must be a datetime")
        self._timestamp = value

    @property
    def interval_minutes(self) -> int:
        return self._interval_minutes

    @interval_minutes.setter
    def interval_minutes(self, value: int) -> None:
        value = int(value)
        if not 1 <= value <= 1440:
            raise ValueError("interval_minutes must be between 1 and 1440")
        self._interval_minutes = value

    @property
    def interval_hours(self) -> float:
        return self.interval_minutes / 60

    def __repr__(self) -> str:
        return (f"EnergyReading(meter={self.meter_id}, {self.meter_type.value}, "
                f"{self.power_kw:.2f} kW @ {self.timestamp:%Y-%m-%d %H:%M})")
