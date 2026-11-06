"""
HTTP routes.

pages - HTML pages for people (dashboard, buildings, AI coach)
api   - JSON REST API for IoT devices and the live dashboard
"""

from __future__ import annotations

from flask import (Blueprint, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)

from .domain import BuildingType
from .errors import ValidationError
from .webapp import get_service

pages = Blueprint("pages", __name__)
api = Blueprint("api", __name__, url_prefix="/api")


# ============================== HTML pages ==================================
@pages.route("/")
def index():
    buildings = get_service().list_buildings()
    if not buildings:
        return redirect(url_for("pages.buildings"))
    return redirect(url_for("pages.dashboard", building_id=buildings[0].id))


@pages.route("/dashboard/<int:building_id>")
def dashboard(building_id: int):
    service = get_service()
    days = request.args.get("days", 7, type=int)
    building, summary, score = service.summary(building_id, days)
    return render_template("dashboard.html", building=building, row=service.get_building(building_id),
                           summary=summary, score=score, days=days,
                           buildings=service.list_buildings())


@pages.route("/buildings", methods=["GET", "POST"])
def buildings():
    service = get_service()
    if request.method == "POST":
        form = request.form
        try:
            row = service.create_building(form.get("name", ""), form.get("building_type", ""),
                                          form.get("area_m2") or 0, form.get("city", ""))
        except ValidationError as error:
            flash(error.message, "danger")
        else:
            flash(f"Building '{row.name}' created with {len(row.meters)} smart meters "
                  "and 7 days of simulated history.", "success")
            return redirect(url_for("pages.dashboard", building_id=row.id))
    return render_template("buildings.html", buildings=service.list_buildings(),
                           building_types=[t.value for t in BuildingType])


@pages.route("/buildings/<int:building_id>")
def building_detail(building_id: int):
    service = get_service()
    building, summary, score = service.summary(building_id)
    return render_template("building_detail.html", row=service.get_building(building_id),
                           summary=summary, score=score,
                           readings=service.recent_readings(building_id),
                           pipeline=current_app.extensions["pipeline"])


@pages.route("/buildings/<int:building_id>/delete", methods=["POST"])
def delete_building(building_id: int):
    service = get_service()
    name = service.get_building(building_id).name
    service.delete_building(building_id)
    flash(f"Building '{name}' deleted.", "info")
    return redirect(url_for("pages.buildings"))


@pages.route("/coach/<int:building_id>", methods=["GET", "POST"])
def coach(building_id: int):
    service = get_service()
    if request.method == "POST":
        service.ask_coach(building_id, request.form.get("question"))
        return redirect(url_for("pages.coach", building_id=building_id))
    building, summary, score = service.summary(building_id)
    return render_template("coach.html", row=service.get_building(building_id),
                           score=score, history=service.advice_history(building_id),
                           ai_enabled=current_app.extensions["coach"].is_ai_enabled)


# ================================ JSON API ==================================
@api.get("/health")
def health():
    return jsonify(status="ok")


@api.get("/buildings")
def api_buildings():
    return jsonify([b.to_dict() for b in get_service().list_buildings()])


@api.post("/buildings")
def api_create_building():
    data = request.get_json(silent=True) or {}
    row = get_service().create_building(data.get("name", ""), data.get("building_type", ""),
                                        data.get("area_m2") or 0, data.get("city", ""),
                                        history_days=int(data.get("history_days", 0)))
    return jsonify(row.to_dict()), 201


@api.get("/buildings/<int:building_id>/summary")
def api_summary(building_id: int):
    days = request.args.get("days", 7, type=int)
    building, summary, score = get_service().summary(building_id, days)
    return jsonify(building=building.name, summary=summary.to_dict(), score=score.to_dict())


@api.post("/buildings/<int:building_id>/live")
def api_live(building_id: int):
    return jsonify(get_service().live_tick(building_id))


@api.post("/readings")
def api_ingest():
    payload = request.get_json(silent=True)
    if payload is None:
        raise ValidationError("Request body must be JSON")
    return jsonify(get_service().ingest_json(payload)), 201


@api.get("/pipeline")
def api_pipeline():
    pipeline = current_app.extensions["pipeline"]
    return jsonify(pipeline=repr(pipeline), steps=pipeline.stats())
