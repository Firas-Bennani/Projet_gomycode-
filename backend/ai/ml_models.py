"""Runtime access to the trained models, with silent fallback when they are absent.

**Design rule: the models annotate, the deterministic rules decide.** A model score never
creates and never suppresses an alarm. It adds a second opinion, names the most deviant
channel, and helps prioritise. That way a model regression, a missing file, or a feature the
plant cannot supply can degrade the *explanation* but never the *detection* — which is the only
version of this a safety reviewer would accept.

Both models were trained on public datasets whose units are not ours, so every plant reading is
converted to a **z-score** against our own normal operating range before it reaches a model. The
mapping lives in the model bundle (`sim_feature_map`), written by the training script, so the
runtime cannot silently disagree with training.

If a `.joblib` is missing the loader returns ``None`` once, logs it at INFO, and every caller
falls back to rules with no further noise.
"""

import logging
import pathlib
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ml_models")

MODEL_DIR = pathlib.Path(__file__).resolve().parent / "models"
MACHINE_MODEL_PATH = MODEL_DIR / "machine_iforest.joblib"
SMOKE_MODEL_PATH = MODEL_DIR / "smoke_rf.joblib"

# None = not tried yet, False = tried and unavailable, dict = loaded bundle.
_cache: Dict[str, Any] = {}


def _load(key: str, path: pathlib.Path) -> Optional[Dict[str, Any]]:
    if key in _cache:
        return _cache[key] or None
    bundle = None
    try:
        if path.exists():
            import joblib
            bundle = joblib.load(path)
            logger.info("Loaded %s (trained %s)", path.name, bundle.get("trained_at", "unknown"))
        else:
            logger.info("%s not present — %s falls back to rules.", path.name, key)
    except Exception as exc:  # noqa: BLE001 - a bad model file must never break detection
        logger.warning("Could not load %s (%s). Falling back to rules.", path.name, exc)
        bundle = None
    _cache[key] = bundle or False
    return bundle


def machine_bundle() -> Optional[Dict[str, Any]]:
    return _load("machine_iforest", MACHINE_MODEL_PATH)


def smoke_bundle() -> Optional[Dict[str, Any]]:
    return _load("smoke_rf", SMOKE_MODEL_PATH)


def reset_cache() -> None:
    """Forget what was loaded — used by tests that simulate a missing model."""
    _cache.clear()


def available() -> Dict[str, bool]:
    return {"machine_iforest": machine_bundle() is not None,
            "smoke_rf": smoke_bundle() is not None}


# --------------------------------------------------------------------- machine anomaly

def _z(value: float, spec: Dict[str, Any]) -> float:
    std = float(spec.get("sim_std") or 1.0) or 1.0
    return (float(value) - float(spec.get("sim_mean", 0.0))) / std


def machine_anomaly(pressure: float, machine_temperature: float, rpm: float) -> Optional[Dict[str, Any]]:
    """Isolation Forest score for one machine sample, or ``None`` if unavailable.

    Returns ``anomaly_score`` (lower = more anomalous, the raw ``score_samples`` value),
    ``is_anomaly`` against the threshold measured during training, and the channel furthest from
    our normal range.
    """
    bundle = machine_bundle()
    if not bundle:
        return None
    try:
        import numpy as np

        sources = {"pressure": pressure, "machine_temperature": machine_temperature, "rpm": rpm}
        feature_map = bundle.get("sim_feature_map", {})
        features: List[str] = bundle.get("features", [])
        z_values = []
        for feature in features:
            spec = feature_map.get(feature)
            if spec is None or spec.get("source") not in sources:
                return None            # a feature we cannot supply: stay silent, use the rules
            z_values.append(_z(sources[spec["source"]], spec))

        z = np.asarray([z_values], dtype=float)
        score = float(bundle["model"].score_samples(z)[0])
        threshold = float(bundle.get("score_threshold", -0.5))

        # Which channel is furthest from normal? Report the plant-side name, not the dataset's.
        worst_index = int(np.argmax(np.abs(z[0])))
        worst_feature = features[worst_index]
        worst_source = feature_map.get(worst_feature, {}).get("source", worst_feature)

        return {
            "anomaly_score": round(score, 4),
            "score_threshold": round(threshold, 4),
            "is_anomaly": score <= threshold,
            "most_deviant_feature": worst_source,
            "most_deviant_z": round(float(z[0][worst_index]), 2),
            "model": "IsolationForest/MetroPT-3",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("machine_anomaly failed (%s); using rules only.", exc)
        return None


# --------------------------------------------------------------------- smoke probability

def smoke_probability(smoke_ppm: float, temperature: Optional[float]) -> Optional[Dict[str, Any]]:
    """RandomForest probability that this looks like a real fire alarm, or ``None``.

    Needs an ambient temperature as well as the particulate reading; without one there is
    nothing to say and the caller keeps its rule-based verdict.
    """
    bundle = smoke_bundle()
    if not bundle or temperature is None:
        return None
    try:
        import numpy as np

        sources = {"smoke": smoke_ppm, "temperature": temperature}
        feature_map = bundle.get("sim_feature_map", {})
        z_values = []
        for feature in bundle.get("features", []):
            spec = feature_map.get(feature)
            if spec is None or spec.get("source") not in sources:
                return None
            z_values.append(_z(sources[spec["source"]], spec))

        probability = float(bundle["model"].predict_proba(np.asarray([z_values], dtype=float))[0][1])
        return {
            "smoke_probability": round(probability, 3),
            "model": "RandomForest/Smoke-IoT",
            "inputs": {"smoke_ppm": smoke_ppm, "temperature": temperature},
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("smoke_probability failed (%s); using rules only.", exc)
        return None
