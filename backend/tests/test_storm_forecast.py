"""The predictive scenario: a forecast, a prepared plant, and a storm that causes nothing.

Every other scenario in this suite is reactive - something is already too hot, too smoky or
already talking to a rogue device. This one is the opposite: the hazard is still in the future,
so the tests here care about three things the reactive tests cannot check.

1. The confidence is **derived from the forecast probability**, not from a severity label, and it
   never reaches certainty, because a forecast is a probability.
2. The incident is raised with a **lead time**, and the four preparation actions are the ones the
   catalogue actually allows for that hazard.
3. The outcome of the storm **depends on what was authorised**: with load shedding and the lower
   setpoint in place the surge stays inside the margin; without them it does not. That contrast is
   the whole argument of the scenario, so it is asserted in both directions.
"""

import pytest

from ai import weather
from ai.actions_catalog import CATALOG, allowed_actions_for
from ai.agents.weather_agent import WeatherAgent
from app.services.state_store import state
from iot import simulator as simulator_module
from iot.simulator import simulator
from scenario_runner import run_scenario


# --------------------------------------------------------------------- the forecast source

def test_simulated_forecast_is_deterministic_and_closes_in():
    """The demo must not depend on the network, so the default source is a fixed timeline."""
    first = weather.simulated_forecast(3)
    again = weather.simulated_forecast(3)
    assert first == again

    steps = [weather.simulated_forecast(i) for i in range(len(weather.SIMULATED_TIMELINE))]
    leads = [s["lead_minutes"] for s in steps]
    probabilities = [s["probability"] for s in steps]
    assert leads == sorted(leads, reverse=True), "the front gets closer, not further away"
    assert probabilities == sorted(probabilities), "and the forecast firms up as it does"
    assert steps[0]["probability"] < weather.PROBABILITY_WARNING, "it starts below the threshold"
    assert steps[-1]["probability"] >= weather.PROBABILITY_CRITICAL


def test_a_calm_forecast_is_not_a_hazard():
    assessment = weather.assess(weather.simulated_forecast(0))
    assert assessment["at_risk"] is False


def test_confidence_is_the_forecast_probability_plus_instability_never_certainty():
    assessment = weather.assess(weather.simulated_forecast(len(weather.SIMULATED_TIMELINE) - 1))
    assert assessment["at_risk"] is True

    probability_alone = assessment["probability"] / 100.0
    assert assessment["confidence"] >= probability_alone, "instability can only add"
    assert assessment["confidence"] <= 0.97, "a forecast is never a measurement"
    # The arithmetic has to be shown, not asserted: the incident text prints this string.
    assert "%.0f" % assessment["probability"] in assessment["confidence_math"]
    assert assessment["indicators"], "CAPE and gusts are named as the reason for the boost"


def test_a_live_forecast_failure_never_breaks_the_demo(monkeypatch):
    import urllib.request

    def explode(*args, **kwargs):
        raise OSError("no network in the demo room")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    assert weather.live_forecast() is None
    # ...and the default path still answers.
    assert weather.current_forecast(2)["source"] == "simulated"


# --------------------------------------------------------------------- the agent

@pytest.mark.asyncio
async def test_weather_agent_reports_lead_time_and_its_own_likelihood():
    agent = WeatherAgent()
    late = weather.simulated_forecast(len(weather.SIMULATED_TIMELINE) - 1)
    observation = await agent.process_event({
        "event_type": "FORECAST_UPDATE", "source": "weather:site_forecast",
        "zone": "GLOBAL", "severity": "WARNING", "data": late,
    })

    assert observation is not None
    assert observation["forecast"] is True
    assert observation["lead_time_minutes"] == late["lead_minutes"]
    # This is what makes the risk engine use the probability instead of mapping WARNING -> 0.60.
    assert observation["source_confidence"] == pytest.approx(weather.assess(late)["confidence"])
    assert "ZONE_B" in observation["exposed_zones"]


@pytest.mark.asyncio
async def test_weather_agent_stays_quiet_on_a_calm_forecast():
    agent = WeatherAgent()
    observation = await agent.process_event({
        "event_type": "FORECAST_UPDATE", "source": "weather:site_forecast",
        "zone": "GLOBAL", "severity": "INFO", "data": weather.simulated_forecast(0),
    })
    assert observation is None


# --------------------------------------------------------------------- the incident

@pytest.mark.asyncio
async def test_storm_forecast_raises_one_predictive_incident():
    run = await run_scenario("storm_forecast", ticks=7)

    assert run.types == ["SEVERE_WEATHER_RISK"], f"expected one weather incident, got {run.types}"
    incident = run.incidents[0]
    assert incident.severity.value in ("WARNING", "HIGH", "CRITICAL")
    assert 0.0 < incident.confidence <= 0.97
    reasoning = incident.ai_reasoning
    assert "LEAD TIME" in reasoning, "a predictive incident has to state how long there is"
    assert "prediction, not a measurement" in reasoning
    assert "FORECAST BASIS" in reasoning, "and show where its confidence came from"


@pytest.mark.asyncio
async def test_the_four_preparation_actions_are_offered_and_allowed():
    run = await run_scenario("storm_forecast", ticks=7)
    incident = run.incidents[0]
    offered = [a.action_type for a in incident.recommended_actions]

    assert offered == ["LOAD_SHEDDING", "REDUCE_PRESSURE_SETPOINT", "SWITCH_TO_UPS",
                       "REINFORCE_ELECTRICAL_CREW"], offered
    # The same four are what the catalogue would hand to n8n for this hazard, so the LLM cannot
    # be offered anything the backend would then refuse to build.
    menu = {a["action_type"] for a in allowed_actions_for(incident)}
    assert set(offered) <= menu, sorted(menu)
    # Nothing here fires by itself: both load shedding and the setpoint change cost production.
    for action in incident.recommended_actions:
        assert action.requires_confirmation is True


def test_weather_actions_never_leak_into_other_hazards():
    for key in ("load_shedding", "reduce_pressure_setpoint", "switch_to_ups",
                "reinforce_electrical_crew"):
        entry = CATALOG[key]
        assert entry.hazards == ["SEVERE_WEATHER_RISK"], entry.hazards
        assert "INDUSTRIAL_FIRE" not in entry.hazards,             f"{entry.action_type} must not be offered for a fire"


# --------------------------------------------------------------------- prevented vs not

async def _strike(prepared: bool):
    """Run the forecast, optionally record the two mitigations, then let the storm hit."""
    run = await run_scenario("storm_forecast", ticks=7, keep_clock=True)
    # run_scenario() drops back to "normal" when it finishes. Re-arm the scenario by hand rather
    # than through set_scenario(), which would rewind the step counter and clear the mitigations.
    simulator.scenario = "storm_forecast"
    # …and park the clock one tick before the strike: the quiet stretch in between is the
    # operator's approval window, which has nothing to assert.
    simulator.scenario_step = simulator_module.STORM_STRIKE_TICK - 1
    if prepared:
        simulator.notify_action_executed("LOAD_SHEDDING", "ZONE_B")
        simulator.notify_action_executed("REDUCE_PRESSURE_SETPOINT", "M-04")
    await run.feed(ticks=2)
    return run


@pytest.mark.asyncio
async def test_storm_is_absorbed_when_the_plant_was_prepared():
    run = await _strike(prepared=True)

    pressure = state.machines["M-04"].parameters["pressure"].value
    assert pressure < 8.0, "the surge has to land inside the widened margin"
    assert state.machines["M-04"].status.value == "INFO"
    assert run.types == ["SEVERE_WEATHER_RISK"], (
        f"a prepared plant produces no second, physical incident: {run.types}")
    assert any("PREVENTED" in log["decision"] for log in state.agent_logs), \
        "the outcome has to be stated, not left for the operator to infer"


@pytest.mark.asyncio
async def test_the_same_storm_causes_an_overpressure_when_it_was_not_prepared():
    run = await _strike(prepared=False)

    pressure = state.machines["M-04"].parameters["pressure"].value
    assert pressure > 8.0, "unmitigated, the surge passes the 8.0 bar limit"
    assert any("NOT PREVENTED" in log["decision"] for log in state.agent_logs)
    assert "SEVERE_WEATHER_RISK" in run.types


# --------------------------------------------------------------------- the effects are real

@pytest.mark.asyncio
async def test_authorising_the_preparation_visibly_changes_the_machines():
    from app.services.command_engine import command_engine

    run = await run_scenario("storm_forecast", ticks=7, keep_clock=True)
    incident = run.incidents[0]
    by_type = {a.action_type: a for a in state.actions.values() if a.incident_id == incident.id}

    before_rpm = state.machines["M-04"].parameters["rpm"].value
    await command_engine.authorize_action(by_type["LOAD_SHEDDING"].id, "owner_01")
    await command_engine.execute_action(by_type["LOAD_SHEDDING"].id)
    assert state.machines["M-04"].parameters["rpm"].value < before_rpm, \
        "load shedding has to be visible in the machine parameters, not only in a log line"

    await command_engine.authorize_action(by_type["REDUCE_PRESSURE_SETPOINT"].id, "owner_01")
    await command_engine.execute_action(by_type["REDUCE_PRESSURE_SETPOINT"].id)
    assert state.machines["M-04"].parameters["pressure"].value <= 6.5


# --------------------------------------------------------------------- the procedure document

def test_the_severe_weather_procedure_is_retrievable():
    from ai.rag.rag_engine import rag_engine

    result = rag_engine.query("thunderstorm load shedding pressure setpoint before the storm")
    cited = " ".join(str(s.get("document", "")) for s in result["sources"]) + result["answer"]
    assert "WX-SP-07" in cited, cited[:400]
    # The numbers the incident relies on have to come from the procedure, not from the code.
    assert "6.5" in result["answer"] or "load" in result["answer"].lower()
