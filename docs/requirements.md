# Requirements – Real-Time Energy Monitoring & Sustainability Analytics

Topic: **AI-Powered Smart Energy Management System**
Subsystem: **Real-Time Energy Monitoring & Sustainability Analytics**

## Functional requirements

| ID | Requirement | Implemented in |
|----|-------------|----------------|
| FR1 | The user can register a building (office, university or home) with name, area and city, and delete it. | `Building`, `EnergyService.create_building`, `/buildings` |
| FR2 | The system automatically installs a default set of smart meters (HVAC, lighting, plug loads, solar, battery) for every new building. | `Building.configure_default_meters` |
| FR3 | The system accepts smart-meter readings in real time through a REST API (one reading or a batch in JSON). | `POST /api/readings`, `EnergyService.ingest_json` |
| FR4 | Readings from inactive/offline meters and sub-threshold readings (noise, standby, solar at night) are filtered out before storage. | `InactiveMeterFilter`, `ThresholdFilter` |
| FR5 | Every valid reading is transformed into energy (kWh), CO₂ equivalent (kg), cost (€) and a peak-tariff flag. | `EnergyConverter`, `CarbonTransformer`, `PeakTariffFlagger` |
| FR6 | All buildings, meters, processed readings and AI advice are stored in a relational database (MySQL; SQLite for development). | `models.py` |
| FR7 | The dashboard shows consumption, own solar production, net cost, savings against a benchmark baseline and CO₂ reduction for 1, 7 or 30 days, with charts. | `EnergyAnalyzer`, `dashboard.html` |
| FR8 | A live monitoring view shows the current power of each meter and the net grid load of the building, updated every 3 seconds. | `LoadBalanceTracker`, `POST /api/buildings/<id>/live` |
| FR9 | The system calculates a sustainability score (0–100) and grade (A–E) per building, with a breakdown of efficiency, renewable share and peak-hour usage. | `SustainabilityScorer` |
| FR10 | An AI Sustainability Coach (OpenAI API) gives building-specific recommendations, answers free-text questions and keeps a history of its advice. | `SustainabilityCoach`, `/coach/<id>` |

## Non-functional requirements

| ID | Category | Requirement | How it is verified |
|----|----------|-------------|--------------------|
| NFR1 | Usability | All key figures of a building are visible on one dashboard screen without training; units are always shown. | Demo / screenshots |
| NFR2 | Performance | The dashboard renders in under 1 s for one week of hourly data; a live tick is processed in under 300 ms. | Measured: ≈ 12 ms dashboard, ≈ 7 ms live tick (local) |
| NFR3 | Reliability | If the OpenAI API is unavailable or no key is configured, the application keeps working with a rule-based coach. | `test_coach_falls_back_when_openai_fails` |
| NFR4 | Robustness | Invalid input never crashes the application; errors return a correct HTTP status and a consistent JSON body (API) or a friendly page (browser). | `ErrorHandler`, 7 error-handling tests |
| NFR5 | Maintainability | Layered architecture (domain → pipeline → analytics → service → web), PEP 8 style, docstrings in every module. | Code review, UML |
| NFR6 | Testability | At least 15 automated tests run with one command (`pytest`); external services (OpenAI) are replaced by fakes in tests. | 40 tests, 93 % coverage |
| NFR7 | Portability | Runs with Docker Compose (Flask + MySQL) or locally with SQLite without code changes – only `DATABASE_URL` changes. | `docker-compose.yml`, `.env.example` |
| NFR8 | Security | Secrets (API key, DB password) only in environment variables / `.env` (git-ignored); database access only through the ORM (no SQL injection); internal error details are never shown to users. | `.gitignore`, `test_unexpected_exceptions_return_500_json` |
| NFR9 | Extensibility | A new processing step is one new subclass of `FilterProcessor` / `TransformProcessor` and is plugged in with the `\|` operator. | `pipeline.py` |
| NFR10 | Availability | Front-end libraries (Bootstrap, Chart.js) are bundled locally, so the dashboard works without internet access (only the AI coach needs it). | `static/vendor/` |

## Data management

* **Storage:** relational database with 4 tables – `buildings`, `meters`, `readings`, `coach_advice` (see `docs/uml/5_database.png`).
* **Access:** Flask-SQLAlchemy ORM; `to_domain()` / `from_domain()` convert between database rows and domain objects.
* **Flow:** meter → stream pipeline (filter + transform) → database → analytics → dashboard / AI coach.
* **Data types:** readings are time series (`timestamp`, `power_kw` float) with derived values (`energy_kwh`, `carbon_kg`, `cost_eur` float, `is_peak` bool).

## Assumptions used in the calculations

* Grid emission factor: 0.380 kg CO₂/kWh (approximate German electricity mix, configurable).
* Tariff: 0.30 €/kWh, peak tariff 0.42 €/kWh between 17:00 and 21:00 (configurable).
* Benchmarks (electricity, kWh/m²/year): office 150, university 180, home 120 – illustrative values.
* Baseline = benchmark × area × days / 365. Savings = baseline − net grid energy.
