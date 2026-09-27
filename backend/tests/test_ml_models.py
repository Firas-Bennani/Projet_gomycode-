"""Tests for the Step 6 model integration.

The property that matters most: **the models annotate, the rules decide.** With the models
present the observation gains a score and a most-deviant channel; with the models gone the
detection is byte-for-byte the same and nothing complains.
"""

import pathlib

import pytest

from ai import ml_models


@pytest.fixture(autouse=True)
def fresh_cache():
    ml_models.reset_cache()
    yield
    ml_models.reset_cache()


MODELS_PRESENT = ml_models.MACHINE_MODEL_PATH.exists() and ml_models.SMOKE_MODEL_PATH.exists()
needs_models = pytest.mark.skipif(not MODELS_PRESENT, reason="trained models not present")


# --------------------------------------------------------------------- loading

def test_available_reports_both_models():
    status = ml_models.available()
    assert set(status) == {"machine_iforest", "smoke_rf"}
    assert status["machine_iforest"] == ml_models.MACHINE_MODEL_PATH.exists()


def test_a_missing_model_is_silent_and_cached(monkeypatch, caplog):
    monkeypatch.setattr(ml_models, "MACHINE_MODEL_PATH", pathlib.Path("does/not/exist.joblib"))
    ml_models.reset_cache()
    assert ml_models.machine_bundle() is None
    assert ml_models.machine_anomaly(8.9, 84.0, 1420.0) is None
    # Second call must not retry the filesystem: the absence is cached.
    assert ml_models.machine_bundle() is None


def test_a_corrupt_model_file_does_not_raise(monkeypatch, tmp_path):
    bad = tmp_path / "broken.joblib"
    bad.write_bytes(b"not a joblib file at all")
    monkeypatch.setattr(ml_models, "MACHINE_MODEL_PATH", bad)
    ml_models.reset_cache()
    assert ml_models.machine_bundle() is None
    assert ml_models.machine_anomaly(8.9, 84.0, 1420.0) is None


# --------------------------------------------------------------------- machine model

@needs_models
def test_machine_anomaly_returns_a_score_and_the_worst_channel():
    result = ml_models.machine_anomaly(pressure=8.9, machine_temperature=88.0, rpm=1420.0)
    assert result is not None
    assert isinstance(result["anomaly_score"], float)
    assert isinstance(result["is_anomaly"], bool)
    assert result["most_deviant_feature"] in ("pressure", "machine_temperature", "rpm")
    assert "IsolationForest" in result["model"]


@needs_models
def test_a_badly_overpressured_sample_scores_worse_than_a_nominal_one():
    nominal = ml_models.machine_anomaly(pressure=5.2, machine_temperature=46.0, rpm=1420.0)
    faulted = ml_models.machine_anomaly(pressure=8.9, machine_temperature=92.0, rpm=1420.0)
    assert faulted["anomaly_score"] < nominal["anomaly_score"], \
        "a compressor well outside its envelope must score as more anomalous"


@needs_models
def test_the_most_deviant_channel_is_the_one_we_pushed():
    result = ml_models.machine_anomaly(pressure=5.2, machine_temperature=110.0, rpm=1420.0)
    assert result["most_deviant_feature"] == "machine_temperature"
    assert result["most_deviant_z"] > 3.0


# --------------------------------------------------------------------- smoke model

@needs_models
def test_smoke_probability_needs_a_temperature():
    assert ml_models.smoke_probability(smoke_ppm=75.0, temperature=None) is None
    assert ml_models.smoke_probability(smoke_ppm=75.0, temperature=58.0) is not None


@needs_models
def test_smoke_probability_is_a_probability():
    result = ml_models.smoke_probability(smoke_ppm=75.0, temperature=58.0)
    assert 0.0 <= result["smoke_probability"] <= 1.0
    assert "RandomForest" in result["model"]


# --------------------------------------------------------------------- agent integration

@pytest.mark.asyncio
@needs_models
async def test_machine_agent_reports_the_model_score_in_its_observation():
    from ai.agents.machine_agent import MachineAgent

    agent = MachineAgent()
    observation = await agent.process_event({
        "event_type": "MACHINE_STATUS", "zone": "ZONE_B",
        "data": {"machine_id": "M-04", "zone": "ZONE_B", "parameters": {
            "pressure": {"value": 8.9}, "temperature": {"value": 88.0},
            "vibration": {"value": 6.1}, "rpm": {"value": 1420}}},
    })
    assert observation is not None
    assert observation["anomaly_score"] is not None
    assert observation["most_deviant_feature"] is not None
    assert "Isolation Forest" in observation["observation"]
    assert "sigma" in observation["observation"]


@pytest.mark.asyncio
async def test_machine_agent_detects_identically_without_the_models(monkeypatch):
    """The regression guard: pulling the models must not change what is detected."""
    from ai.agents.machine_agent import MachineAgent

    event = {
        "event_type": "MACHINE_STATUS", "zone": "ZONE_B",
        "data": {"machine_id": "M-04", "zone": "ZONE_B", "parameters": {
            "pressure": {"value": 8.9}, "temperature": {"value": 88.0},
            "vibration": {"value": 6.1}, "rpm": {"value": 1420}}},
    }

    monkeypatch.setattr(ml_models, "MACHINE_MODEL_PATH", pathlib.Path("no/such/model.joblib"))
    ml_models.reset_cache()
    without = await MachineAgent().process_event(event)

    assert without is not None
    assert without["severity"] == "CRITICAL"
    assert without["anomaly_score"] is None
    assert "Isolation Forest" not in without["observation"]
    assert without["failing_parameters"], "the rules must still explain themselves"


@pytest.mark.asyncio
@needs_models
async def test_the_smoke_classifier_is_not_wired_into_the_fire_path():
    """Deliberate: the Kaggle label is not physically transferable to our smoke sensor.

    Every intuitive fire indicator in that dataset is negatively correlated with its
    "Fire Alarm" label (PM2.5 -0.085, TVOC -0.215, temperature -0.164; mean PM2.5 is 78 when
    alarm=1 and 450 when alarm=0). Wired up, it reported 0% for 75 ppm of smoke in a hot zone.
    A confidently wrong number on an incident card is worse than no number, so the fire path
    stays on the FIRE-EP-03 rules. See docs/ai/METRICS.md §4.2.
    """
    from ai.agents.temperature_agent import TemperatureAgent
    from app.services.state_store import state

    state.initialize_state()
    state.sensors["TEMP-B-01"].current_value = 58.0

    observation = await TemperatureAgent().process_event({
        "event_type": "SENSOR_READING", "zone": "ZONE_B",
        "data": {"sensor_id": "SMOKE-B-01", "type": "smoke", "value": 75.0,
                 "unit": "ppm", "zone": "ZONE_B"},
    })
    assert observation is not None
    assert observation["severity"] == "CRITICAL", "the rules must still call this critical"
    assert observation["smoke_probability"] is None
    assert "RandomForest" not in observation["observation"]
    state.initialize_state()


@needs_models
def test_the_rejected_smoke_model_is_still_loadable_for_the_record():
    """It stays in the repo with its metrics; it is simply not consulted at runtime."""
    result = ml_models.smoke_probability(smoke_ppm=75.0, temperature=58.0)
    assert result is not None and 0.0 <= result["smoke_probability"] <= 1.0


@pytest.mark.asyncio
async def test_scenarios_still_produce_the_same_incident_types_with_models_loaded():
    """Belt and braces: the models must not have changed detection outcomes."""
    from scenario_runner import run_scenario

    assert (await run_scenario("machine_overheating", ticks=12)).types == ["MACHINE_OVERHEATING"]
    assert (await run_scenario("fire", ticks=12)).types == ["INDUSTRIAL_FIRE"]
    assert (await run_scenario("normal", ticks=20)).types == []
