"""
Analytics layer: turns energy readings into the numbers shown on the dashboard.

    CarbonCalculator     - emission factor, electricity tariff and peak hours
    EnergyAnalyzer       - totals, savings, daily/hourly series per building
    SustainabilityScorer - 0-100 score + grade (A-E) for a building

All numbers are deliberately simple so they can be explained in a presentation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from .domain import Building, BuildingType, MeterType

# Illustrative electricity benchmarks in kWh per m² per year.
BENCHMARK_KWH_PER_M2_YEAR = {
    BuildingType.OFFICE: 150.0,
    BuildingType.UNIVERSITY: 180.0,
    BuildingType.HOME: 120.0,
}


class CarbonCalculator:
    """Knows how much CO2 and money one kWh costs at a given time."""

    def __init__(self, emission_factor_kg_per_kwh: float = 0.380,
                 price_eur_per_kwh: float = 0.30,
                 peak_price_eur_per_kwh: float = 0.42,
                 peak_hours: tuple[int, int] = (17, 21)) -> None:
        self.emission_factor = emission_factor_kg_per_kwh
        self.price = price_eur_per_kwh
        self.peak_price = peak_price_eur_per_kwh
        self.peak_hours = peak_hours

    # ---- initialisation / setup -------------------------------------------
    def configure(self, **settings) -> "CarbonCalculator":
        """Change several settings at once, e.g. configure(price=0.35)."""
        for name, value in settings.items():
            if not hasattr(self, name):
                raise AttributeError(f"Unknown setting: {name}")
            setattr(self, name, value)
        return self

    # ---- getters & setters ------------------------------------------------
    @property
    def emission_factor(self) -> float:
        """kg CO2 per kWh taken from the grid (approx. German grid mix)."""
        return self._emission_factor

    @emission_factor.setter
    def emission_factor(self, value: float) -> None:
        if not 0 <= float(value) <= 2:
            raise ValueError("Emission factor must be between 0 and 2 kg/kWh")
        self._emission_factor = float(value)

    @property
    def price(self) -> float:
        return self._price

    @price.setter
    def price(self, value: float) -> None:
        if float(value) < 0:
            raise ValueError("Price cannot be negative")
        self._price = float(value)

    @property
    def peak_price(self) -> float:
        return self._peak_price

    @peak_price.setter
    def peak_price(self, value: float) -> None:
        if float(value) < 0:
            raise ValueError("Peak price cannot be negative")
        self._peak_price = float(value)

    @property
    def peak_hours(self) -> tuple[int, int]:
        """(start, end) hour of the peak tariff, end is exclusive."""
        return self._peak_hours

    @peak_hours.setter
    def peak_hours(self, value: tuple[int, int]) -> None:
        start, end = value
        if not 0 <= start < end <= 24:
            raise ValueError("Peak hours must satisfy 0 <= start < end <= 24")
        self._peak_hours = (int(start), int(end))

    # ---- calculations -----------------------------------------------------
    def is_peak(self, timestamp: datetime) -> bool:
        start, end = self.peak_hours
        return start <= timestamp.hour < end

    def price_at(self, timestamp: datetime) -> float:
        return self.peak_price if self.is_peak(timestamp) else self.price

    def carbon_for(self, kwh: float) -> float:
        return kwh * self.emission_factor


@dataclass
class EnergySummary:
    """Result of EnergyAnalyzer.summarize() - everything the dashboard needs."""

    days: float
    consumption_kwh: float = 0.0
    solar_kwh: float = 0.0
    battery_kwh: float = 0.0          # + discharged, - charged
    net_grid_kwh: float = 0.0
    carbon_kg: float = 0.0
    cost_eur: float = 0.0
    peak_consumption_kwh: float = 0.0
    baseline_kwh: float = 0.0
    savings_kwh: float = 0.0
    savings_eur: float = 0.0
    carbon_reduction_kg: float = 0.0
    by_type_kwh: dict = field(default_factory=dict)
    daily: list = field(default_factory=list)
    hourly: list = field(default_factory=list)

    @property
    def renewable_share(self) -> float:
        return self.solar_kwh / self.consumption_kwh if self.consumption_kwh else 0.0

    @property
    def peak_share(self) -> float:
        return (self.peak_consumption_kwh / self.consumption_kwh
                if self.consumption_kwh else 0.0)

    def to_dict(self) -> dict:
        data = {key: (round(value, 2) if isinstance(value, float) else value)
                for key, value in self.__dict__.items()}
        data["renewable_share"] = round(self.renewable_share, 3)
        data["peak_share"] = round(self.peak_share, 3)
        return data


class EnergyAnalyzer:
    """Aggregates processed readings into an EnergySummary.

    A "reading" here is any object with the attributes meter_type, timestamp,
    energy_kwh, carbon_kg, cost_eur and is_peak - so it works for both the
    domain EnergyReading and the database ReadingModel (duck typing).
    """

    def __init__(self, calculator: CarbonCalculator | None = None) -> None:
        self._calculator = calculator or CarbonCalculator()

    @property
    def calculator(self) -> CarbonCalculator:
        return self._calculator

    @calculator.setter
    def calculator(self, value: CarbonCalculator) -> None:
        if not isinstance(value, CarbonCalculator):
            raise TypeError("calculator must be a CarbonCalculator")
        self._calculator = value

    @staticmethod
    def baseline_kwh(building: Building, days: float) -> float:
        """Expected consumption of an average building of the same type and size."""
        per_year = BENCHMARK_KWH_PER_M2_YEAR[building.building_type] * building.area_m2
        return per_year * days / 365

    def summarize(self, readings, building: Building, days: float) -> EnergySummary:
        s = EnergySummary(days=days)
        by_type: dict[str, float] = defaultdict(float)
        daily: dict[str, dict[str, float]] = defaultdict(
            lambda: {"consumption": 0.0, "solar": 0.0, "net": 0.0})
        hourly: dict[datetime, float] = defaultdict(float)
        latest = None

        for r in readings:
            meter_type = MeterType(r.meter_type)
            kwh = r.energy_kwh or 0.0
            day = r.timestamp.strftime("%Y-%m-%d")
            hour = r.timestamp.replace(minute=0, second=0, microsecond=0)
            latest = max(latest, r.timestamp) if latest else r.timestamp
            by_type[meter_type.value] += kwh
            s.carbon_kg += r.carbon_kg or 0.0
            s.cost_eur += r.cost_eur or 0.0

            if meter_type.is_consumer:
                s.consumption_kwh += kwh
                daily[day]["consumption"] += kwh
                daily[day]["net"] += kwh
                hourly[hour] += kwh
                if r.is_peak:
                    s.peak_consumption_kwh += kwh
            elif meter_type.is_generator:
                s.solar_kwh += kwh
                daily[day]["solar"] += kwh
                daily[day]["net"] -= kwh
                hourly[hour] -= kwh
            else:  # battery
                s.battery_kwh += kwh
                daily[day]["net"] -= kwh
                hourly[hour] -= kwh

        s.net_grid_kwh = max(0.0, s.consumption_kwh - s.solar_kwh - s.battery_kwh)
        s.baseline_kwh = self.baseline_kwh(building, days)
        s.savings_kwh = s.baseline_kwh - s.net_grid_kwh
        s.savings_eur = s.savings_kwh * self.calculator.price
        s.carbon_reduction_kg = self.calculator.carbon_for(s.savings_kwh)
        s.by_type_kwh = {k: round(v, 1) for k, v in sorted(by_type.items())}
        daily_baseline = self.baseline_kwh(building, 1)
        s.daily = [{"date": d, **{k: round(v, 1) for k, v in values.items()},
                    "baseline": round(daily_baseline, 1)}
                   for d, values in sorted(daily.items())]
        if latest:
            since = latest - timedelta(hours=24)
            s.hourly = [{"time": h.strftime("%d.%m %H:%M"), "net_kwh": round(v, 2)}
                        for h, v in sorted(hourly.items()) if h > since]
        return s


@dataclass
class SustainabilityScore:
    total: float
    grade: str
    efficiency_score: float
    renewable_score: float
    peak_score: float
    intensity_kwh_m2_year: float
    benchmark_kwh_m2_year: float

    def to_dict(self) -> dict:
        return {k: (round(v, 1) if isinstance(v, float) else v)
                for k, v in self.__dict__.items()}


class SustainabilityScorer:
    """Rates a building from 0 to 100.

        50 % efficiency  - consumption per m² compared with the benchmark
        30 % renewables  - share of consumption covered by own solar power
        20 % peak load   - share of consumption during expensive peak hours
    """

    GRADES = [(85, "A"), (70, "B"), (55, "C"), (40, "D"), (0, "E")]

    def __init__(self, weights: tuple[float, float, float] = (0.5, 0.3, 0.2)) -> None:
        self.weights = weights

    @property
    def weights(self) -> tuple[float, float, float]:
        return self._weights

    @weights.setter
    def weights(self, value: tuple[float, float, float]) -> None:
        if len(value) != 3 or abs(sum(value) - 1.0) > 1e-6:
            raise ValueError("Exactly three weights that add up to 1.0 are required")
        self._weights = tuple(float(v) for v in value)

    @staticmethod
    def _linear(value: float, best: float, worst: float) -> float:
        """Map value to 0..100 where `best` gives 100 and `worst` gives 0."""
        if best == worst:
            return 100.0
        ratio = (value - worst) / (best - worst)
        return max(0.0, min(100.0, ratio * 100))

    @classmethod
    def grade_for(cls, total: float) -> str:
        for limit, grade in cls.GRADES:
            if total >= limit:
                return grade
        return "E"

    def score(self, summary: EnergySummary, building: Building) -> SustainabilityScore:
        benchmark = BENCHMARK_KWH_PER_M2_YEAR[building.building_type]
        days = summary.days or 1
        intensity = summary.consumption_kwh / days * 365 / building.area_m2

        efficiency = self._linear(intensity / benchmark, best=0.5, worst=1.5)
        renewable = self._linear(summary.renewable_share, best=0.5, worst=0.0)
        peak = self._linear(summary.peak_share, best=0.10, worst=0.40)

        w_eff, w_ren, w_peak = self.weights
        total = w_eff * efficiency + w_ren * renewable + w_peak * peak
        return SustainabilityScore(
            total=total, grade=self.grade_for(total),
            efficiency_score=efficiency, renewable_score=renewable,
            peak_score=peak, intensity_kwh_m2_year=intensity,
            benchmark_kwh_m2_year=benchmark,
        )
