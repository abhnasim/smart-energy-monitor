"""Unit tests for the OOP domain classes and analytics (Hometask 1)."""

from datetime import datetime

import pytest

from energy_app.analytics import (CarbonCalculator, EnergyAnalyzer,
                                  SustainabilityScorer)
from energy_app.domain import (Building, BuildingType, EnergyReading,
                               MeterType, SmartMeter)


def test_building_setup_installs_default_meters():
    building = Building("Library", "university", 3000)
    meters = building.configure_default_meters()
    assert building.building_type is BuildingType.UNIVERSITY
    assert len(meters) == 5
    assert {m.meter_type for m in meters} == set(MeterType)
    assert all(m.building is building for m in meters)


def test_default_meter_ratings_scale_with_floor_area():
    small = Building("Library", "university", 1200).configure_default_meters()
    large = Building("Campus", "university", 8000).configure_default_meters()
    for small_meter, large_meter in zip(small, large):
        assert small_meter.rated_power_kw == pytest.approx(
            large_meter.rated_power_kw * 1200 / 8000, abs=0.01)


@pytest.mark.parametrize("area", [0, -50])
def test_building_rejects_invalid_area(area):
    with pytest.raises(ValueError):
        Building("Library", "office", area)


def test_building_rejects_unknown_type_and_empty_name():
    with pytest.raises(ValueError, match="Building type"):
        Building("Library", "castle", 100)
    with pytest.raises(ValueError, match="name"):
        Building("   ", "home", 100)


def test_meter_activate_and_deactivate():
    meter = SmartMeter("HVAC-1", "hvac", 10)
    meter.deactivate()
    assert not meter.is_active
    assert not meter.create_reading(5).is_meter_active
    meter.activate()
    assert meter.is_active


def test_only_battery_may_report_negative_power():
    now = datetime(2026, 11, 6, 12)
    assert EnergyReading(1, "battery", -3.0, now).power_kw == -3.0
    with pytest.raises(ValueError):
        EnergyReading(1, "hvac", -3.0, now)


def test_reading_from_dict_validates_fields():
    reading = EnergyReading.from_dict({"meter_id": 2, "meter_type": "solar", "power_kw": "4.5",
                                       "timestamp": "2026-11-06T12:00:00"})
    assert reading.power_kw == 4.5 and reading.timestamp.hour == 12
    with pytest.raises(ValueError, match="power_kw"):
        EnergyReading.from_dict({"meter_id": 2, "meter_type": "solar"})


def test_carbon_calculator_peak_tariff_and_setters():
    calc = CarbonCalculator(emission_factor_kg_per_kwh=0.4, price_eur_per_kwh=0.3,
                            peak_price_eur_per_kwh=0.5, peak_hours=(17, 21))
    assert calc.is_peak(datetime(2026, 11, 6, 18))
    assert not calc.is_peak(datetime(2026, 11, 6, 21))
    assert calc.price_at(datetime(2026, 11, 6, 18)) == 0.5
    assert calc.carbon_for(10) == pytest.approx(4.0)
    with pytest.raises(ValueError):
        calc.peak_hours = (22, 10)
    with pytest.raises(AttributeError):
        calc.configure(unknown_setting=1)


@pytest.mark.parametrize("total, grade", [(90, "A"), (85, "A"), (70, "B"), (60, "C"),
                                          (40, "D"), (12, "E")])
def test_score_grades(total, grade):
    assert SustainabilityScorer.grade_for(total) == grade


def test_analyzer_calculates_savings_and_renewable_share():
    building = Building("Home", "home", 365)       # baseline: 120 kWh per day
    ts = datetime(2026, 11, 6, 12)
    readings = []
    for meter_type, kwh in [("hvac", 60), ("lighting", 20), ("solar", 20)]:
        r = EnergyReading(1, meter_type, kwh, ts)
        r.energy_kwh = kwh
        r.carbon_kg = r.cost_eur = 0
        readings.append(r)
    summary = EnergyAnalyzer().summarize(readings, building, days=1)
    assert summary.consumption_kwh == 80
    assert summary.net_grid_kwh == 60
    assert summary.baseline_kwh == pytest.approx(120)
    assert summary.savings_kwh == pytest.approx(60)
    assert summary.renewable_share == pytest.approx(0.25)
    score = SustainabilityScorer().score(summary, building)
    assert 0 <= score.total <= 100 and score.grade in "ABCDE"
