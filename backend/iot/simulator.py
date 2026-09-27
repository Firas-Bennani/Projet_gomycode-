import asyncio
import random
import math
from datetime import datetime
import logging
from app.services.state_store import state
from app.services.event_bus import event_bus
from app.models.schemas import Severity

logger = logging.getLogger("simulator")

class IoTSimulator:
    def __init__(self):
        self.running = False
        self.scenario = "normal"  # normal, machine_overheating, cybersecurity, fire
        self.scenario_step = 0
        self.tick_count = 0
        # ---- P5: applied by Engineer 1 on 2026-09-27 04:20, authorised by Firas ----------
        # Once the copilot's remedy has actually been executed, the simulator must stop
        # driving the fault. Before this, STOP_MACHINE set M-04 to a safe baseline and the
        # very next tick overwrote it with the scenario curve (8.93 bar / 52.9 C), so a brand
        # new CRITICAL incident opened seconds after the operator resolved the first one.
        # command_engine sets these when the matching action reaches COMPLETED.
        # Please review: Engineer 2 owns this file. See docs/ai/PROPOSED_CHANGES_FOR_TEAM.md.
        self.stopped_machines: set = set()
        self.cooling_active: bool = False
        self.suppression_active: bool = False
        # ---------------------------------------------------------------------------------

    @staticmethod
    def _decay(current: float, baseline: float, rate: float = 0.35) -> float:
        """Exponential approach to a baseline: fast at first, then settles and stays."""
        value = current + (baseline - current) * rate
        return baseline if abs(value - baseline) < 0.05 else value

    async def start(self):
        self.running = True
        logger.info("Starting IoT factory simulator loop...")
        while self.running:
            try:
                await self.tick()
            except Exception as e:
                logger.error(f"Simulator error in tick: {e}")
            await asyncio.sleep(1.0)

    def stop(self):
        self.running = False

    def set_scenario(self, scenario_name: str):
        self.scenario = scenario_name
        self.scenario_step = 0
        logger.info(f"Simulator scenario switched to: {scenario_name}")

    async def reset(self):
        self.scenario = "normal"
        self.scenario_step = 0
        # P5 (Engineer 1): forget remediations so a fresh demo run ramps normally again.
        self.stopped_machines.clear()
        self.cooling_active = False
        self.suppression_active = False
        state.initialize_state()
        await event_bus.publish(
            event_type="FACTORY_RESET",
            source="simulator",
            data={"status": "RESET_COMPLETE"},
            zone="GLOBAL",
            severity="INFO"
        )

    async def tick(self):
        self.tick_count += 1
        t = self.tick_count * 0.1

        if self.scenario == "normal":
            await self._tick_normal(t)
        elif self.scenario == "machine_overheating":
            await self._tick_overheating()
        elif self.scenario == "cybersecurity":
            await self._tick_cyber()
        elif self.scenario == "fire":
            await self._tick_fire()

    async def _tick_normal(self, t: float):
        # Subtle realistic fluctuation
        temp_b = 25.5 + 0.8 * math.sin(t) + random.uniform(-0.1, 0.1)
        pres_b = 5.2 + 0.3 * math.cos(t * 0.8) + random.uniform(-0.05, 0.05)
        smoke_b = 7.0 + random.uniform(-0.5, 0.5)
        vib_b = 2.4 + 0.2 * math.sin(t * 1.5)

        if "TEMP-B-01" in state.sensors:
            state.sensors["TEMP-B-01"].current_value = round(temp_b, 1)
        if "PRES-B-01" in state.sensors:
            state.sensors["PRES-B-01"].current_value = round(pres_b, 2)
        if "SMOKE-B-01" in state.sensors:
            state.sensors["SMOKE-B-01"].current_value = round(smoke_b, 1)
        if "VIB-B-01" in state.sensors:
            state.sensors["VIB-B-01"].current_value = round(vib_b, 2)

        if "M-04" in state.machines:
            state.machines["M-04"].parameters["temperature"].value = round(temp_b + 18.0, 1)
            state.machines["M-04"].parameters["pressure"].value = round(pres_b, 2)
            state.machines["M-04"].parameters["vibration"].value = round(vib_b, 2)

        # Broadcast sensor readings every 2 ticks
        if self.tick_count % 2 == 0:
            await event_bus.publish(
                event_type="SENSOR_READING",
                source="sensor:TEMP-B-01",
                data={
                    "sensor_id": "TEMP-B-01",
                    "type": "temperature",
                    "value": round(temp_b, 1),
                    "unit": "°C",
                    "zone": "ZONE_B"
                },
                zone="ZONE_B"
            )

    async def _tick_overheating(self):
        self.scenario_step += 1
        step = self.scenario_step

        # Ramp up temperature and pressure
        # Step 1-3: Normal -> Warning (31°C -> 39°C)
        # Step 4-6: Warning -> Critical (45°C -> 51.5°C, Pressure -> 8.7 bar)
        temp_curve = [26.0, 31.5, 36.8, 42.4, 47.9, 51.4, 52.8, 53.0]
        pres_curve = [5.4, 6.1, 7.0, 7.8, 8.3, 8.7, 8.8, 8.9]

        idx = min(step - 1, len(temp_curve) - 1)
        cur_temp = temp_curve[idx] + random.uniform(-0.2, 0.2)
        cur_pres = pres_curve[idx] + random.uniform(-0.05, 0.05)
        cur_vib = 3.5 + (idx * 0.4)

        # ---- P5 (Engineer 1) ------------------------------------------------------------
        # M-04 has been shut down and/or cooling is running: decay to the safe baseline and
        # stay there until reset, instead of snapping back onto the fault curve.
        remedied = ("M-04" in self.stopped_machines) or self.cooling_active
        if remedied:
            prev_temp = state.sensors["TEMP-B-01"].current_value if "TEMP-B-01" in state.sensors else 26.0
            prev_pres = state.sensors["PRES-B-01"].current_value if "PRES-B-01" in state.sensors else 5.2
            cur_temp = self._decay(prev_temp, 25.5)
            cur_pres = self._decay(prev_pres, 5.2)
            cur_vib = self._decay(cur_vib if idx == 0 else
                                  state.machines["M-04"].parameters["vibration"].value
                                  if "M-04" in state.machines else 2.4, 0.2)
        # ---------------------------------------------------------------------------------

        # Update sensors
        if "TEMP-B-01" in state.sensors:
            state.sensors["TEMP-B-01"].current_value = round(cur_temp, 1)
            state.sensors["TEMP-B-01"].status = Severity.CRITICAL if cur_temp >= 50 else (Severity.WARNING if cur_temp >= 35 else Severity.INFO)

        if "PRES-B-01" in state.sensors:
            state.sensors["PRES-B-01"].current_value = round(cur_pres, 2)
            state.sensors["PRES-B-01"].status = Severity.CRITICAL if cur_pres >= 8.0 else (Severity.WARNING if cur_pres >= 7.0 else Severity.INFO)

        # Update Machine M-04
        if "M-04" in state.machines:
            m = state.machines["M-04"]
            # P5 (Engineer 1): a remedied machine reports nominal, and its body temperature
            # follows the calm offset used by the normal scenario rather than the fault one.
            if remedied:
                m.status = Severity.INFO
                body_offset = 18.0
            else:
                m.status = Severity.CRITICAL if (cur_temp >= 50 or cur_pres >= 8.0) else Severity.WARNING
                body_offset = 35.0
            m.parameters["temperature"].value = round(cur_temp + body_offset, 1)
            m.parameters["temperature"].status = m.status
            m.parameters["pressure"].value = round(cur_pres, 2)
            m.parameters["pressure"].status = m.status
            m.parameters["vibration"].value = round(cur_vib, 2)
            m.parameters["vibration"].status = (
                Severity.INFO if remedied else (Severity.WARNING if idx >= 4 else Severity.INFO)
            )

        # Publish sensor and machine events to drive multi-agent reasoning
        await event_bus.publish(
            event_type="SENSOR_READING",
            source="sensor:TEMP-B-01",
            data={
                "sensor_id": "TEMP-B-01",
                "type": "temperature",
                "value": round(cur_temp, 1),
                "unit": "°C",
                "zone": "ZONE_B"
            },
            zone="ZONE_B",
            severity=("INFO" if remedied else ("CRITICAL" if cur_temp >= 50 else "WARNING"))
        )

        await event_bus.publish(
            event_type="MACHINE_STATUS",
            source="machine:M-04",
            data={
                "machine_id": "M-04",
                "zone": "ZONE_B",
                "parameters": {
                    "pressure": {"value": round(cur_pres, 2)},
                    "temperature": {"value": round(cur_temp + 35.0, 1)},
                    "vibration": {"value": round(3.5 + (idx * 0.4), 2)},
                    "rpm": {"value": 1420}
                }
            },
            zone="ZONE_B",
            severity=("INFO" if remedied else ("CRITICAL" if cur_pres >= 8.0 else "WARNING"))
        )

    async def _tick_cyber(self):
        self.scenario_step += 1
        # Trigger cyber intrusion event
        await event_bus.publish(
            event_type="CYBER_EVENT",
            source="simulator:cyber_engine",
            data={
                "cyber_type": "UNAUTHORIZED_DEVICE",
                "device": "UNKNOWN-DEVICE-07",
                "attempts": 47,
                "target": "Industrial Modbus Gateway (192.168.10.45)"
            },
            zone="ZONE_B",
            severity="HIGH"
        )

    async def _tick_fire(self):
        self.scenario_step += 1
        step = self.scenario_step
        temp_curve = [28.0, 35.0, 44.0, 52.0, 58.5, 62.0]
        smoke_curve = [10.0, 22.0, 35.0, 48.0, 60.0, 75.0]

        idx = min(step - 1, len(temp_curve) - 1)
        cur_temp = temp_curve[idx]
        cur_smoke = smoke_curve[idx]

        # ---- P5 (Engineer 1) ------------------------------------------------------------
        # Suppression has been discharged: let the fire go out instead of re-igniting on the
        # next tick.
        if self.suppression_active:
            prev_smoke = state.sensors["SMOKE-B-01"].current_value if "SMOKE-B-01" in state.sensors else 7.0
            prev_temp = state.sensors["TEMP-B-01"].current_value if "TEMP-B-01" in state.sensors else 26.0
            cur_smoke = self._decay(prev_smoke, 7.0)
            cur_temp = self._decay(prev_temp, 25.5)
        # ---------------------------------------------------------------------------------

        if "TEMP-B-01" in state.sensors:
            sensor = state.sensors["TEMP-B-01"]
            sensor.current_value = round(cur_temp, 1)
            sensor.status = (Severity.CRITICAL if cur_temp >= 50 else
                             Severity.WARNING if cur_temp >= 35 else Severity.INFO)
        if "SMOKE-B-01" in state.sensors:
            sensor = state.sensors["SMOKE-B-01"]
            sensor.current_value = round(cur_smoke, 1)
            sensor.status = (Severity.CRITICAL if cur_smoke >= 40 else
                             Severity.WARNING if cur_smoke >= 20 else Severity.INFO)

        await event_bus.publish(
            event_type="SENSOR_READING",
            source="sensor:SMOKE-B-01",
            data={
                "sensor_id": "SMOKE-B-01",
                "type": "smoke",
                "value": round(cur_smoke, 1),
                "unit": "ppm",
                "zone": "ZONE_B"
            },
            zone="ZONE_B",
            severity=("INFO" if cur_smoke < 20 else "CRITICAL" if cur_smoke >= 40 else "WARNING")
        )

simulator = IoTSimulator()
