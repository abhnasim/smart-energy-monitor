# ⚡ AI-Powered Smart Energy Management System

**Subsystem: Real-Time Energy Monitoring & Sustainability Analytics** · Python course, FH Dortmund

## Hometask 2 – Real-Time Data Processing

🎥 **Video presentation (3–5 min):** [watch here](PASTE_YOUR_VIDEO_LINK_HERE)

An event-driven stream processing framework for **IoT smart-meter readings** (HVAC, lighting, plug loads,
solar inverters, battery storage).

## 👤 Team overview

| Member | Role | Subsystem |
|--------|------|-----------|
| **Nasim Abhari** (matr. no. 7226039) | Developer, architect, tester – all roles | Real-Time Energy Monitoring & Sustainability Analytics |

> The group originally had four members. After the other members left the course, the professor
> approved that the project is completed by one student who focuses on one subsystem.

## 🎯 Pipeline goal (Smart Energy Management System)

1. **Filter** inactive / offline meters and sub-threshold readings (noise, standby, solar at night, idle battery)
   → `InactiveMeterFilter`, `ThresholdFilter`
2. **Transform** valid readings into energy (kWh), **carbon equivalents** (kg CO₂), cost with
   **peak-tariff flags**, and the building's **net load balance**
   → `EnergyConverter`, `CarbonTransformer`, `PeakTariffFlagger`, `LoadBalanceTracker`

```python
pipeline = (InactiveMeterFilter()
            | ThresholdFilter(min_power_kw=0.05)
            | EnergyConverter()
            | CarbonTransformer(calculator)
            | PeakTariffFlagger(calculator)
            | LoadBalanceTracker())

for reading in pipeline(MeterReadingStream(simulate_readings(meters, start, ticks=24))):
    print(reading)
```

## ✅ OOP concepts → where they are (`energy_app/pipeline.py`)

| Concept | Implementation |
|---------|----------------|
| Abstract Base Classes | `StreamProcessor` (abstract `process`), `FilterProcessor` (abstract `keep`), `TransformProcessor` (abstract `transform`) – all use `@abstractmethod` |
| Inheritance & polymorphism | 6 concrete processors inherit from the ABCs; `Pipeline` calls `handle()` on each without knowing its type. `Pipeline` is itself a `StreamProcessor` (Composite pattern) |
| Operator overloading | `__or__` and `__add__` → `a \| b` or `a + b` returns a new `Pipeline`; nested pipelines are flattened; `__len__` on `Pipeline` |
| Iterators | `MeterReadingStream` implements `__iter__` and `__next__` (with optional limit, raises `StopIteration`) |
| Generators | `simulate_readings()` (`simulator.py`) yields an endless stream of readings; `StreamProcessor.__call__` is a generator that processes lazily, one reading at a time |

## 🏗️ System design – UML class diagrams

### Stream pipeline

![Pipeline classes](docs/uml/2_pipeline.png)

### Domain classes (from Hometask 1)

![Domain classes](docs/uml/1_domain.png)

### Data flow

![Architecture](docs/uml/4_architecture.png)

## 🚀 How to run

Only Python 3.10+ is needed:

```bash
python demo_pipeline.py     # simulates 24 hours of an office building
python demo_oop.py          # Hometask 1 demo
```

The output shows the processed readings (kWh, CO₂, €, PEAK flag) and statistics per step,
e.g. how many readings each filter dropped.

## 🌿 Branches

| Branch | Content |
|--------|---------|
| `HomeworkAssignment1` | OOP classes: constructors, setup methods, getters & setters |
| `HomeworkAssignment2` | Real-time stream pipeline: ABCs, inheritance, operator overloading, iterators & generators |
| `HomeworkAssignment3` | Flask web app + MySQL database + AI coach |
| `HomeworkAssignment4` | Exception handling class + automated tests |
| `main` | Final capstone project |
