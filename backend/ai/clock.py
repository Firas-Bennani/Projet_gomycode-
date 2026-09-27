"""Injectable clock for the AI layer.

Why this exists: the agents reason about *trends* (°C per minute, bar per minute), so
they need timestamps. If they call ``datetime.utcnow()`` directly, the only way to test
trend logic is to sleep in real time, which makes the test suite slow and flaky.

Production behaviour is unchanged: ``clock.now()`` returns ``datetime.utcnow()``.
Tests swap in a :class:`FakeClock` and advance it tick by tick.
"""

from datetime import datetime, timedelta


class Clock:
    """Real wall clock (UTC)."""

    def now(self) -> datetime:
        return datetime.utcnow()


class FakeClock(Clock):
    """Manually advanced clock, used by the scenario tests."""

    def __init__(self, start: datetime = None):
        self._t = start or datetime(2026, 1, 1, 0, 0, 0)

    def now(self) -> datetime:
        return self._t

    def advance(self, seconds: float) -> datetime:
        self._t = self._t + timedelta(seconds=seconds)
        return self._t


_clock: Clock = Clock()


def now() -> datetime:
    """Current time as seen by the AI layer."""
    return _clock.now()


def set_clock(clock: Clock) -> None:
    global _clock
    _clock = clock


def reset_clock() -> None:
    global _clock
    _clock = Clock()
