"""
backend.py — Self-Healing Infrastructure FastAPI Backend
Reads ESP32 serial data → time-based counters → ML risk prediction → /data endpoint

Run:  uvicorn backend:app --host 0.0.0.0 --port 8001 --reload
Requires: model.pkl (run train_model.py first)
"""
import joblib
import json
import math
import pickle
import threading
import time
from collections import deque
from typing import Optional

import numpy as np
import joblib
import serial
import serial.tools.list_ports
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ================================================================
#  APP SETUP
# ================================================================
app = FastAPI(title="Self-Healing Infrastructure Backend", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ================================================================
#  CONFIGURATION
# ================================================================
SERIAL_PORT      = None        # None = auto-detect ESP32
BAUD_RATE        = 115200
WATER_THRESHOLD  = 1500        # Water level that triggers flood concern
WATER_CRITICAL   = 3200        # Water level = high flood risk
MAX_HISTORY      = 120         # Keep 2 min of readings
MODEL_PATH       = "model.pkl"
DISASTER_MODEL_TARGETS = ("flood_risk", "earthquake_risk", "rain_risk")
RAIN_MAP = {"DRY": 0, "MODERATE": 1, "WET": 2}
VIBRATION_MAP = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

# ================================================================
#  ML MODEL LOAD
# ================================================================
_ml_bundle = None
try:
    try:
        _ml_bundle = joblib.load(MODEL_PATH)
    except Exception:
        with open(MODEL_PATH, "rb") as f:
            _ml_bundle = pickle.load(f)
    print(f"[ML] Model loaded: {MODEL_PATH}")
except FileNotFoundError:
    print(f"[ML] WARNING: {MODEL_PATH} not found. Run train_model.py first. Using rule-based fallback.")
except Exception as e:
    print(f"[ML] ERROR loading model: {e}. Using rule-based fallback.")


# ================================================================
#  SHARED STATE (thread-safe via lock)
# ================================================================
_lock = threading.Lock()

_state = {
    # Raw sensor values
    "rain":       "DRY",
    "water":      0,
    "vibration":  "LOW",

    # Time-based counters (incremented each serial reading ~0.5s)
    "rain_counter": 0,    # ticks of continuous non-DRY rain
    "vib_counter":  0,    # ticks of continuous vibration

    # Rolling histories
    "water_history": deque(maxlen=MAX_HISTORY),
    "risk_history":  deque(maxlen=MAX_HISTORY),

    # Computed risk values (%)
    "flood_risk":       0.0,
    "earthquake_risk":  0.0,
    "rain_risk":        0.0,
    "overall_risk":     0.0,

    # Predictions
    "future_10s":  0.0,
    "future_30s":  0.0,
    "future_60s":  0.0,

    # Status
    "trend":         "STABLE",
    "voice_message": "System initializing.",
    "ai_reasoning":  "Awaiting sensor data.",
    "connected":     False,
    "last_update":   0.0,
    "time_step":     0,
}


# ================================================================
#  ENCODING HELPERS
# ================================================================
def encode_rain(rain_str: str) -> int:
    return RAIN_MAP.get(str(rain_str).upper(), 0)


def risk_level(pct: float) -> int:
    """Convert % risk to 0-3 discrete level."""
    if pct >= 70:  return 3
    if pct >= 45:  return 2
    if pct >= 20:  return 1
    return 0


# ================================================================
#  FEATURE ENGINEERING (must match train_model.py)
# ================================================================
def build_features(rain: str, water: int, vibration: str,
                   rain_duration: float, vib_duration: float,
                   water_trend: float) -> np.ndarray:
    r    = encode_rain(rain)
    w    = float(water)
    v    = 1.0 if vibration == "HIGH" else 0.0
    rd   = float(rain_duration)
    vd   = float(vib_duration)
    wt   = float(water_trend)

    flood_p  = w * rd / (4095 * 100 + 1)
    seis_e   = v * vd
    w_norm   = w / 4095.0
    rain_i   = r * rd / (2 * 100 + 1)
    w_sq     = w_norm ** 2

    return np.array([[r, w, v, rd, vd, wt, flood_p, seis_e, w_norm, rain_i, w_sq]])


# ================================================================
#  RULE-BASED RISK CALCULATION (baseline + fallback when no ML)
# ================================================================
def rule_based_risks(rain: str, water: int, vibration: str,
                     rain_dur: float, vib_dur: float,
                     water_trend: float):
    """
    Returns (flood_risk, earthquake_risk, rain_risk) each 0-100.
    Time-based: longer duration = higher risk.
    """
    water_norm = water / 4095.0

    # ── FLOOD RISK ──────────────────────────────────────────────
    # Water level component (quadratic — floods accelerate)
    water_component = min(water_norm ** 1.6, 1.0)

    # Rain component
    rain_enc = encode_rain(rain)
    rain_component = rain_enc / 2.0

    # Duration component (saturates at 10 min = 600 ticks at 1Hz)
    dur_component = 1 - math.exp(-rain_dur / 200.0)  # smooth saturation

    # Trend bonus: if water is rising fast, boost flood risk
    trend_bonus = min(max(water_trend / 100.0, 0), 0.3)

    flood_risk = (
        water_component * 50
        + rain_component * 20
        + dur_component  * 20
        + trend_bonus    * 10
    )

    # ── EARTHQUAKE RISK ─────────────────────────────────────────
    vib_active = 1.0 if vibration == "HIGH" else 0.0

    # Instantaneous spike
    vib_instant = vib_active * 40.0

    # Duration: sustained vibration = structural threat
    vib_sustained = (1 - math.exp(-vib_dur / 30.0)) * 60.0

    earthquake_risk = vib_instant + vib_sustained * vib_active

    # ── RAIN RISK ────────────────────────────────────────────────
    rain_base_pct = rain_enc * 25.0        # DRY=0, MOD=25, WET=50
    rain_dur_sat  = (1 - math.exp(-rain_dur / 300.0)) * 50.0
    rain_risk = rain_base_pct + rain_dur_sat * min(rain_enc, 1)

    return (
        float(np.clip(flood_risk,     0, 100)),
        float(np.clip(earthquake_risk, 0, 100)),
        float(np.clip(rain_risk,      0, 100)),
    )


def ml_predict_risk(rain, water, vibration, rain_dur, vib_dur, water_trend) -> Optional[float]:
    if _ml_bundle is None:
        return None
    if not isinstance(_ml_bundle, dict) or "model" not in _ml_bundle:
        return None
    try:
        feats = build_features(rain, water, vibration, rain_dur, vib_dur, water_trend)
        pred  = _ml_bundle["model"].predict(feats)[0]
        return float(np.clip(pred, 0, 100))
    except Exception as e:
        print(f"[ML] Prediction error: {e}")
        return None


def _get_disaster_models():
    if not isinstance(_ml_bundle, dict):
        return None

    if all(target in _ml_bundle for target in DISASTER_MODEL_TARGETS):
        return _ml_bundle

    models = _ml_bundle.get("models")
    if isinstance(models, dict) and all(target in models for target in DISASTER_MODEL_TARGETS):
        return models

    return None


def ml_predict_disaster_risks(rain, water, vibration) -> Optional[tuple]:
    try:
        rain_map = {"DRY": 0, "MODERATE": 1, "WET": 2}
        vib_map = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

        rain_val = rain_map.get(rain, 0)
        vib_val = vib_map.get(vibration, 0)

        if _ml_bundle is None:
            return None

        pred = _ml_bundle.predict([[rain_val, water, vib_val]])[0]

        flood_risk = round(pred[0], 2)
        earthquake_risk = round(pred[1], 2)
        rain_risk = round(pred[2], 2)

        return (flood_risk, earthquake_risk, rain_risk)
    except Exception as e:
        print(f"[ML] Disaster model prediction error: {e}")
        return None


# ================================================================
#  TREND & PREDICTION
# ================================================================
def compute_trend(risk_history: deque) -> str:
    if len(risk_history) < 6:
        return "STABLE"
    recent = list(risk_history)[-6:]
    # Fit slope over last 6 readings
    x = np.arange(len(recent), dtype=float)
    slope = np.polyfit(x, recent, 1)[0]
    if slope > 2.5:   return "RISING"
    if slope < -2.5:  return "FALLING"
    return "STABLE"


def predict_future(risk_history: deque, seconds_ahead: int) -> float:
    arr = list(risk_history)
    if len(arr) < 4:
        return arr[-1] if arr else 0.0

    # Use last 20 readings to fit linear + quadratic trend
    recent = arr[-20:]
    n = len(recent)
    x = np.arange(n, dtype=float)
    # Quadratic fit for acceleration awareness
    coeffs = np.polyfit(x, recent, min(2, n - 1))
    future_x = n - 1 + float(seconds_ahead)
    future_val = np.polyval(coeffs, future_x)
    return float(np.clip(future_val, 0, 100))


# ================================================================
#  VOICE & AI REASONING GENERATORS
# ================================================================
def generate_voice_message(flood_r: float, quake_r: float, rain_r: float,
                            overall: float, trend: str,
                            rain: str, water: int, vibration: str) -> str:
    if overall >= 80:
        parts = ["CRITICAL ALERT."]
        if flood_r >= 70:
            parts.append(f"Flood risk at {flood_r:.0f} percent. Immediate valve closure required.")
        if quake_r >= 70:
            parts.append(f"Seismic activity at {quake_r:.0f} percent. Structural risk elevated.")
        parts.append("Evacuate affected zones. Emergency protocols engaged.")
        return " ".join(parts)

    if overall >= 55:
        parts = ["Warning. Elevated risk detected."]
        dominant = max((flood_r, "flood"), (quake_r, "seismic"), (rain_r, "precipitation"))[1]
        parts.append(f"Primary hazard: {dominant}.")
        if trend == "RISING":
            parts.append("Risk is escalating. Prepare response teams.")
        parts.append("Systems on standby.")
        return " ".join(parts)

    if overall >= 25:
        parts = ["Low risk detected."]
        if rain != "DRY":
            parts.append(f"Precipitation level: {rain.lower()}.")
        if vibration == "HIGH":
            parts.append("Minor vibration detected.")
        parts.append("Passive surveillance active.")
        return " ".join(parts)

    # Safe
    if trend == "FALLING":
        return "Risk returning to baseline. Systems stabilizing. All parameters nominal."
    return "All systems stable. Infrastructure healthy. No anomalies detected."


def generate_ai_reasoning(flood_r: float, quake_r: float, rain_r: float,
                           overall: float, trend: str,
                           rain: str, water: int, vibration: str,
                           rain_dur: float, vib_dur: float,
                           water_trend: float,
                           f10: float, f30: float, f60: float) -> str:
    lines = []

    # Overall assessment
    if overall >= 70:
        lines.append(f"⚠️ CRITICAL: Overall infrastructure risk at {overall:.1f}%.")
    elif overall >= 40:
        lines.append(f"⚠️ ELEVATED: Risk at {overall:.1f}% — monitoring closely.")
    else:
        lines.append(f"✅ Risk stable at {overall:.1f}%.")

    # Flood analysis
    if flood_r > 30:
        water_pct = (water / 4095) * 100
        lines.append(
            f"Flood indicators: water level {water:.0f} ADC ({water_pct:.0f}% of max), "
            f"rain status {rain}, continuous rain for {rain_dur:.0f}s. "
            f"Flood risk: {flood_r:.1f}%."
        )

    # Seismic analysis
    if quake_r > 20:
        lines.append(
            f"Seismic indicators: vibration active {vib_dur:.0f}s continuously. "
            f"Earthquake risk: {quake_r:.1f}%."
        )

    # Trend
    trend_msg = {"RISING": "escalating — intervention window narrowing",
                 "FALLING": "de-escalating — recovery in progress",
                 "STABLE": "stable — no immediate change expected"}
    lines.append(f"Trend: {trend_msg.get(trend, 'unknown')}.")

    # Future projection
    if f60 > overall + 10:
        lines.append(f"Projection: risk expected to reach {f60:.0f}% in 60s if trend continues.")
    elif f60 < overall - 10:
        lines.append(f"Projection: risk expected to decrease to {f60:.0f}% in 60s.")

    # Water rising warning
    if water_trend > 30:
        lines.append(f"⚡ Water level rising rapidly ({water_trend:.0f} ADC/s). Flood imminent if sustained.")

    return " ".join(lines)


# ================================================================
#  CORE STATE UPDATE (called after each serial reading)
# ================================================================
def process_reading(rain: str, water: int, vibration: str):
    with _lock:
        previous_risk = float(_state["overall_risk"])
        time_step = int(_state["time_step"]) + 1

        # ── Time-based counters ──────────────────────────────────
        if rain != "DRY":
            _state["rain_counter"] += 1
        else:
            _state["rain_counter"] = max(0, _state["rain_counter"] - 1)

        if vibration == "HIGH":
            _state["vib_counter"] += 1
        else:
            # Faster decay for vibration (not persistent like flooding)
            _state["vib_counter"] = max(0, _state["vib_counter"] - 3)

        rain_dur = float(_state["rain_counter"])
        vib_dur  = float(_state["vib_counter"])

        # ── Water trend ──────────────────────────────────────────
        _state["water_history"].append(float(water))
        wh = list(_state["water_history"])
        if len(wh) >= 6:
            water_trend = (wh[-1] - wh[-6]) / 6.0
        elif len(wh) >= 2:
            water_trend = (wh[-1] - wh[0]) / max(len(wh) - 1, 1)
        else:
            water_trend = 0.0

        # ── Rule-based risks ─────────────────────────────────────
        flood_r, quake_r, rain_r = rule_based_risks(
            rain, water, vibration, rain_dur, vib_dur, water_trend
        )

        rule_overall = flood_r * 0.45 + quake_r * 0.35 + rain_r * 0.20

        ml_pred = ml_predict_risk(rain, water, vibration, rain_dur, vib_dur, water_trend)

        if ml_pred is not None:
            # blend ML + rules
            overall = rule_overall * 0.4 + ml_pred * 0.6
        else:
            overall = rule_overall

        overall = float(np.clip(overall, 0, 100))

        print("ML:", ml_pred, "| RULE:", rule_overall, "| FINAL:", overall)

        # ── Risk history & trend ─────────────────────────────────
        _state["risk_history"].append(overall)

        trend = compute_trend(_state["risk_history"])
        f10   = predict_future(_state["risk_history"], 10)
        f30   = predict_future(_state["risk_history"], 30)
        f60   = predict_future(_state["risk_history"], 60)

        # ── Voice & AI reasoning ─────────────────────────────────
        voice = generate_voice_message(flood_r, quake_r, rain_r, overall, trend, rain, water, vibration)
        ai_reasoning = generate_ai_reasoning(
            flood_r, quake_r, rain_r, overall, trend,
            rain, water, vibration, rain_dur, vib_dur, water_trend,
            f10, f30, f60
        )

        # ── Commit to state ──────────────────────────────────────
        _state.update({
            "rain":           rain,
            "water":          water,
            "vibration":      vibration,
            "flood_risk":     round(flood_r, 1),
            "earthquake_risk":round(quake_r, 1),
            "rain_risk":      round(rain_r, 1),
            "overall_risk":   round(overall, 1),
            "future_10s":     round(f10, 1),
            "future_30s":     round(f30, 1),
            "future_60s":     round(f60, 1),
            "trend":          trend,
            "voice_message":  voice,
            "ai_reasoning":   ai_reasoning,
            "last_update":    time.time(),
            "time_step":      time_step,
        })


# ================================================================
#  SERIAL PORT AUTO-DETECTION
# ================================================================
def find_esp32_port() -> Optional[str]:
    ports = serial.tools.list_ports.comports()
    keywords = ["cp210", "ch340", "ch910", "silicon labs", "usb serial", "uart", "esp"]
    for p in ports:
        desc = (p.description or "").lower()
        if any(k in desc for k in keywords):
            print(f"[SERIAL] ESP32 detected: {p.device} ({p.description})")
            return p.device
    if ports:
        print(f"[SERIAL] Fallback to first port: {ports[0].device}")
        return ports[0].device
    return None


# ================================================================
#  SERIAL READER THREAD
# ================================================================
def serial_reader():
    port = SERIAL_PORT or find_esp32_port()
    if not port:
        print("[SERIAL] No ESP32 found. Start simulator.py for testing.")
        with _lock:
            _state["connected"] = False
        return

    while True:
        try:
            with serial.Serial(port, BAUD_RATE, timeout=2) as ser:
                with _lock:
                    _state["connected"] = True
                print(f"[SERIAL] Connected: {port} @ {BAUD_RATE}")

                while True:
                    raw = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not raw:
                        continue

                    # Skip non-JSON lines (boot messages, debug output)
                    if not (raw.startswith("{") and raw.endswith("}")):
                        continue

                    try:
                        payload = json.loads(raw)
                    except json.JSONDecodeError:
                        continue

                    rain      = str(payload.get("rain", "DRY")).upper()
                    water     = int(payload.get("water", 0))
                    vibration = str(payload.get("vibration", "NO")).upper()

                    # Map vibration to model categories
                    if vibration == "YES":
                        vibration = "HIGH"
                    else:
                        vibration = "LOW"

                    # Validate
                    if rain not in ("DRY", "MODERATE", "WET"):
                        rain = "DRY"
                    water = max(0, min(4095, water))
                    if vibration not in ("HIGH", "LOW"):
                        vibration = "LOW"

                    process_reading(rain, water, vibration)

                    # Optional: send actuation command back to ESP32
                    with _lock:
                        lvl = risk_level(_state["overall_risk"])
                    try:
                        ser.write(f"ACT:{lvl}\n".encode())
                    except Exception:
                        pass

        except serial.SerialException as e:
            print(f"[SERIAL] Disconnected: {e} — retrying in 3s...")
            with _lock:
                _state["connected"] = False
            time.sleep(3)
        except Exception as e:
            print(f"[SERIAL] Error: {e} — retrying in 3s...")
            with _lock:
                _state["connected"] = False
            time.sleep(3)


# Start serial thread
threading.Thread(target=serial_reader, daemon=True).start()


# ================================================================
#  API ENDPOINTS
# ================================================================
@app.get("/")
def root():
    return {"status": "online", "service": "Self-Healing Infrastructure Backend v2.0"}


@app.get("/data")
def get_data():
    with _lock:
        return {
            "rain": _state["rain"],
            "water": int(_state["water"]),
            "vibration": _state["vibration"],
            "flood_risk": int(round(_state["flood_risk"])),
            "earthquake_risk": int(round(_state["earthquake_risk"])),
            "rain_risk": int(round(_state["rain_risk"])),
            "overall_risk": int(round(_state["overall_risk"])),
        }


@app.get("/history")
def get_history():
    with _lock:
        return {
            "water_history": list(_state["water_history"]),
            "risk_history":  list(_state["risk_history"]),
        }


@app.get("/status")
def get_status():
    with _lock:
        return {
            "connected":  _state["connected"],
            "last_update": _state["last_update"],
            "ml_loaded":  _ml_bundle is not None,
        }
