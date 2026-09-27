"""Train a smoke / fire-alarm classifier on the Kaggle Smoke Detection IoT dataset.

Two models are trained deliberately:

1. **full** — every sensor channel in the dataset. Trained only to show what the data supports;
   our plant does not have a TVOC, eCO2, H2 or particle-count sensor, so this model could never
   run here.
2. **deployable** — only the channels our plant actually publishes: an ambient temperature and a
   smoke reading. This is the one that gets saved and used, because a model that needs features
   the plant does not have is worse than useless: it is a model that silently never runs.

Reporting both makes the gap explicit rather than quietly shipping the optimistic number.

Usage:
    python backend/scripts/train_smoke.py
    python backend/scripts/train_smoke.py --csv <path> --out <joblib>
"""

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import precision_recall_fscore_support, roc_auc_score
from sklearn.model_selection import train_test_split

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_CSV = REPO / "Dataset" / "smoke_detection_iot.csv"
DEFAULT_OUT = REPO / "backend" / "ai" / "models" / "smoke_rf.joblib"

TARGET = "Fire Alarm"

#: Everything the dataset offers.
FULL_FEATURES = [
    "Temperature[C]", "Humidity[%]", "TVOC[ppb]", "eCO2[ppm]", "Raw H2", "Raw Ethanol",
    "Pressure[hPa]", "PM1.0", "PM2.5", "NC0.5", "NC1.0", "NC2.5",
]

#: What our plant can actually supply. TEMP-B-01 gives °C; SMOKE-B-01 gives a particulate
#: reading in ppm which stands in for PM2.5. Both are z-scored before they reach the model,
#: because the units do not match the dataset's.
DEPLOY_FEATURES = ["Temperature[C]", "PM2.5"]

SIM_FEATURE_MAP = {
    "Temperature[C]": {"source": "temperature", "sim_mean": 25.5, "sim_std": 6.0,
                       "note": "ambient zone temperature from TEMP-B-01, in C"},
    "PM2.5": {"source": "smoke", "sim_mean": 8.0, "sim_std": 12.0,
              "note": "SMOKE-B-01 particulate reading in ppm, standing in for PM2.5"},
}

RANDOM_STATE = 42


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def evaluate(model, x_test, y_test) -> dict:
    predictions = model.predict(x_test)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, predictions, average="binary", zero_division=0)
    try:
        auc = round(float(roc_auc_score(y_test, model.predict_proba(x_test)[:, 1])), 3)
    except Exception:
        auc = float("nan")
    return {
        "precision": round(float(precision), 3),
        "recall": round(float(recall), 3),
        "f1": round(float(f1), 3),
        "roc_auc": auc,
        "support_positive": int((y_test == 1).sum()),
        "support_negative": int((y_test == 0).sum()),
    }


def zscore(frame: pd.DataFrame, columns) -> np.ndarray:
    """Z-score within the dataset, so the model is unit-agnostic and our plant can feed it."""
    out = []
    stats = {}
    for column in columns:
        mean = float(frame[column].mean())
        std = float(frame[column].std()) or 1.0
        stats[column] = {"mean": mean, "std": std}
        out.append((frame[column] - mean) / std)
    return np.column_stack(out), stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=pathlib.Path, default=DEFAULT_CSV)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"smoke CSV not found at {args.csv}")
        return 2

    frame = pd.read_csv(args.csv)
    missing = [c for c in FULL_FEATURES + [TARGET] if c not in frame.columns]
    if missing:
        print(f"columns missing from the CSV: {missing}")
        return 2
    frame = frame[FULL_FEATURES + [TARGET]].dropna()
    y = frame[TARGET].astype(int).to_numpy()
    log(f"{len(frame):,} rows, {int(y.sum()):,} positive ({y.mean() * 100:.1f}% alarm)")

    results = {}
    bundle_parts = {}

    for name, features in (("full", FULL_FEATURES), ("deployable", DEPLOY_FEATURES)):
        x, stats = zscore(frame, features)
        x_train, x_test, y_train, y_test = train_test_split(
            x, y, test_size=0.25, random_state=RANDOM_STATE, stratify=y)
        model = RandomForestClassifier(
            n_estimators=120, max_depth=12, random_state=RANDOM_STATE, n_jobs=-1,
            class_weight="balanced_subsample",
        ).fit(x_train, y_train)
        results[name] = evaluate(model, x_test, y_test)
        log(f"{name:<11} features={len(features):<2} precision={results[name]['precision']} "
            f"recall={results[name]['recall']} f1={results[name]['f1']} "
            f"auc={results[name]['roc_auc']}")
        if name == "deployable":
            bundle_parts = {"model": model, "features": features, "zscore_stats": stats,
                            "importances": dict(zip(features, [round(float(v), 3)
                                                               for v in model.feature_importances_]))}

    import joblib
    args.out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        **bundle_parts,
        "sim_feature_map": SIM_FEATURE_MAP,
        "metrics": results,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "Kaggle Smoke Detection IoT (deepcontractor)",
        "note": "Only the deployable model is saved: the full-feature model needs sensors the "
                "plant does not have.",
    }, args.out, compress=3)
    log(f"saved {args.out.relative_to(REPO)} ({args.out.stat().st_size / 1024:.0f} KB), "
        f"deployable features {DEPLOY_FEATURES}")

    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
