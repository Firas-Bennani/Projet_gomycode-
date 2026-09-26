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
            m.status = Severity.CRITICAL if (cur_temp >= 50 or cur_pres >= 8.0) else Severity.WARNING
            m.parameters["temperature"].value = round(cur_temp + 35.0, 1)
            m.parameters["temperature"].status = m.status
            m.parameters["pressure"].value = round(cur_pres, 2)
            m.parameters["pressure"].status = m.status
            m.parameters["vibration"].value = round(3.5 + (idx * 0.4), 2)
            m.parameters["vibration"].status = Severity.WARNING if idx >= 4 else Severity.INFO

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
            severity="CRITICAL" if cur_temp >= 50 else "WARNING"
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
            severity="CRITICAL" if cur_pres >= 8.0 else "WARNING"
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

        if "TEMP-B-01" in state.sensors:
            state.sensors["TEMP-B-01"].current_value = cur_temp
            state.sensors["TEMP-B-01"].status = Severity.CRITICAL
        if "SMOKE-B-01" in state.sensors:
            state.sensors["SMOKE-B-01"].current_value = cur_smoke
            state.sensors["SMOKE-B-01"].status = Severity.CRITICAL

        await event_bus.publish(
            event_type="SENSOR_READING",
            source="sensor:SMOKE-B-01",
            data={
                "sensor_id": "SMOKE-B-01",
                "type": "smoke",
                "value": cur_smoke,
                "unit": "ppm",
                "zone": "ZONE_B"
            },
            zone="ZONE_B",
            severity="CRITICAL"
        )

simulator = IoTSimulator()
