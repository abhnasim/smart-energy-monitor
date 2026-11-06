"""
IoT smart-meter simulator.

Real buildings would send readings over MQTT/HTTP. For the MVP we generate
realistic readings with a Python *generator* (yield), so the rest of the
system works exactly as with real meters.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta
from typing import Iterator

from .domain import BuildingType, EnergyReading, MeterType, SmartMeter


def occupancy(building_type: BuildingType, ts: datetime) -> float:
    """How "busy" a building is at a given time (0..1)."""
    hour, weekend = ts.hour, ts.weekday() >= 5
    if building_type is BuildingType.HOME:
        if 6 <= hour < 8:
            return 0.6
        if 17 <= hour < 23:
            return 0.85
        if 8 <= hour < 17:
            return 0.55 if weekend else 0.25
        return 0.1
    opening = (7, 19) if building_type is BuildingType.OFFICE else (8, 21)
    if not weekend and opening[0] <= hour < opening[1]:
        return 0.8
    return 0.08


def load_factor(meter_type: MeterType, building_type: BuildingType,
                ts: datetime, rng: random.Random) -> float:
    """Share of the rated power a meter uses at time ts (-1..1)."""
    hour = ts.hour + ts.minute / 60
    if meter_type is MeterType.SOLAR:
        # winter = 0 in late June, 1 in late December -> shorter, weaker days
        winter = (1 - math.cos(2 * math.pi * (ts.timetuple().tm_yday - 172) / 365)) / 2
        sunrise, sunset = 5 + 3 * winter, 21.5 - 5 * winter
        if not sunrise <= hour <= sunset:
            return 0.0
        daylight = math.sin(math.pi * (hour - sunrise) / (sunset - sunrise))
        return daylight * (1 - 0.6 * winter) * rng.uniform(0.35, 1.0)   # clouds
    if meter_type is MeterType.BATTERY:
        if 11 <= hour < 15:
            return -0.5          # charge with midday solar
        if 17 <= hour < 21:
            return 0.5           # discharge during the peak tariff
        return 0.0               # idle -> removed by ThresholdFilter
    occ = occupancy(building_type, ts)
    base, span = {MeterType.HVAC: (0.2, 0.55),
                  MeterType.LIGHTING: (0.03, 0.8),
                  MeterType.PLUG_LOADS: (0.1, 0.6)}[meter_type]
    return (base + span * occ) * rng.uniform(0.9, 1.1)


def simulate_readings(meters: list[SmartMeter], start: datetime,
                      interval_minutes: int = 60, ticks: int | None = None,
                      offline_rate: float = 0.02,
                      seed: int | None = None) -> Iterator[EnergyReading]:
    """Generator: yields one reading per meter per time step.

    ticks=None means an endless stream (real-time mode).
    offline_rate is the chance that a meter is temporarily offline.
    """
    rng = random.Random(seed)
    tick = 0
    while ticks is None or tick < ticks:
        ts = start + timedelta(minutes=interval_minutes * tick)
        for meter in meters:
            building_type = meter.building.building_type if meter.building else BuildingType.OFFICE
            reading = meter.create_reading(
                power_kw=meter.rated_power_kw * load_factor(meter.meter_type, building_type, ts, rng),
                timestamp=ts, interval_minutes=interval_minutes)
            if not meter.is_active or rng.random() < offline_rate:
                reading.is_meter_active = False
                reading.power_kw = 0.0
            yield reading
        tick += 1
