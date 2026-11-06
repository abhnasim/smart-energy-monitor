"""Unit tests for the real-time stream pipeline (Hometask 2)."""

from datetime import datetime

import pytest

from energy_app.analytics import CarbonCalculator
from energy_app.domain import Building, EnergyReading
from energy_app.pipeline import (CarbonTransformer, EnergyConverter,
                                 FilterProcessor, InactiveMeterFilter,
                                 LoadBalanceTracker, MeterReadingStream,
                                 PeakTariffFlagger, Pipeline, StreamProcessor,
                                 ThresholdFilter, build_default_pipeline)
from energy_app.simulator import simulate_readings

EVENING = datetime(2026, 11, 6, 18, 0)


def make(meter_type="hvac", power=10.0, active=True, ts=EVENING, meter_id=1):
    return EnergyReading(meter_id, meter_type, power, ts, building_id=1, is_meter_active=active)


def test_abstract_processor_cannot_be_instantiated():
    with pytest.raises(TypeError):
        StreamProcessor()
    with pytest.raises(TypeError):
        FilterProcessor()


def test_pipe_and_plus_operators_build_flat_pipelines():
    pipeline = InactiveMeterFilter() | ThresholdFilter() | EnergyConverter()
    assert isinstance(pipeline, Pipeline)
    assert len(pipeline) == 3                       # nested pipelines are flattened
    longer = pipeline + CarbonTransformer()
    assert len(longer) == 4 and len(pipeline) == 3  # original is unchanged


def test_filters_drop_inactive_and_sub_threshold_readings():
    pipeline = InactiveMeterFilter() | ThresholdFilter(min_power_kw=0.5)
    stream = [make(power=5), make(power=0.1), make(power=5, active=False),
              make("battery", -2.0)]
    kept = list(pipeline(stream))
    assert [r.power_kw for r in kept] == [5, -2.0]   # charging battery is kept
    assert pipeline.received == 4 and pipeline.dropped == 2


def test_transformers_add_energy_carbon_cost_and_peak_flag():
    calc = CarbonCalculator(emission_factor_kg_per_kwh=0.5, price_eur_per_kwh=0.3,
                            peak_price_eur_per_kwh=0.4)
    pipeline = EnergyConverter() | CarbonTransformer(calc) | PeakTariffFlagger(calc)
    consumer, solar = list(pipeline([make(power=10), make("solar", 4)]))
    assert consumer.energy_kwh == pytest.approx(10)       # 10 kW * 1 h
    assert consumer.carbon_kg == pytest.approx(5)
    assert consumer.is_peak and consumer.cost_eur == pytest.approx(4)
    assert solar.carbon_kg == pytest.approx(-2)           # avoided emissions


def test_reading_stream_is_an_iterator_with_limit():
    stream = MeterReadingStream((make(power=p) for p in range(1, 100)), limit=3)
    assert iter(stream) is stream
    assert [r.power_kw for r in stream] == [1, 2, 3]
    with pytest.raises(StopIteration):
        next(stream)
    assert stream.count == 3


def test_simulator_generator_and_load_balance_tracker():
    building = Building("Office", "office", 1000, building_id=7)
    for number, meter in enumerate(building.configure_default_meters(), start=1):
        meter.id = number
    generator = simulate_readings(building.meters, EVENING, ticks=2, seed=1)
    assert next(generator).meter_id == 1                  # lazy generator
    pipeline = build_default_pipeline()
    processed = list(pipeline(simulate_readings(building.meters, EVENING, ticks=2, seed=1)))
    assert 0 < len(processed) <= 10
    tracker = pipeline.find(LoadBalanceTracker)
    assert 7 in tracker.snapshot()
