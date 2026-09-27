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
        self.lifecycle_phase = "IDLE"  # IDLE, DEVELOPING, DETECTED, INCIDENT_ACTIVE, ACTION_EXECUTING, COOLING_DOWN, VERIFYING, RESOLVED
        self.cooling_down = False

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
        self.cooling_down = False
        self.lifecycle_phase = "IDLE" if scenario_name == "normal" else "DEVELOPING"
        logger.info(f"Simulator scenario switched to: {scenario_name} (phase: {self.lifecycle_phase})")

    async def reset(self):
        self.scenario = "normal"
        self.scenario_step = 0
        self.cooling_down = False
        self.lifecycle_phase = "IDLE"
        state.initialize_state()
        await event_bus.publish(
            event_type="FACTORY_RESET",
            source="simulator",
            data={"status": "RESET_COMPLETE"},
            zone="GLOBAL",
            severity="INFO"
        )

    def notify_action_executed(self, action_type: str, target: str):
        logger.info(f"Simulator received action execution notification: {action_type} on {target}")
        if action_type in ["STOP_MACHINE", "ACTIVATE_COOLING", "ACTIVATE_SUPPRESSION"]:
            self.cooling_down = True
            self.lifecycle_phase = "COOLING_DOWN"

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
            state.sensors["TEMP-B-01"].status = Severity.INFO
        if "PRES-B-01" in state.sensors:
            state.sensors["PRES-B-01"].current_value = round(pres_b, 2)
            state.sensors["PRES-B-01"].status = Severity.INFO
        if "SMOKE-B-01" in state.sensors:
            state.sensors["SMOKE-B-01"].current_value = round(smoke_b, 1)
            state.sensors["SMOKE-B-01"].status = Severity.INFO
        if "VIB-B-01" in state.sensors:
            state.sensors["VIB-B-01"].current_value = round(vib_b, 2)
            state.sensors["VIB-B-01"].status = Severity.INFO

        if "M-04" in state.machines:
            state.machines["M-04"].status = Severity.INFO
            state.machines["M-04"].parameters["temperature"].value = round(temp_b + 18.0, 1)
            state.machines["M-04"].parameters["temperature"].status = Severity.INFO
            state.machines["M-04"].parameters["pressure"].value = round(pres_b, 2)
            state.machines["M-04"].parameters["pressure"].status = Severity.INFO
            state.machines["M-04"].parameters["vibration"].value = round(vib_b, 2)
            state.machines["M-04"].parameters["vibration"].status = Severity.INFO

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

        if self.cooling_down:
            # Gradually reduce sensor parameters back to baseline
            cur_temp_sensor = state.sensors.get("TEMP-B-01")
            prev_temp = cur_temp_sensor.current_value if cur_temp_sensor else 52.0
            new_temp = max(26.0, round(prev_temp - 4.5, 1))

            cur_pres_sensor = state.sensors.get("PRES-B-01")
            prev_pres = cur_pres_sensor.current_value if cur_pres_sensor else 8.5
            new_pres = max(4.5, round(prev_pres - 0.9, 2))

            new_vib = 1.2 if new_temp <= 32.0 else 2.5

            if new_temp <= 30.0:
                self.lifecycle_phase = "RESOLVED"

            sev = Severity.INFO if new_temp <= 32.0 else Severity.WARNING

            if "TEMP-B-01" in state.sensors:
                state.sensors["TEMP-B-01"].current_value = new_temp
                state.sensors["TEMP-B-01"].status = sev
            if "PRES-B-01" in state.sensors:
                state.sensors["PRES-B-01"].current_value = new_pres
                state.sensors["PRES-B-01"].status = sev

            if "M-04" in state.machines:
                m = state.machines["M-04"]
                m.status = sev
                m.parameters["temperature"].value = round(new_temp + 15.0, 1)
                m.parameters["temperature"].status = sev
                m.parameters["pressure"].value = new_pres
                m.parameters["pressure"].status = sev
                m.parameters["vibration"].value = new_vib
                m.parameters["vibration"].status = sev
                m.parameters["rpm"].value = 0.0

            await event_bus.publish(
                event_type="SENSOR_READING",
                source="sensor:TEMP-B-01",
                data={
                    "sensor_id": "TEMP-B-01",
                    "type": "temperature",
                    "value": new_temp,
                    "unit": "°C",
                    "zone": "ZONE_B"
                },
                zone="ZONE_B",
                severity=sev.value
            )
            await event_bus.publish(
                event_type="MACHINE_STATUS",
                source="machine:M-04",
                data={
                    "machine_id": "M-04",
                    "zone": "ZONE_B",
                    "parameters": {
                        "pressure": {"value": new_pres},
                        "temperature": {"value": round(new_temp + 15.0, 1)},
                        "vibration": {"value": new_vib},
                        "rpm": {"value": 0.0}
                    }
                },
                zone="ZONE_B",
                severity=sev.value
            )
            return

        # Ramp up temperature and pressure during anomaly development phase
        temp_curve = [26.0, 31.5, 36.8, 42.4, 47.9, 51.4, 52.8, 53.0]
        pres_curve = [5.4, 6.1, 7.0, 7.8, 8.3, 8.7, 8.8, 8.9]

        idx = min(step - 1, len(temp_curve) - 1)
        cur_temp = temp_curve[idx] + random.uniform(-0.2, 0.2)
        cur_pres = pres_curve[idx] + random.uniform(-0.05, 0.05)

        if cur_temp >= 50.0 or cur_pres >= 8.0:
            self.lifecycle_phase = "INCIDENT_ACTIVE"
        elif cur_temp >= 35.0:
            self.lifecycle_phase = "DETECTED"

        if "TEMP-B-01" in state.sensors:
            state.sensors["TEMP-B-01"].current_value = round(cur_temp, 1)
            state.sensors["TEMP-B-01"].status = Severity.CRITICAL if cur_temp >= 50 else (Severity.WARNING if cur_temp >= 35 else Severity.INFO)

        if "PRES-B-01" in state.sensors:
            state.sensors["PRES-B-01"].current_value = round(cur_pres, 2)
            state.sensors["PRES-B-01"].status = Severity.CRITICAL if cur_pres >= 8.0 else (Severity.WARNING if cur_pres >= 7.0 else Severity.INFO)

        if "M-04" in state.machines:
            m = state.machines["M-04"]
            m.status = Severity.CRITICAL if (cur_temp >= 50 or cur_pres >= 8.0) else Severity.WARNING
            m.parameters["temperature"].value = round(cur_temp + 35.0, 1)
            m.parameters["temperature"].status = m.status
            m.parameters["pressure"].value = round(cur_pres, 2)
            m.parameters["pressure"].status = m.status
            m.parameters["vibration"].value = round(3.5 + (idx * 0.4), 2)
            m.parameters["vibration"].status = Severity.WARNING if idx >= 4 else Severity.INFO

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
        self.lifecycle_phase = "INCIDENT_ACTIVE"
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

        if self.cooling_down:
            cur_smoke_sensor = state.sensors.get("SMOKE-B-01")
            prev_smoke = cur_smoke_sensor.current_value if cur_smoke_sensor else 65.0
            new_smoke = max(7.0, round(prev_smoke - 12.0, 1))

            cur_temp_sensor = state.sensors.get("TEMP-B-01")
            prev_temp = cur_temp_sensor.current_value if cur_temp_sensor else 58.0
            new_temp = max(25.0, round(prev_temp - 8.0, 1))

            sev = Severity.INFO if new_smoke <= 15.0 else Severity.WARNING
            if new_smoke <= 10.0:
                self.lifecycle_phase = "RESOLVED"

            if "TEMP-B-01" in state.sensors:
                state.sensors["TEMP-B-01"].current_value = new_temp
                state.sensors["TEMP-B-01"].status = sev
            if "SMOKE-B-01" in state.sensors:
                state.sensors["SMOKE-B-01"].current_value = new_smoke
                state.sensors["SMOKE-B-01"].status = sev

            await event_bus.publish(
                event_type="SENSOR_READING",
                source="sensor:SMOKE-B-01",
                data={
                    "sensor_id": "SMOKE-B-01",
                    "type": "smoke",
                    "value": new_smoke,
                    "unit": "ppm",
                    "zone": "ZONE_B"
                },
                zone="ZONE_B",
                severity=sev.value
            )
            return

        temp_curve = [28.0, 35.0, 44.0, 52.0, 58.5, 62.0]
        smoke_curve = [10.0, 22.0, 35.0, 48.0, 60.0, 75.0]

        idx = min(step - 1, len(temp_curve) - 1)
        cur_temp = temp_curve[idx]
        cur_smoke = smoke_curve[idx]

        if cur_smoke >= 40.0:
            self.lifecycle_phase = "INCIDENT_ACTIVE"
        elif cur_smoke >= 20.0:
            self.lifecycle_phase = "DETECTED"

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
