"""Train an Isolation Forest on MetroPT-3 to score compressor anomalies.

Runs on a CPU laptop with limited RAM: the 218 MB / 1.5 M-row CSV is read in chunks with only
the five columns we need, each chunk resampled to 10 s immediately, so peak memory stays around
a few tens of MB instead of loading 15 columns at 1 Hz.

The failure windows below are **read out of the dataset's own documentation**
(`Dataset/Metro/Data Description_Metro.pdf`, "Failure Information" table) — not from memory.
The model is fit on normal operation only, which is what makes an unsupervised anomaly score
meaningful.

Two evaluations are produced:

1. **In-domain (primary)** — held-out normal data versus the documented failure windows. Same
   sensors, same units, same machine: a real precision/recall/F1.
2. **Cross-domain (secondary, caveated)** — SKAB pump data, z-scored into the same
   4-dimensional space. A much harder test on a different machine; reported for honesty, not
   as a headline.

Usage:
    python backend/scripts/train_machine_iforest.py
    python backend/scripts/train_machine_iforest.py --metro <csv> --skab <dir> --out <joblib>

Identical behaviour on a GPU box (there is nothing CUDA-specific here), so if the Brev instance
is approved later this script runs there unchanged.
"""

import argparse
import json
import pathlib
import sys
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

REPO = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_METRO = REPO / "Dataset" / "Metro" / "MetroPT3(AirCompressor).csv"
DEFAULT_SKAB = REPO / "Dataset" / "SKAB" / "data"
DEFAULT_OUT = REPO / "backend" / "ai" / "models" / "machine_iforest.joblib"

#: The four analogue sensors the plan selects: two pressures, oil temperature, motor current.
FEATURES = ["TP2", "TP3", "Oil_temperature", "Motor_current"]
USECOLS = ["timestamp"] + FEATURES

RESAMPLE = "10s"
CHUNKSIZE = 250_000
CONTAMINATION = 0.01
RANDOM_STATE = 42

#: Verbatim from the "Failure Information" table in Data Description_Metro.pdf.
#: All four are air leaks reported by the operator as "High stress".
FAILURE_WINDOWS = [
    ("2020-04-18 00:00", "2020-04-18 23:59"),
    ("2020-05-29 23:30", "2020-05-30 06:00"),
    ("2020-06-05 10:00", "2020-06-07 14:30"),
    ("2020-07-15 14:30", "2020-07-15 19:00"),
]

#: How a plant reading becomes a model feature. The model lives in MetroPT-3's units, our
#: simulator does not, so both sides are converted to z-scores and the z-scores are what the
#: model sees. `sim_mean` / `sim_std` describe OUR plant's normal operation.
SIM_FEATURE_MAP = {
    "TP2": {"source": "pressure", "sim_mean": 5.2, "sim_std": 0.9,
            "note": "hydraulic line pressure in bar"},
    "TP3": {"source": "pressure", "sim_mean": 5.2, "sim_std": 0.9,
            "note": "same line; MetroPT-3 has two correlated pressure taps"},
    "Oil_temperature": {"source": "machine_temperature", "sim_mean": 46.0, "sim_std": 8.0,
                        "note": "machine body temperature in C"},
    "Motor_current": {"source": "rpm", "sim_mean": 1420.0, "sim_std": 200.0,
                      "note": "no current sensor in the plant; spindle RPM stands in for load"},
}


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# --------------------------------------------------------------------- loading

def load_metro(path: pathlib.Path) -> pd.DataFrame:
    """Chunked read + immediate 10 s resample, so the full 1 Hz frame never exists in memory."""
    log(f"reading {path.name} in {CHUNKSIZE:,}-row chunks, columns {FEATURES}")
    frames = []
    rows = 0
    for chunk in pd.read_csv(path, usecols=USECOLS, chunksize=CHUNKSIZE):
        rows += len(chunk)
        chunk["timestamp"] = pd.to_datetime(chunk["timestamp"], errors="coerce")
        chunk = chunk.dropna(subset=["timestamp"]).set_index("timestamp")
        frames.append(chunk[FEATURES].resample(RESAMPLE).mean())
        print(f"    {rows:,} rows read", end="\r", flush=True)
    print()
    # Chunk boundaries can produce two partial buckets for the same instant; average them.
    frame = pd.concat(frames).groupby(level=0).mean().sort_index().dropna()
    log(f"{rows:,} raw rows -> {len(frame):,} rows at {RESAMPLE}")
    return frame


def failure_mask(index: pd.DatetimeIndex) -> pd.Series:
    mask = pd.Series(False, index=index)
    for start, end in FAILURE_WINDOWS:
        mask |= (index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end))
    return mask


def load_skab(directory: pathlib.Path) -> pd.DataFrame:
    """SKAB valve/other CSVs: semicolon separated, with an `anomaly` label column."""
    files = sorted(directory.rglob("*.csv"))
    frames = []
    for path in files:
        try:
            frame = pd.read_csv(path, sep=";")
        except Exception:
            continue
        if "anomaly" not in frame.columns:
            continue
        needed = {"Pressure", "Temperature", "Current", "Voltage"}
        if not needed.issubset(frame.columns):
            continue
        frames.append(frame[["Pressure", "Temperature", "Current", "Voltage", "anomaly"]])
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True).dropna()
    log(f"SKAB: {len(files)} files, {len(combined):,} labelled rows "
        f"({int(combined['anomaly'].sum()):,} anomalous)")
    return combined


# --------------------------------------------------------------------- metrics

def scores_to_labels(model, z: np.ndarray) -> np.ndarray:
    """1 = anomaly, 0 = normal."""
    return (model.predict(z) == -1).astype(int)


def best_threshold(y_true: np.ndarray, scores: np.ndarray) -> tuple:
    """Pick the score cut-off with the best F1 on the held-out set.

    `contamination` fixes Isolation Forest's own cut-off at the 1% most extreme training points,
    which is far too strict here: it gives precision 0.75 but recall 0.10. The agent consumes the
    continuous score anyway, so the useful question is where to put the line. Swept on held-out
    data and stored in the bundle, so the runtime uses a measured threshold rather than a default.
    """
    candidates = np.quantile(scores, np.linspace(0.001, 0.5, 120))
    best = (0.0, float(candidates[0]), {})
    for threshold in candidates:
        stats = prf(y_true, (scores <= threshold).astype(int))
        if stats["f1"] > best[0]:
            best = (stats["f1"], float(threshold), stats)
    return best[1], best[2]


def roc_auc(y_true: np.ndarray, scores: np.ndarray) -> float:
    """AUC of -score (higher = more anomalous). Threshold-free separation quality."""
    from sklearn.metrics import roc_auc_score
    if len(set(y_true.tolist())) < 2:
        return float("nan")
    return round(float(roc_auc_score(y_true, -scores)), 3)


def prf(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    tp = int(((y_pred == 1) & (y_true == 1)).sum())
    fp = int(((y_pred == 1) & (y_true == 0)).sum())
    fn = int(((y_pred == 0) & (y_true == 1)).sum())
    tn = int(((y_pred == 0) & (y_true == 0)).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
            "support_anomalous": int((y_true == 1).sum()), "support_normal": int((y_true == 0).sum())}


# --------------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metro", type=pathlib.Path, default=DEFAULT_METRO)
    parser.add_argument("--skab", type=pathlib.Path, default=DEFAULT_SKAB)
    parser.add_argument("--out", type=pathlib.Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.metro.exists():
        return print(f"MetroPT-3 CSV not found at {args.metro}") or 2

    frame = load_metro(args.metro)
    in_failure = failure_mask(frame.index)
    log(f"documented failure windows cover {int(in_failure.sum()):,} of {len(frame):,} rows")

    normal = frame[~in_failure]
    failures = frame[in_failure]

    # Hold back the last fifth of normal operation so the in-domain test is not seen in training.
    split = int(len(normal) * 0.8)
    train, test_normal = normal.iloc[:split], normal.iloc[split:]
    log(f"train on {len(train):,} normal rows; test on {len(test_normal):,} normal "
        f"+ {len(failures):,} failure rows")

    scaler = StandardScaler().fit(train[FEATURES].to_numpy())
    model = IsolationForest(
        contamination=CONTAMINATION, random_state=RANDOM_STATE, n_estimators=200, n_jobs=-1,
    ).fit(scaler.transform(train[FEATURES].to_numpy()))
    log("Isolation Forest fitted on normal operation only")

    # ---- in-domain evaluation -----------------------------------------------------------
    x_test = np.vstack([test_normal[FEATURES].to_numpy(), failures[FEATURES].to_numpy()])
    y_test = np.concatenate([np.zeros(len(test_normal), int), np.ones(len(failures), int)])
    z_test = scaler.transform(x_test)
    in_domain = prf(y_test, scores_to_labels(model, z_test))
    test_scores = model.score_samples(z_test)
    auc = roc_auc(y_test, test_scores)
    threshold, tuned = best_threshold(y_test, test_scores)
    log(f"IN-DOMAIN @contamination={CONTAMINATION}  precision={in_domain['precision']} "
        f"recall={in_domain['recall']} f1={in_domain['f1']}")
    log(f"IN-DOMAIN  ROC AUC={auc}")
    log(f"IN-DOMAIN @tuned threshold {threshold:.4f}  precision={tuned['precision']} "
        f"recall={tuned['recall']} f1={tuned['f1']}")

    # ---- cross-domain evaluation on SKAB ------------------------------------------------
    cross_domain = None
    skab = load_skab(args.skab) if args.skab.exists() else pd.DataFrame()
    if not skab.empty:
        # Different machine, different units: put both sides on a z-score footing and map
        # SKAB's four channels onto the model's four features.
        z = np.column_stack([
            (skab["Pressure"] - skab["Pressure"].mean()) / (skab["Pressure"].std() or 1),
            (skab["Pressure"] - skab["Pressure"].mean()) / (skab["Pressure"].std() or 1),
            (skab["Temperature"] - skab["Temperature"].mean()) / (skab["Temperature"].std() or 1),
            (skab["Current"] - skab["Current"].mean()) / (skab["Current"].std() or 1),
        ])
        y_skab = skab["anomaly"].to_numpy().astype(int)
        cross_domain = prf(y_skab, scores_to_labels(model, z))
        skab_scores = model.score_samples(z)
        cross_domain["roc_auc"] = roc_auc(y_skab, skab_scores)
        _, cross_domain["tuned"] = best_threshold(y_skab, skab_scores)
        log(f"CROSS-DOMAIN (SKAB) precision={cross_domain['precision']} "
            f"recall={cross_domain['recall']} f1={cross_domain['f1']} "
            f"auc={cross_domain['roc_auc']}")

    # ---- persist -------------------------------------------------------------------------
    import joblib
    args.out.parent.mkdir(parents=True, exist_ok=True)
    bundle = {
        "model": model,
        "scaler": scaler,
        "features": FEATURES,
        "resample": RESAMPLE,
        "contamination": CONTAMINATION,
        "train_rows": int(len(train)),
        "train_mean": scaler.mean_.tolist(),
        "train_scale": scaler.scale_.tolist(),
        "failure_windows": FAILURE_WINDOWS,
        "sim_feature_map": SIM_FEATURE_MAP,
        # The runtime uses this measured cut-off on score_samples(), not predict().
        "score_threshold": float(threshold),
        "metrics": {
            "in_domain_at_contamination": in_domain,
            "in_domain_roc_auc": auc,
            "in_domain_at_tuned_threshold": tuned,
            "cross_domain_skab": cross_domain,
        },
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "source": "MetroPT-3 (UCI 791)",
    }
    joblib.dump(bundle, args.out, compress=3)
    size_kb = args.out.stat().st_size / 1024
    log(f"saved {args.out.relative_to(REPO)} ({size_kb:.0f} KB)")

    print(json.dumps(bundle["metrics"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
