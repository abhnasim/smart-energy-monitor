"""
Hometask 2 demo - real-time stream processing.

Run:  python demo_pipeline.py
Simulates smart meters of an office building, sends the readings through a
pipeline built with the | operator and prints what happens.
"""

from datetime import datetime

from energy_app.analytics import CarbonCalculator
from energy_app.domain import Building
from energy_app.pipeline import (CarbonTransformer, EnergyConverter,
                                 InactiveMeterFilter, LoadBalanceTracker,
                                 MeterReadingStream, PeakTariffFlagger,
                                 ThresholdFilter)
from energy_app.simulator import simulate_readings


def main() -> None:
    building = Building("Demo Office", "office", 2500, building_id=1)
    for number, meter in enumerate(building.configure_default_meters(), start=1):
        meter.id = number

    calculator = CarbonCalculator()

    # Operator overloading: | builds a Pipeline out of processors
    pipeline = (InactiveMeterFilter()
                | ThresholdFilter(min_power_kw=0.05)
                | EnergyConverter()
                | CarbonTransformer(calculator)
                | PeakTariffFlagger(calculator)
                | LoadBalanceTracker())
    print("Pipeline:", pipeline, "\n")

    # Generator (simulate_readings) wrapped in an iterator (MeterReadingStream)
    source = simulate_readings(building.meters, start=datetime(2026, 11, 6, 0, 0),
                               ticks=24, seed=42)
    stream = MeterReadingStream(source)

    print(f"{'time':<6} {'meter':<11} {'kW':>8} {'kWh':>8} {'CO2 kg':>8} {'EUR':>7}  peak")
    for reading in pipeline(stream):           # lazy: one reading at a time
        if reading.timestamp.hour % 4 == 0 or reading.is_peak:
            print(f"{reading.timestamp:%H:%M}  {reading.meter_type.value:<11}"
                  f"{reading.power_kw:8.2f} {reading.energy_kwh:8.2f}"
                  f"{reading.carbon_kg:8.2f} {reading.cost_eur:7.2f}  "
                  f"{'PEAK' if reading.is_peak else ''}")

    print(f"\nReadings consumed from the stream: {stream.count}")
    print("\nStep statistics:")
    for step in pipeline.stats():
        print(f"  {step['step']:<36} in={step['received']:>4} "
              f"out={step['passed']:>4} dropped={step['dropped']:>3}")

    tracker = pipeline.find(LoadBalanceTracker)
    print("\nCurrent net grid load per building (kW):", tracker.snapshot())


if __name__ == "__main__":
    main()
