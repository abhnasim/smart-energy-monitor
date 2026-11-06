# ⚡ AI-Powered Smart Energy Management System

**Subsystem: Real-Time Energy Monitoring & Sustainability Analytics** · Python course, FH Dortmund

## Hometask 1 – Object-Oriented Concepts

🎥 **Video presentation (3–5 min):** [watch here](PASTE_YOUR_VIDEO_LINK_HERE)

This branch translates the UML class diagram of the subsystem into Python classes.

## 👤 Team overview

| Member | Role | Subsystem |
|--------|------|-----------|
| **YOUR NAME** (matr. no. XXXXXXX) | Developer, architect, tester – all roles | Real-Time Energy Monitoring & Sustainability Analytics |

> The group originally had four members. After the other members left the course, the professor
> approved that the project is completed by one student who focuses on one subsystem.

## ✅ What the task asked for → where it is

| Requirement | Implementation |
|-------------|----------------|
| ≥ 3 classes per subsystem | **6 classes**: `Building`, `SmartMeter`, `EnergyReading` (`energy_app/domain.py`), `CarbonCalculator`, `EnergyAnalyzer`, `SustainabilityScorer` (`energy_app/analytics.py`) |
| Constructor `__init__` | every class initialises its state, values go through the setters for validation |
| Initialisation / setup methods | `Building.configure_default_meters()`, `SmartMeter.activate()/deactivate()`, `EnergyReading.reset_calculations()`, `EnergyReading.from_dict()`, `CarbonCalculator.configure()` |
| Encapsulation – getters & setters | private attributes (`_name`, `_area_m2`, …) with `@property` getters and `@x.setter` setters that reject invalid values (e.g. negative area) |

## 🏗️ System design – UML class diagram

![Domain classes](docs/uml/1_domain.png)

Requirements of the subsystem: [`docs/requirements.md`](docs/requirements.md)

## 🚀 How to run

Only Python 3.10+ is needed (no extra packages):

```bash
python demo_oop.py
```

The demo creates a university building with its smart meters, uses getters and setters,
shows that invalid values are rejected and calculates CO₂ for a reading.

## 📁 Structure

```
energy_app/domain.py      Building, SmartMeter, EnergyReading, BuildingType, MeterType
energy_app/analytics.py   CarbonCalculator, EnergyAnalyzer, SustainabilityScorer
demo_oop.py               console demo
docs/                     UML diagram + requirements
```

## 🌿 Branches

| Branch | Content |
|--------|---------|
| `Homeassignment1` | OOP classes: constructors, setup methods, getters & setters |
| `HomeworkAssignment2` | Real-time stream pipeline: ABCs, inheritance, operator overloading, iterators & generators |
| `HomeworkAssignment3` | Flask web app + MySQL database + AI coach |
| `HomeworkAssignment4` | Exception handling class + automated tests |
| `main` | Final capstone project |
