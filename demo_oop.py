"""
Hometask 1 demo - Object-Oriented concepts.

Run:  python demo_oop.py
Shows constructors, setup methods, getters/setters and validation.
"""

from datetime import datetime

from energy_app.analytics import CarbonCalculator
from energy_app.domain import Building, EnergyReading, MeterType, SmartMeter


def main() -> None:
    print("=== 1. Building: constructor + setup method ===")
    office = Building("FH Dortmund - Emil-Figge-Str. 42", "university", 8000)
    office.configure_default_meters()          # initialisation method
    print(office)
    for meter in office.meters:
        print("   ", meter)

    print("\n=== 2. Getters and setters with validation ===")
    print("Area (getter):", office.area_m2, "m²")
    office.area_m2 = 8500                      # setter
    print("Area after setter:", office.area_m2, "m²")
    try:
        office.area_m2 = -10                   # invalid -> ValueError
    except ValueError as error:
        print("Rejected invalid area ->", error)

    print("\n=== 3. SmartMeter: activate / deactivate ===")
    meter = SmartMeter("HVAC-99", MeterType.HVAC, rated_power_kw=12.5)
    meter.deactivate()
    print(meter)
    meter.activate()
    print(meter)

    print("\n=== 4. EnergyReading: factory method + from_dict ===")
    reading = meter.create_reading(power_kw=7.2, timestamp=datetime(2026, 11, 6, 18, 0))
    print(reading)
    from_iot = EnergyReading.from_dict(
        {"meter_id": 3, "meter_type": "solar", "power_kw": 4.1,
         "timestamp": "2026-11-06T12:00:00"})
    print(from_iot)

    print("\n=== 5. CarbonCalculator ===")
    calc = CarbonCalculator()
    print(f"10 kWh = {calc.carbon_for(10):.2f} kg CO2")
    print("18:00 is peak tariff?", calc.is_peak(datetime(2026, 11, 6, 18, 0)))
    calc.configure(price=0.35, peak_price=0.50)
    print("New prices:", calc.price, "/", calc.peak_price, "EUR per kWh")


if __name__ == "__main__":
    main()
