"""
Event-driven stream processing framework for smart-meter readings.

OOP concepts demonstrated (Hometask 2):

    1. Abstract Base Classes  - StreamProcessor, FilterProcessor, TransformProcessor
    2. Inheritance & polymorphism - every processor implements process()
       and the Pipeline calls them all through the same interface
    3. Operator overloading   - `a | b` (and `a + b`) builds a Pipeline
    4. Iterators & generators - MeterReadingStream implements __iter__/__next__,
       StreamProcessor.__call__ is a generator that processes readings lazily

Example:
    pipeline = InactiveMeterFilter() | ThresholdFilter(0.05) | EnergyConverter()
    for reading in pipeline(MeterReadingStream(source)):
        print(reading)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Iterable, Iterator

from .analytics import CarbonCalculator
from .domain import EnergyReading, MeterType


# --------------------------------------------------------------------------
# 1. Abstract base classes (the "interface contract")
# --------------------------------------------------------------------------
class StreamProcessor(ABC):
    """Base class of every pipeline step.

    process() returns the (possibly changed) reading, or None to drop it.
    """

    def __init__(self) -> None:
        self.received = 0
        self.passed = 0

    @abstractmethod
    def process(self, reading: EnergyReading) -> EnergyReading | None:
        """Handle one reading. Must be implemented by every subclass."""

    @property
    def name(self) -> str:
        return type(self).__name__

    @property
    def dropped(self) -> int:
        return self.received - self.passed

    def handle(self, reading: EnergyReading) -> EnergyReading | None:
        """Template method: counts readings and calls process()."""
        self.received += 1
        result = self.process(reading)
        if result is not None:
            self.passed += 1
        return result

    # ---- 3. operator overloading ------------------------------------------
    def __or__(self, other: "StreamProcessor") -> "Pipeline":
        """processor_a | processor_b  ->  Pipeline(processor_a, processor_b)"""
        if not isinstance(other, StreamProcessor):
            return NotImplemented
        return Pipeline(self, other)

    __add__ = __or__   # processor_a + processor_b works the same way

    # ---- 4. generator -----------------------------------------------------
    def __call__(self, stream: Iterable[EnergyReading]) -> Iterator[EnergyReading]:
        """Lazily process a stream: readings are handled one at a time."""
        for reading in stream:
            result = self.handle(reading)
            if result is not None:
                yield result

    def __repr__(self) -> str:
        return f"{self.name}()"


class FilterProcessor(StreamProcessor, ABC):
    """A step that keeps or drops readings."""

    @abstractmethod
    def keep(self, reading: EnergyReading) -> bool:
        """Return True to keep the reading."""

    def process(self, reading: EnergyReading) -> EnergyReading | None:
        return reading if self.keep(reading) else None


class TransformProcessor(StreamProcessor, ABC):
    """A step that enriches / changes every reading."""

    @abstractmethod
    def transform(self, reading: EnergyReading) -> EnergyReading:
        """Return the transformed reading."""

    def process(self, reading: EnergyReading) -> EnergyReading:
        return self.transform(reading)


# --------------------------------------------------------------------------
# 2. Concrete processors (inheritance + polymorphism)
# --------------------------------------------------------------------------
class InactiveMeterFilter(FilterProcessor):
    """Drops readings from meters that are switched off or offline."""

    def keep(self, reading: EnergyReading) -> bool:
        return reading.is_meter_active


class ThresholdFilter(FilterProcessor):
    """Drops sub-threshold readings (noise, standby, solar at night...)."""

    def __init__(self, min_power_kw: float = 0.05) -> None:
        super().__init__()
        if min_power_kw < 0:
            raise ValueError("min_power_kw cannot be negative")
        self.min_power_kw = min_power_kw

    def keep(self, reading: EnergyReading) -> bool:
        # abs() because a charging battery reports negative power
        return abs(reading.power_kw) >= self.min_power_kw

    def __repr__(self) -> str:
        return f"ThresholdFilter(min_power_kw={self.min_power_kw})"


def grid_sign(meter_type: MeterType) -> int:
    """+1 if the meter takes energy from the grid, -1 if it reduces grid usage."""
    return 1 if meter_type.is_consumer else -1


class EnergyConverter(TransformProcessor):
    """Power (kW) x interval (h) = energy (kWh)."""

    def transform(self, reading: EnergyReading) -> EnergyReading:
        reading.energy_kwh = reading.power_kw * reading.interval_hours
        return reading


class CarbonTransformer(TransformProcessor):
    """Adds the CO2 equivalent. Solar / battery discharge give negative CO2 (avoided)."""

    def __init__(self, calculator: CarbonCalculator | None = None) -> None:
        super().__init__()
        self.calculator = calculator or CarbonCalculator()

    def transform(self, reading: EnergyReading) -> EnergyReading:
        if reading.energy_kwh is None:
            reading.energy_kwh = reading.power_kw * reading.interval_hours
        reading.carbon_kg = (grid_sign(reading.meter_type)
                             * self.calculator.carbon_for(reading.energy_kwh))
        return reading


class PeakTariffFlagger(TransformProcessor):
    """Flags peak-tariff readings and adds the cost in EUR."""

    def __init__(self, calculator: CarbonCalculator | None = None) -> None:
        super().__init__()
        self.calculator = calculator or CarbonCalculator()

    def transform(self, reading: EnergyReading) -> EnergyReading:
        if reading.energy_kwh is None:
            reading.energy_kwh = reading.power_kw * reading.interval_hours
        reading.is_peak = self.calculator.is_peak(reading.timestamp)
        price = self.calculator.price_at(reading.timestamp)
        reading.cost_eur = grid_sign(reading.meter_type) * reading.energy_kwh * price
        return reading


class LoadBalanceTracker(TransformProcessor):
    """Stateful step: keeps the latest power of every meter and computes the
    current net grid load of each building (consumption - solar - battery)."""

    def __init__(self) -> None:
        super().__init__()
        self._latest: dict = defaultdict(dict)   # building -> {meter: (type, kW)}

    def transform(self, reading: EnergyReading) -> EnergyReading:
        self._latest[reading.building_id][reading.meter_id] = (
            reading.meter_type, reading.power_kw)
        return reading

    def net_load_kw(self, building_id) -> float:
        meters = self._latest.get(building_id, {})
        return sum(grid_sign(meter_type) * power for meter_type, power in meters.values())

    def snapshot(self) -> dict:
        return {building: round(self.net_load_kw(building), 2) for building in self._latest}


class Pipeline(StreamProcessor):
    """A chain of processors that itself behaves like one processor (Composite)."""

    def __init__(self, *processors: StreamProcessor) -> None:
        super().__init__()
        self.processors: list[StreamProcessor] = []
        for processor in processors:
            # Flatten nested pipelines: (a | b) | c  ->  Pipeline(a, b, c)
            if isinstance(processor, Pipeline):
                self.processors.extend(processor.processors)
            else:
                self.processors.append(processor)

    def process(self, reading: EnergyReading) -> EnergyReading | None:
        for processor in self.processors:
            reading = processor.handle(reading)
            if reading is None:          # dropped by a filter
                return None
        return reading

    def __or__(self, other: StreamProcessor) -> "Pipeline":
        if not isinstance(other, StreamProcessor):
            return NotImplemented
        return Pipeline(*self.processors, other)

    __add__ = __or__

    def __len__(self) -> int:
        return len(self.processors)

    def find(self, processor_type: type) -> StreamProcessor | None:
        return next((p for p in self.processors if isinstance(p, processor_type)), None)

    def stats(self) -> list[dict]:
        return [{"step": repr(p), "received": p.received, "passed": p.passed,
                 "dropped": p.dropped} for p in self.processors]

    def __repr__(self) -> str:
        return " | ".join(repr(p) for p in self.processors)


# --------------------------------------------------------------------------
# 4. Iterator over a source of readings
# --------------------------------------------------------------------------
class MeterReadingStream:
    """Iterator that consumes readings from any source (list, generator,
    message queue...) with an optional limit."""

    def __init__(self, source: Iterable[EnergyReading], limit: int | None = None) -> None:
        self._source = iter(source)
        self._limit = limit
        self._count = 0

    def __iter__(self) -> "MeterReadingStream":
        return self

    def __next__(self) -> EnergyReading:
        if self._limit is not None and self._count >= self._limit:
            raise StopIteration
        reading = next(self._source)          # raises StopIteration at the end
        self._count += 1
        return reading

    @property
    def count(self) -> int:
        return self._count


def build_default_pipeline(calculator: CarbonCalculator | None = None,
                           min_power_kw: float = 0.05) -> Pipeline:
    """The standard ingestion pipeline used by the web application."""
    calculator = calculator or CarbonCalculator()
    return (InactiveMeterFilter()
            | ThresholdFilter(min_power_kw)
            | EnergyConverter()
            | CarbonTransformer(calculator)
            | PeakTariffFlagger(calculator)
            | LoadBalanceTracker())
