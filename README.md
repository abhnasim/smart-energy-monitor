# ⚡ AI-Powered Smart Energy Management System

**Subsystem: Real-Time Energy Monitoring & Sustainability Analytics** · Python course, FH Dortmund

## Hometask 3 – Web APIs & Database Access Layers

🎥 **Video presentation (3–5 min):** [watch here](PASTE_YOUR_VIDEO_LINK_HERE)

A **Flask** web application with a **MySQL** database. Smart-meter readings go through the stream
pipeline from Hometask 2 and are stored in MySQL; the dashboard reads them back for analysis.

## 👤 Team overview

| Member | Role | Subsystem |
|--------|------|-----------|
| **Nasim Abhari** (matr. no. 7226039) | Developer, architect, tester – all roles | Real-Time Energy Monitoring & Sustainability Analytics |

> The group originally had four members. After the other members left the course, the professor
> approved that the project is completed by one student who focuses on one subsystem.

![Dashboard](docs/screenshots/dashboard_top.png)

## ✅ What is included

| Part | Implementation |
|------|----------------|
| Web framework | Flask with blueprints (`energy_app/routes.py`), application factory (`energy_app/webapp.py`) |
| Database | **MySQL 8** via Docker Compose (Flask-SQLAlchemy + PyMySQL); SQLite automatically for local development |
| Data access layer | `energy_app/models.py` – tables `buildings`, `meters`, `readings`, `coach_advice`; `to_domain()` / `from_domain()` convert rows ↔ domain objects |
| Service layer | `energy_app/services.py` – `EnergyService` (create buildings, ingest readings, summaries, live tick) |
| Data output | Dashboard with KPIs and Chart.js charts, building details, JSON REST API |
| AI | `energy_app/coach.py` – AI Sustainability Coach using the OpenAI API (rule-based fallback without key) |

## 🚀 How to start

### With MySQL (Docker)

```bash
docker compose up --build
```

Open http://localhost:5000

### Locally with SQLite (no Docker needed)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000 – three demo buildings with 7 days of data are created automatically.

To use your own MySQL server instead, set in `.env`:
`DATABASE_URL=mysql+pymysql://USER:PASSWORD@localhost:3306/energy`

## 🔌 REST API

| Method | URL | Description |
|--------|-----|-------------|
| GET | `/api/health` | health check |
| GET | `/api/buildings` | all buildings with meters |
| POST | `/api/buildings` | create a building |
| GET | `/api/buildings/<id>/summary?days=7` | KPIs + sustainability score |
| POST | `/api/buildings/<id>/live` | one real-time tick |
| POST | `/api/readings` | ingest readings from IoT meters |

## 🏗️ System design

### Web, database & AI classes

![Web classes](docs/uml/3_web.png)

### Database schema

![Database](docs/uml/5_database.png)

### Architecture

![Architecture](docs/uml/4_architecture.png)

Earlier diagrams: [domain](docs/uml/1_domain.png) · [pipeline](docs/uml/2_pipeline.png)

## 🌿 Branches

| Branch | Content |
|--------|---------|
| `HomeworkAssignment1` | OOP classes: constructors, setup methods, getters & setters |
| `HomeworkAssignment2` | Real-time stream pipeline: ABCs, inheritance, operator overloading, iterators & generators |
| `HomeworkAssignment3` | Flask web app + MySQL database + AI coach |
| `HomeworkAssignment4` | Exception handling class + automated tests |
| `main` | Final capstone project |
