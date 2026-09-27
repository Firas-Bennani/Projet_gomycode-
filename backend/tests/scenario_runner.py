"""Drive the real simulator and the real orchestrator without waiting in real time.

The production path is ``simulator.tick()`` -> ``event_bus.publish()`` ->
``orchestrator.handle_event()`` dispatched through ``asyncio.create_task``. Tasks make
assertions racy, so here we collect the published events and feed them to the orchestrator
*in order*, one tick at a time, with a :class:`ai.clock.FakeClock` advanced by one second
per tick. Same code, same event payloads, deterministic timing.
"""

import asyncio
import random
from types import SimpleNamespace
from typing import Any, Dict, List

from ai import clock
from ai.orchestrator import AgentOrchestrator
from app.services.event_bus import event_bus
from app.services.state_store import state
from iot.simulator import simulator

#: Events the plant emits. Anything the AI layer publishes itself (INCIDENT_*, ACTION_*)
#: is not fed back in, so a run cannot amplify its own output.
PLANT_EVENT_TYPES = {"SENSOR_READING", "MACHINE_STATUS", "CYBER_EVENT", "WORKER_UPDATE",
                     # the weather feed and the storm strike are plant inputs too: the
                     # forecast is what makes the storm scenario predictive.
                     "FORECAST_UPDATE", "STORM_IMPACT"}


async def cancel_stray_tasks() -> None:
    """Cancel the auto-execute action tasks the orchestrator fired off."""
    current = asyncio.current_task()
    stray = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    for task in stray:
        task.cancel()
    if stray:
        await asyncio.gather(*stray, return_exceptions=True)


FACTORY_RESET_EVENT = {
    "event_type": "FACTORY_RESET",
    "source": "simulator",
    "zone": "GLOBAL",
    "severity": "INFO",
    "data": {"status": "RESET_COMPLETE"},
}


def _make_feeder(orchestrator, fake):
    """Keep ticking the simulator through the same orchestrator and the same fake clock.

    Used by tests that need to carry on after a run (e.g. authorise everything, then prove
    nothing re-opens). It manages its own event subscription, because the run restores the
    original subscribers when it finishes.
    """
    async def feed(ticks: int, scenario: str = None, tick_seconds: float = 1.0):
        local: List[Dict[str, Any]] = []
        saved = dict(event_bus._subscribers)
        event_bus._subscribers.clear()
        event_bus.subscribe("*", lambda evt: local.append(evt))
        try:
            if scenario:
                simulator.tick_count = 0
                simulator.set_scenario(scenario)
            for _ in range(ticks):
                fake.advance(tick_seconds)
                await simulator.tick()
                batch = [e for e in local if e["event_type"] in PLANT_EVENT_TYPES]
                local.clear()
                for event in batch:
                    await orchestrator.handle_event(event)
        finally:
            event_bus._subscribers.clear()
            event_bus._subscribers.update(saved)
    return feed


async def run_scenario(
    scenario: str,
    ticks: int = 12,
    seed: int = 42,
    tick_seconds: float = 1.0,
    extra_events: List[Dict[str, Any]] = None,
    keep_clock: bool = False,
) -> SimpleNamespace:
    return await run_scenario_sequence(
        [(scenario, ticks)], seed=seed, tick_seconds=tick_seconds, extra_events=extra_events,
        keep_clock=keep_clock,
    )


async def run_scenario_sequence(
    steps,
    seed: int = 42,
    tick_seconds: float = 1.0,
    factory_reset_between: bool = False,
    extra_events: List[Dict[str, Any]] = None,
    keep_clock: bool = False,
) -> SimpleNamespace:
    """Drive several scenarios through ONE orchestrator, as the demo bar does.

    ``factory_reset_between`` reproduces ``POST /api/demo/reset``: the state store is
    re-initialised and a ``FACTORY_RESET`` event is delivered to the orchestrator.
    """
    random.seed(seed)
    fake = clock.FakeClock()
    clock.set_clock(fake)

    state.initialize_state()
    orchestrator = AgentOrchestrator()

    # P5 left these set by a previous run; a fresh scenario must ramp normally again.
    simulator.stopped_machines.clear()
    simulator.cooling_active = False
    simulator.suppression_active = False

    collected: List[Dict[str, Any]] = []
    published: List[Dict[str, Any]] = []      # every event, including what the AI layer emits
    saved_subscribers = dict(event_bus._subscribers)
    event_bus._subscribers.clear()

    def _collect(event):
        collected.append(event)
        published.append(event)

    event_bus.subscribe("*", _collect)

    try:
        for index, (scenario, ticks) in enumerate(steps):
            if index > 0 and factory_reset_between:
                state.initialize_state()
                await orchestrator.handle_event(dict(FACTORY_RESET_EVENT))
            simulator.tick_count = 0
            simulator.set_scenario(scenario)
            for _ in range(ticks):
                fake.advance(tick_seconds)
                await simulator.tick()
                batch = [e for e in collected if e["event_type"] in PLANT_EVENT_TYPES]
                collected.clear()
                for event in batch:
                    await orchestrator.handle_event(event)
        for event in extra_events or []:
            fake.advance(tick_seconds)
            await orchestrator.handle_event(event)
    finally:
        event_bus._subscribers.clear()
        event_bus._subscribers.update(saved_subscribers)
        await cancel_stray_tasks()
        # keep_clock leaves the fake clock installed so a test can carry on from where the run
        # stopped. Restarting it would put `resolved_at` in the future, which silently disables
        # the cooldown and the re-open guard.
        if not keep_clock:
            clock.reset_clock()
        simulator.set_scenario("normal")

    return SimpleNamespace(
        orchestrator=orchestrator,
        incidents=list(state.incidents.values()),
        actions=list(state.actions.values()),
        logs=list(state.agent_logs),
        types=[i.type for i in state.incidents.values()],
        published=published,
        events_of=lambda event_type: [e for e in published if e["event_type"] == event_type],
        clock=fake,
        feed=_make_feeder(orchestrator, fake),
    )
