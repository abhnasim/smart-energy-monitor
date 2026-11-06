"""
AI Sustainability Coach.

Uses the OpenAI API to turn the building's numbers into concrete advice.
If no API key is configured (or the API fails) a rule-based coach answers
instead, so the application always works - also offline during a demo.
"""

from __future__ import annotations

from .analytics import EnergySummary, SustainabilityScore
from .domain import Building
from .errors import AICoachError

SYSTEM_PROMPT = (
    "You are an energy-efficiency and sustainability coach for buildings. "
    "You get monitoring data of one building. Give 3 to 5 concrete, practical "
    "recommendations that reduce energy use, cost and CO2 while keeping comfort. "
    "Refer to the numbers. Answer in plain text, one recommendation per line "
    "starting with '- ', at most 180 words."
)


class SustainabilityCoach:
    """Gives energy-saving advice with OpenAI, falling back to rules."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini",
                 client=None) -> None:
        self._api_key = api_key or None
        self._model = model
        self._client = client          # can be injected (useful for tests)

    # ---- getters & setters ------------------------------------------------
    @property
    def model(self) -> str:
        return self._model

    @model.setter
    def model(self, value: str) -> None:
        if not value:
            raise ValueError("Model name must not be empty")
        self._model = value

    @property
    def is_ai_enabled(self) -> bool:
        return bool(self._api_key or self._client)

    # ---- prompt -----------------------------------------------------------
    @staticmethod
    def build_context(building: Building, summary: EnergySummary,
                      score: SustainabilityScore) -> str:
        return (
            f"Building: {building.name} ({building.building_type.value}, "
            f"{building.area_m2:.0f} m², {building.city})\n"
            f"Period: last {summary.days:g} days\n"
            f"Consumption: {summary.consumption_kwh:.0f} kWh, own solar: "
            f"{summary.solar_kwh:.0f} kWh ({summary.renewable_share:.0%} of consumption)\n"
            f"Net grid energy: {summary.net_grid_kwh:.0f} kWh, cost {summary.cost_eur:.0f} EUR, "
            f"CO2 {summary.carbon_kg:.0f} kg\n"
            f"Share used in peak-tariff hours: {summary.peak_share:.0%}\n"
            f"Consumption by meter type (kWh): {summary.by_type_kwh}\n"
            f"Energy intensity: {score.intensity_kwh_m2_year:.0f} kWh/m²/year "
            f"(benchmark {score.benchmark_kwh_m2_year:.0f})\n"
            f"Sustainability score: {score.total:.0f}/100, grade {score.grade}"
        )

    # ---- main entry point -------------------------------------------------
    def advise(self, building: Building, summary: EnergySummary,
               score: SustainabilityScore, question: str | None = None) -> tuple[str, str]:
        """Return (answer, source). Raises AICoachError if OpenAI fails."""
        if not self.is_ai_enabled:
            return self.rule_based_advice(summary, score), "rules"

        context = self.build_context(building, summary, score)
        user_message = context + "\n\n" + (
            f"Question from the facility manager: {question}" if question
            else "What should we do next to improve?")
        try:
            client = self._client or self._create_client()
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": user_message}],
            )
            answer = (response.choices[0].message.content or "").strip()
        except Exception as error:      # network, auth, quota ...
            raise AICoachError(f"OpenAI request failed: {error}") from error
        if not answer:
            raise AICoachError("OpenAI returned an empty answer")
        return answer, "openai"

    def _create_client(self):
        from openai import OpenAI      # imported lazily: only needed with a key
        return OpenAI(api_key=self._api_key, timeout=30)

    # ---- offline fallback ---------------------------------------------------
    @staticmethod
    def rule_based_advice(summary: EnergySummary, score: SustainabilityScore) -> str:
        tips = []
        ratio = score.intensity_kwh_m2_year / score.benchmark_kwh_m2_year
        if ratio > 0.9:
            tips.append(
                f"- Energy intensity is {score.intensity_kwh_m2_year:.0f} kWh/m²/year "
                f"({ratio:.0%} of the {score.benchmark_kwh_m2_year:.0f} benchmark). "
                "Lower heating set-points by 1 °C "
                "(about 6 % less heating energy) and switch HVAC to night set-back.")
        hvac = summary.by_type_kwh.get("hvac", 0)
        if summary.consumption_kwh and hvac / summary.consumption_kwh > 0.5:
            tips.append(f"- HVAC uses {hvac / summary.consumption_kwh:.0%} of the energy. "
                        "Check schedules so it is off when rooms are empty.")
        if summary.peak_share > 0.15:
            tips.append(f"- {summary.peak_share:.0%} of consumption falls in the expensive "
                        "17:00-21:00 peak. Shift flexible loads (dishwashers, EV charging, "
                        "pre-heating) earlier and discharge the battery during the peak.")
        if summary.renewable_share < 0.3:
            tips.append(f"- Own solar covers only {summary.renewable_share:.0%} of consumption. "
                        "Consider extending the PV system or buying certified green electricity.")
        lighting = summary.by_type_kwh.get("lighting", 0)
        if summary.consumption_kwh and lighting / summary.consumption_kwh > 0.2:
            tips.append("- Lighting is a large share. Replace remaining lamps with LEDs and "
                        "add presence sensors in corridors and meeting rooms.")
        if not tips:
            tips.append("- Great work: the building performs better than the benchmark. "
                        "Keep monitoring and review the peak-hour schedule monthly.")
        tips.append(f"- Current sustainability score: {score.total:.0f}/100 (grade {score.grade}).")
        return "\n".join(tips)
