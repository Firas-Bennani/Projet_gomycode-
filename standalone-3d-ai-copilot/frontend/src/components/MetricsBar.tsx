import React from 'react';
import { Sensor, Machine, Incident, Worker } from '../types';
import { Thermometer, Gauge, Droplets, Zap, Activity, Users, AlertTriangle, TrendingUp } from 'lucide-react';

interface MetricsBarProps {
  sensors: Sensor[];
  machines: Machine[];
  incidents: Incident[];
  workers: Worker[];
}

export const MetricsBar: React.FC<MetricsBarProps> = ({
  sensors,
  machines,
  incidents,
  workers,
}) => {
  const tempSensor = sensors.find((s) => s.id === 'TEMP-B-01');
  const presSensor = sensors.find((s) => s.id === 'PRES-B-01');
  const humSensor = sensors.find((s) => s.id === 'HUM-B-01');
  const energySensor = sensors.find((s) => s.id === 'ENG-TOTAL');

  const curTemp = tempSensor ? tempSensor.current_value : 26.2;
  const curPres = presSensor ? presSensor.current_value : 5.4;
  const curHum = humSensor ? humSensor.current_value : 48.0;
  const curEnergy = energySensor ? energySensor.current_value : 423.0;

  const activeAlerts = incidents.filter((i) => i.status === 'ACTIVE').length;
  const activeWorkers = workers.filter((w) => w.status === 'ON_SITE').length;

  const isTempCritical = curTemp >= 50.0;
  const isPresCritical = curPres >= 8.0;

  return (
    <div className="h-20 glass-panel border-t border-slate-800 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2 p-2 select-none font-mono">
      {/* 1. Temperature */}
      <div className={`p-2 rounded-lg border flex flex-col justify-between transition-colors ${
        isTempCritical ? 'bg-red-950/40 border-red-500/50 text-red-300' : 'bg-slate-900/60 border-slate-800 text-slate-300'
      }`}>
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span>TEMPERATURE</span>
          <Thermometer className={`w-3.5 h-3.5 ${isTempCritical ? 'text-red-400 animate-bounce' : 'text-cyan-400'}`} />
        </div>
        <div className="flex items-baseline justify-between">
          <span className={`text-base font-extrabold ${isTempCritical ? 'text-red-400' : 'text-white'}`}>
            {curTemp.toFixed(1)}°C
          </span>
          <span className={`text-[10px] font-bold ${curTemp > 30 ? 'text-red-400' : 'text-emerald-400'}`}>
            {curTemp > 30 ? '↑ +4.2%' : 'Normal'}
          </span>
        </div>
      </div>

      {/* 2. Pressure */}
      <div className={`p-2 rounded-lg border flex flex-col justify-between transition-colors ${
        isPresCritical ? 'bg-red-950/40 border-red-500/50 text-red-300' : 'bg-slate-900/60 border-slate-800 text-slate-300'
      }`}>
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span>PRESSURE</span>
          <Gauge className={`w-3.5 h-3.5 ${isPresCritical ? 'text-red-400' : 'text-sky-400'}`} />
        </div>
        <div className="flex items-baseline justify-between">
          <span className={`text-base font-extrabold ${isPresCritical ? 'text-red-400' : 'text-white'}`}>
            {curPres.toFixed(2)} bar
          </span>
          <span className={`text-[10px] font-bold ${isPresCritical ? 'text-red-400 animate-pulse' : 'text-emerald-400'}`}>
            {isPresCritical ? 'OVERPRESSURE' : 'Normal'}
          </span>
        </div>
      </div>

      {/* 3. Humidity */}
      <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800 flex flex-col justify-between text-slate-300">
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span>HUMIDITY</span>
          <Droplets className="w-3.5 h-3.5 text-blue-400" />
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-base font-extrabold text-white">{curHum.toFixed(0)}%</span>
          <span className="text-[10px] text-emerald-400">Optimal</span>
        </div>
      </div>

      {/* 4. Energy */}
      <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800 flex flex-col justify-between text-slate-300">
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span>ENERGY DEMAND</span>
          <Zap className="w-3.5 h-3.5 text-amber-400" />
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-base font-extrabold text-white">{curEnergy.toFixed(0)} kW</span>
          <span className="text-[10px] text-slate-400">Baseline</span>
        </div>
      </div>

      {/* 5. Production Throughput */}
      <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800 flex flex-col justify-between text-slate-300">
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span>PRODUCTION OEE</span>
          <Activity className="w-3.5 h-3.5 text-emerald-400" />
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-base font-extrabold text-white">94.2%</span>
          <span className="text-[10px] text-emerald-400 font-bold">↑ High</span>
        </div>
      </div>

      {/* 6. Active Workers */}
      <div className="p-2 rounded-lg bg-slate-900/60 border border-slate-800 flex flex-col justify-between text-slate-300">
        <div className="flex items-center justify-between text-[10px] text-slate-400">
          <span>ACTIVE WORKERS</span>
          <Users className="w-3.5 h-3.5 text-purple-400" />
        </div>
        <div className="flex items-baseline justify-between">
          <span className="text-base font-extrabold text-white">{activeWorkers}</span>
          <span className="text-[10px] text-slate-400">All Sectors</span>
        </div>
      </div>

      {/* 7. Active Alerts */}
      <div className={`p-2 rounded-lg border flex flex-col justify-between transition-colors ${
        activeAlerts > 0
          ? 'bg-red-950/60 border-red-500 text-red-300 shadow-glow-red animate-pulse'
          : 'bg-slate-900/60 border-slate-800 text-slate-300'
      }`}>
        <div className="flex items-center justify-between text-[10px]">
          <span className={activeAlerts > 0 ? 'text-red-300 font-bold' : 'text-slate-400'}>ACTIVE ALERTS</span>
          <AlertTriangle className={`w-3.5 h-3.5 ${activeAlerts > 0 ? 'text-red-400' : 'text-slate-500'}`} />
        </div>
        <div className="flex items-baseline justify-between">
          <span className={`text-base font-extrabold ${activeAlerts > 0 ? 'text-red-400' : 'text-slate-400'}`}>
            {activeAlerts}
          </span>
          <span className={`text-[10px] font-bold ${activeAlerts > 0 ? 'text-red-400' : 'text-emerald-400'}`}>
            {activeAlerts > 0 ? 'ATTN REQ' : 'Nominal'}
          </span>
        </div>
      </div>
    </div>
  );
};
