"""Integration tests for the Flask app, database, AI coach and error handling
(Hometasks 3 and 4)."""

from types import SimpleNamespace

from energy_app.coach import SustainabilityCoach
from energy_app.errors import (AICoachError, BuildingNotFoundError,
                               EnergySystemError, InvalidReadingError)
from energy_app.models import BuildingModel, ReadingModel


# ---------- pages & API ------------------------------------------------------
def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_dashboard_and_pages_render(client, building):
    for url in [f"/dashboard/{building.id}", "/buildings",
                f"/buildings/{building.id}", f"/coach/{building.id}"]:
        response = client.get(url)
        assert response.status_code == 200, url
    assert b"Test Office" in client.get(f"/dashboard/{building.id}").data


def test_create_building_via_form_stores_meters_and_readings(client, app):
    response = client.post("/buildings", data={"name": "Library", "building_type": "university",
                                               "area_m2": "1200", "city": "Dortmund"})
    assert response.status_code == 302
    row = BuildingModel.query.filter_by(name="Library").one()
    assert len(row.meters) == 5
    assert row.readings.count() > 0


def test_create_building_with_invalid_data_shows_error(client):
    response = client.post("/buildings", data={"name": "Bad", "building_type": "office",
                                               "area_m2": "-5"}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Area must be greater than 0" in response.data
    assert BuildingModel.query.count() == 0


def test_summary_api_returns_score(client, building):
    data = client.get(f"/api/buildings/{building.id}/summary?days=1").get_json()
    assert data["building"] == "Test Office"
    assert data["summary"]["consumption_kwh"] > 0
    assert data["score"]["grade"] in "ABCDE"


def test_ingest_valid_reading_is_stored(client, building):
    meter_id = building.meters[0].id
    before = ReadingModel.query.count()
    response = client.post("/api/readings", json={"meter_id": meter_id, "power_kw": 12.5})
    assert response.status_code == 201
    assert response.get_json()["stored"] == 1
    assert ReadingModel.query.count() == before + 1


def test_live_tick_returns_meter_values(client, building):
    data = client.post(f"/api/buildings/{building.id}/live").get_json()
    assert len(data["meters"]) == 5
    assert data["received"] == 5
    assert "net_load_kw" in data


def test_delete_building_removes_its_readings(client, building):
    client.post(f"/buildings/{building.id}/delete")
    assert BuildingModel.query.count() == 0
    assert ReadingModel.query.count() == 0


# ---------- error handling (Hometask 4) --------------------------------------
def test_unknown_building_returns_json_404_for_api(client):
    response = client.get("/api/buildings/999/summary")
    assert response.status_code == 404
    assert response.get_json()["error"] == "building_not_found"


def test_unknown_building_returns_html_404_for_pages(client):
    response = client.get("/dashboard/999")
    assert response.status_code == 404
    assert b"Building 999 does not exist" in response.data


def test_invalid_reading_is_rejected_with_400(client, building):
    meter_id = building.meters[0].id                   # an HVAC meter
    response = client.post("/api/readings", json={"meter_id": meter_id, "power_kw": -4})
    assert response.status_code == 400
    assert response.get_json()["error"] == "invalid_reading"


def test_reading_for_unknown_meter_and_non_json_body(client, building):
    assert client.post("/api/readings", json={"meter_id": 4242, "power_kw": 1}).status_code == 404
    response = client.post("/api/readings", data="not json")
    assert response.status_code == 400
    assert response.get_json()["error"] == "validation_error"


def test_invalid_days_parameter_is_rejected(client, building):
    response = client.get(f"/api/buildings/{building.id}/summary?days=0")
    assert response.status_code == 400


def test_unexpected_exceptions_return_500_json(app, client):
    @app.get("/api/boom")
    def boom():
        raise RuntimeError("database exploded")
    response = client.get("/api/boom")
    assert response.status_code == 500
    assert response.get_json()["error"] == "internal_error"
    assert "exploded" not in response.get_data(as_text=True)   # no internal details leaked


def test_error_classes_carry_status_codes():
    assert BuildingNotFoundError(5).status_code == 404
    assert BuildingNotFoundError(5).to_dict()["details"] == {"building_id": 5}
    assert issubclass(InvalidReadingError, EnergySystemError)
    assert AICoachError("x").status_code == 503


# ---------- AI Sustainability Coach --------------------------------------------
def test_coach_without_api_key_uses_rules(client, service, building):
    advice = service.ask_coach(building.id, "How can we save energy?")
    assert advice.source == "rules"
    assert "sustainability score" in advice.answer.lower()


class FakeOpenAI:
    """Stands in for the OpenAI client so tests never call the real API."""

    def __init__(self, answer=None, fail=False):
        def create(**kwargs):
            if fail:
                raise ConnectionError("network down")
            self.last_messages = kwargs["messages"]
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer))])
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=create))


def test_coach_uses_openai_answer(service, building):
    fake = FakeOpenAI("- Turn off HVAC at night")
    service.coach = SustainabilityCoach(client=fake)
    advice = service.ask_coach(building.id)
    assert advice.source == "openai"
    assert advice.answer == "- Turn off HVAC at night"
    assert "Test Office" in fake.last_messages[1]["content"]   # real numbers in the prompt


def test_coach_falls_back_when_openai_fails(service, building):
    service.coach = SustainabilityCoach(client=FakeOpenAI(fail=True))
    advice = service.ask_coach(building.id)
    assert advice.source == "rules"
    assert "AI service unavailable" in advice.answer
