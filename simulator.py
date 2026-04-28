"""
simulator.py — Hardware Simulator for Self-Healing Infrastructure System
Drop-in replacement for backend.py when ESP32 is not connected.

Runs a FastAPI on port 8001 with the SAME /data output as backend.py.
Cycles through realistic disaster scenarios automatically.

Run: uvicorn simulator:app --host 0.0.0.0 --port 8001 --reload
     OR: python simulator.py
"""

import math
import random
import threading
import time
from collections import deque
from typing import List

import numpy as np

try:
    import uvicorn
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError:
    print("Install: pip install fastapi uvicorn")
    raise

# ================================================================
#  SCENARIO DEFINITIONS
# ================================================================
SCENARIOS = [
    {
        "name":        "All Clear",
        "duration_s":  30,
        "rain":        ["DRY"],
        "water_base":  400,
        "water_noise": 30,
        "water_drift": 0,
        "vib_prob":    0.00,
        "description": "Normal operations. All sensors nominal.",
    },
    {
        "name":        "Light Rain",
        "duration_s":  25,
        "rain":        ["DRY", "MODERATE"],
        "water_base":  900,
        "water_noise": 60,
        "water_drift": 8,
        "vib_prob":    0.01,
        "description": "Precipitation beginning. Water level rising slowly.",
    },
    {
        "name":        "Heavy Rain",
        "duration_s":  30,
        "rain":        ["MODERATE", "WET"],
        "water_base":  1800,
        "water_noise": 100,
        "water_drift": 20,
        "vib_prob":    0.02,
        "description": "Heavy rainfall. Flood risk increasing.",
    },
    {
        "name":        "Flood Warning",
        "duration_s":  35,
        "rain":        ["WET"],
        "water_base":  2800,
        "water_noise": 120,
        "water_drift": 35,
        "vib_prob":    0.03,
        "description": "Flood conditions developing. Water above threshold.",
    },
    {
        "name":        "Critical Flood",
        "duration_s":  25,
        "rain":        ["WET"],
        "water_base":  3600,
        "water_noise": 80,
        "water_drift": 15,
        "vib_prob":    0.10,
        "description": "Critical flood level. Infrastructure at risk.",
    },
    {
        "name":        "Earthquake",
        "duration_s":  20,
        "rain":        ["DRY", "MODERATE"],
        "water_base":  600,
        "water_noise": 40,
        "water_drift": 0,
        "vib_prob":    0.90,
        "description": "Seismic activity detected. Structural integrity alert.",
    },
    {
        "name":        "Combined Disaster",
        "duration_s":  30,
        "rain":        ["WET"],
        "water_base":  3200,
        "water_noise": 150,
        "water_drift": 25,
        "vib_prob":    0.85,
        "description": "CRITICAL: Simultaneous flood and seismic event.",
    },
    {
        "name":        "Recovery",
        "duration_s":  30,
        "rain":        ["MODERATE", "DRY"],
        "water_base":  2000,
        "water_noise": 80,
        "water_drift": -25,
        "vib_prob":    0.02,
        "description": "Conditions improving. Systems returning to normal.",
    },
]


# ================================================================
#  SIMULATOR CORE
# ================================================================
class InfrastructureSimulator:
    def __init__(self):
        self.scenario_idx   = 0
        self.scenario_tick  = 0
        self.current_water  = 400.0
        self.tick           = 0

        # Mirror of backend state
        self.rain_counter   = 0
        self.vib_counter    = 0
        self.water_history  = deque(maxlen=120)
        self.risk_history   = deque(maxlen=120)

        self.current_output = self._build_output("DRY", 400, "NO")
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _current_scenario(self):
        return SCENARIOS[self.scenario_idx % len(SCENARIOS)]

    def _next_scenario(self):
        self.scenario_idx = (self.scenario_idx + 1) % len(SCENARIOS)
        self.scenario_tick = 0
        sc = self._current_scenario()
        print(f"[SIM] Scenario → {sc['name']}: {sc['description']}")

    def _simulate_tick(self):
        sc = self._current_scenario()

        # Advance or switch scenario
        self.scenario_tick += 1
        if self.scenario_tick >= sc["duration_s"] * 2:  # 0.5s ticks
            self._next_scenario()
            sc = self._current_scenario()

        # Generate rain
        rain_choices = sc["rain"]
        rain = random.choice(rain_choices)

        # Generate water level (smooth drift + noise)
        drift = sc["water_drift"] * 0.5  # per tick
        noise = random.gauss(0, sc["water_noise"] * 0.3)
        self.current_water += drift + noise
        self.current_water = float(np.clip(self.current_water, 100, 4095))

        # Pull toward scenario base over time
        base = sc["water_base"]
        self.current_water += (base - self.current_water) * 0.05

        water = int(self.current_water)

        # Generate vibration
        vib_prob = sc["vib_prob"]
        # Vibration is bursty — if we were vibrating last tick, higher chance to continue
        if self.vib_counter > 0:
            vib_prob = min(vib_prob + 0.4, 0.95)
        vibration = "YES" if random.random() < vib_prob else "NO"

        return rain, water, vibration

    def _build_output(self, rain, water, vibration):
        """Mirror backend.py risk computation."""
        # Update counters
        if rain != "DRY":
            self.rain_counter += 1
        else:
            self.rain_counter = max(0, self.rain_counter - 1)

        if vibration == "YES":
            self.vib_counter += 1
        else:
            self.vib_counter = max(0, self.vib_counter - 3)

        rain_dur = float(self.rain_counter)
        vib_dur  = float(self.vib_counter)

        # Water trend
        self.water_history.append(float(water))
        wh = list(self.water_history)
        water_trend = (wh[-1] - wh[-6]) / 6.0 if len(wh) >= 6 else 0.0

        # Rule-based risks (mirrors backend.py)
        water_norm = water / 4095.0
        rain_enc   = {"DRY": 0, "MODERATE": 1, "WET": 2}.get(rain, 0)

        # Flood risk
        water_comp  = min(water_norm ** 1.6, 1.0)
        rain_comp   = rain_enc / 2.0
        dur_comp    = 1 - math.exp(-rain_dur / 200.0)
        trend_bonus = min(max(water_trend / 100.0, 0), 0.3)
        flood_r     = water_comp * 50 + rain_comp * 20 + dur_comp * 20 + trend_bonus * 10
        flood_r     = float(np.clip(flood_r, 0, 100))

        # Earthquake risk
        vib_a   = 1.0 if vibration == "YES" else 0.0
        quake_r = vib_a * 40 + (1 - math.exp(-vib_dur / 30.0)) * 60 * vib_a
        quake_r = float(np.clip(quake_r, 0, 100))

        # Rain risk
        rain_r = rain_enc * 25.0 + (1 - math.exp(-rain_dur / 300.0)) * 50 * min(rain_enc, 1)
        rain_r = float(np.clip(rain_r, 0, 100))

        # Overall
        overall = flood_r * 0.45 + quake_r * 0.35 + rain_r * 0.20
        overall = float(np.clip(overall, 0, 100))

        self.risk_history.append(overall)

        # Trend
        rh = list(self.risk_history)
        if len(rh) >= 6:
            slope = np.polyfit(np.arange(6, dtype=float), rh[-6:], 1)[0]
            trend = "RISING" if slope > 2.5 else ("FALLING" if slope < -2.5 else "STABLE")
        else:
            trend = "STABLE"

        # Future predictions (linear projection)
        def future(sec):
            if len(rh) < 4: return overall
            recent = rh[-20:]
            n = len(recent)
            coeffs = np.polyfit(np.arange(n, dtype=float), recent, min(2, n-1))
            return float(np.clip(np.polyval(coeffs, n - 1 + sec), 0, 100))

        # Voice message
        sc_name = self._current_scenario()["name"]
        if overall >= 75:
            voice = f"CRITICAL: {sc_name} scenario. Overall risk {overall:.0f}%. Emergency protocols active."
        elif overall >= 45:
            voice = f"Warning: {sc_name}. Risk at {overall:.0f}%. Response teams on standby."
        elif overall >= 20:
            voice = f"Low risk: {sc_name}. Monitoring active. Risk {overall:.0f}%."
        else:
            voice = "All systems stable. Infrastructure nominal."

        # AI reasoning
        reasoning_parts = [
            f"Scenario: {sc_name}.",
            f"Overall risk {overall:.1f}% (Flood:{flood_r:.0f}%, Seismic:{quake_r:.0f}%, Rain:{rain_r:.0f}%).",
        ]
        if water_trend > 20:
            reasoning_parts.append(f"Water rising at {water_trend:.0f} ADC/s — flood threat increasing.")
        if vib_dur > 10:
            reasoning_parts.append(f"Sustained vibration {vib_dur:.0f}s — structural monitoring active.")
        reasoning_parts.append(f"60s projection: {future(60):.0f}%.")
        ai_reasoning = " ".join(reasoning_parts)

        return {
            "rain":           rain,
            "water":          water,
            "vibration":      vibration,
            "flood_risk":     round(flood_r, 1),
            "earthquake_risk":round(quake_r, 1),
            "rain_risk":      round(rain_r, 1),
            "overall_risk":   round(overall, 1),
            "future_10s":     round(future(10), 1),
            "future_30s":     round(future(30), 1),
            "future_60s":     round(future(60), 1),
            "trend":          trend,
            "voice_message":  voice,
            "ai_reasoning":   ai_reasoning,
            "connected":      True,
            "stale":          False,
            "rain_duration":  int(rain_dur),
            "vib_duration":   int(vib_dur),
            "_scenario":      sc_name,   # bonus debug field
        }

    def _run(self):
        print("[SIM] Starting simulation loop...")
        sc = self._current_scenario()
        print(f"[SIM] Initial scenario: {sc['name']}")
        while True:
            rain, water, vibration = self._simulate_tick()
            output = self._build_output(rain, water, vibration)
            with self._lock:
                self.current_output = output
            self.tick += 1
            time.sleep(0.5)  # Match ESP32 polling rate

    def get_data(self):
        with self._lock:
            return dict(self.current_output)


# ================================================================
#  FASTAPI APP
# ================================================================
app = FastAPI(title="Infrastructure Simulator", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_sim = InfrastructureSimulator()


@app.get("/")
def root():
    return {"status": "simulator_online", "note": "Replace with backend.py when ESP32 is connected."}


@app.get("/data")
def get_data():
    return _sim.get_data()


@app.get("/scenarios")
def list_scenarios():
    return [{"index": i, "name": s["name"], "description": s["description"]}
            for i, s in enumerate(SCENARIOS)]


if __name__ == "__main__":
    print("=" * 50)
    print("  Infrastructure Simulator")
    print("  Starting on http://localhost:8001")
    print("  Dashboard connects to /data")
    print("=" * 50)
    uvicorn.run(app, host="0.0.0.0", port=8001)