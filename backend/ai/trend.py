"""Trend maths shared by the sensor agents.

Two problems this module fixes.

1. **Slope was first-vs-last over a 2 s buffer.** A single noisy sample produced
   "+38.4 °C/min" for a calm ramp. We now use a least-squares regression over the whole
   window and refuse to report a slope until the window actually spans
   :data:`MIN_TREND_SPAN_S` seconds. An unknown slope is ``None`` — never a silent 0.0
   that later gets printed as a fact.

2. **The demo simulator compresses time.** One simulator tick (1 real second) represents
   one *minute* of plant time: the overheating scenario takes a compressor from 26 °C to
   53 °C in 8 ticks. Reported per real second that is ~160 °C/min, which is physically
   absurd and destroys credibility in front of a jury. :data:`DEMO_TIME_SCALE` converts
   real seconds into plant seconds, so slopes are reported per **plant minute**
   (~3 °C/min for that same ramp — a realistic industrial figure, and the reason the
   existing 2.0 / 4.0 °C-per-minute thresholds are meaningful).

   Set ``DEMO_TIME_SCALE=1`` in the environment to report raw per-real-second slopes.
"""

import os
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

Point = Tuple[datetime, float]

#: Minimum real-time span of history before a slope is trustworthy enough to report.
MIN_TREND_SPAN_S = 10.0

#: Minimum number of samples before a slope is trustworthy enough to report.
MIN_TREND_POINTS = 3

#: Plant seconds represented by one real second of the demo simulator.
DEMO_TIME_SCALE = float(os.getenv("DEMO_TIME_SCALE", "60.0"))

#: How long a sample stays in an agent's history buffer (real seconds).
HISTORY_TTL_S = 60.0


def span_seconds(points: Sequence[Point]) -> float:
    """Real-time span covered by ``points`` (oldest first)."""
    if len(points) < 2:
        return 0.0
    return (points[-1][0] - points[0][0]).total_seconds()


def prune(points: List[Point], now: datetime, ttl_s: float = HISTORY_TTL_S) -> List[Point]:
    """Drop samples older than ``ttl_s``. Returns the same list object, mutated."""
    cutoff = now.timestamp() - ttl_s
    while points and points[0][0].timestamp() < cutoff:
        points.pop(0)
    return points


def slope_per_plant_minute(
    points: Sequence[Point],
    min_span_s: float = MIN_TREND_SPAN_S,
    min_points: int = MIN_TREND_POINTS,
) -> Optional[float]:
    """Least-squares slope in units per *plant* minute, or ``None`` if not yet known.

    ``None`` means "I do not have enough history to make a claim" and callers must not
    substitute a number for it.
    """
    if len(points) < min_points:
        return None
    if span_seconds(points) < min_span_s:
        return None

    t0 = points[0][0]
    xs = [(t - t0).total_seconds() for t, _ in points]
    ys = [float(v) for _, v in points]
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom <= 0.0:
        return None
    numer = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))

    per_real_second = numer / denom
    # 1 real second == DEMO_TIME_SCALE plant seconds == DEMO_TIME_SCALE/60 plant minutes
    return per_real_second * 60.0 / DEMO_TIME_SCALE


def trailing_above(points: Sequence[Point], threshold: float) -> Tuple[int, float]:
    """Length and real-time span of the run of most-recent samples ``>= threshold``.

    Used for alarm *verification*: a smoke reading that stays above the critical level
    for several consecutive readings is a different, stronger signal than a single spike.
    """
    run: List[Point] = []
    for point in reversed(points):
        if point[1] >= threshold:
            run.insert(0, point)
        else:
            break
    return len(run), span_seconds(run)


def sustained_above(
    points: Sequence[Point],
    threshold: float,
    min_readings: int = 3,
    min_span_s: float = 3.0,
) -> bool:
    """True when the latest readings have held above ``threshold`` long enough to trust."""
    count, span = trailing_above(points, threshold)
    return count >= min_readings and span >= min_span_s


def eta_seconds_to_limit(value: float, limit: float, slope_per_minute: Optional[float]) -> Optional[float]:
    """Plant seconds until ``value`` reaches ``limit`` at the current slope.

    ``None`` when the slope is unknown, flat, or pointing away from the limit.
    """
    if slope_per_minute is None or slope_per_minute <= 0.0:
        return None
    remaining = limit - value
    if remaining <= 0.0:
        return 0.0
    return (remaining / slope_per_minute) * 60.0
