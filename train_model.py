"""
train_model.py
Generates synthetic training data and trains a RandomForest risk predictor.
Run once before starting backend.py:  python train_model.py
Saves: model.pkl
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler
import pickle
import os

RANDOM_SEED = 42
N_SAMPLES   = 8000

np.random.seed(RANDOM_SEED)


# ================================================================
#  FEATURE DEFINITIONS
#  rain_encoded     : 0=DRY, 1=MODERATE, 2=WET
#  water_level      : 0–4095 (ADC raw)
#  vibration        : 0 or 1
#  rain_duration    : seconds of continuous non-DRY rain
#  vib_duration     : seconds of continuous vibration
#  water_trend      : delta water/second (positive = rising)
# ================================================================

def generate_scenario(n, scenario):
    """Generate n samples for a named scenario with realistic correlations."""
    data = []

    for _ in range(n):
        if scenario == "normal":
            rain_enc   = np.random.choice([0, 1], p=[0.85, 0.15])
            water      = np.random.randint(200, 900)
            vib        = 0
            rain_dur   = np.random.exponential(5) if rain_enc > 0 else 0
            vib_dur    = 0
            water_trend= np.random.uniform(-5, 8)
            risk       = np.random.uniform(0, 15)

        elif scenario == "light_rain":
            rain_enc   = np.random.choice([1, 2], p=[0.7, 0.3])
            water      = np.random.randint(600, 1600)
            vib        = 0
            rain_dur   = np.random.uniform(10, 120)
            vib_dur    = 0
            water_trend= np.random.uniform(0, 20)
            risk       = np.random.uniform(10, 35)

        elif scenario == "heavy_rain":
            rain_enc   = 2
            water      = np.random.randint(1400, 3200)
            vib        = 0
            rain_dur   = np.random.uniform(60, 600)
            vib_dur    = 0
            water_trend= np.random.uniform(10, 60)
            risk       = np.random.uniform(40, 80)

        elif scenario == "flood":
            rain_enc   = 2
            water      = np.random.randint(2800, 4095)
            vib        = np.random.choice([0, 1], p=[0.6, 0.4])
            rain_dur   = np.random.uniform(300, 1800)
            vib_dur    = np.random.uniform(0, 30) if vib else 0
            water_trend= np.random.uniform(30, 100)
            risk       = np.random.uniform(70, 100)

        elif scenario == "vibration_mild":
            rain_enc   = np.random.choice([0, 1], p=[0.7, 0.3])
            water      = np.random.randint(200, 1200)
            vib        = 1
            rain_dur   = np.random.exponential(15) if rain_enc > 0 else 0
            vib_dur    = np.random.uniform(2, 20)
            water_trend= np.random.uniform(-5, 15)
            risk       = np.random.uniform(20, 50)

        elif scenario == "earthquake":
            rain_enc   = np.random.choice([0, 1, 2], p=[0.5, 0.3, 0.2])
            water      = np.random.randint(400, 2000)
            vib        = 1
            rain_dur   = np.random.exponential(30) if rain_enc > 0 else 0
            vib_dur    = np.random.uniform(15, 120)
            water_trend= np.random.uniform(-10, 30)
            risk       = np.random.uniform(55, 95)

        elif scenario == "combined_disaster":
            rain_enc   = 2
            water      = np.random.randint(2500, 4095)
            vib        = 1
            rain_dur   = np.random.uniform(200, 1200)
            vib_dur    = np.random.uniform(30, 180)
            water_trend= np.random.uniform(40, 120)
            risk       = np.random.uniform(85, 100)

        else:  # random noise
            rain_enc   = np.random.choice([0, 1, 2])
            water      = np.random.randint(0, 4095)
            vib        = np.random.choice([0, 1])
            rain_dur   = np.random.uniform(0, 300)
            vib_dur    = np.random.uniform(0, 60)
            water_trend= np.random.uniform(-20, 100)
            risk       = np.random.uniform(0, 100)

        # Add small noise to risk label for realism
        risk = float(np.clip(risk + np.random.normal(0, 2), 0, 100))

        data.append({
            "rain_encoded":     float(rain_enc),
            "water_level":      float(water),
            "vibration":        float(vib),
            "rain_duration":    float(max(rain_dur, 0)),
            "vib_duration":     float(max(vib_dur, 0)),
            "water_trend":      float(water_trend),
            "overall_risk":     risk,
        })

    return data


def build_dataset(n_total):
    scenarios = {
        "normal":             0.25,
        "light_rain":         0.15,
        "heavy_rain":         0.15,
        "flood":              0.10,
        "vibration_mild":     0.12,
        "earthquake":         0.10,
        "combined_disaster":  0.08,
        "random_noise":       0.05,
    }

    rows = []
    for scenario, frac in scenarios.items():
        n = max(1, int(n_total * frac))
        rows.extend(generate_scenario(n, scenario))

    return pd.DataFrame(rows)


def add_derived_features(df):
    """Feature engineering to improve model accuracy."""
    df = df.copy()

    # Interaction features
    df["flood_pressure"] = df["water_level"] * df["rain_duration"] / (4095 * 100 + 1)
    df["seismic_energy"] = df["vibration"] * df["vib_duration"]
    df["water_level_norm"] = df["water_level"] / 4095.0
    df["rain_intensity"] = df["rain_encoded"] * df["rain_duration"] / (2 * 100 + 1)

    # Polynomial feature on water_level (flood risk accelerates)
    df["water_sq"] = df["water_level_norm"] ** 2

    return df


def train():
    print("=" * 55)
    print("  Self-Predictive Infrastructure — ML Model Training")
    print("=" * 55)

    print(f"\n[1/5] Generating {N_SAMPLES} synthetic training samples...")
    df = build_dataset(N_SAMPLES)
    df = add_derived_features(df)
    print(f"      Dataset shape: {df.shape}")

    feature_cols = [
        "rain_encoded", "water_level", "vibration",
        "rain_duration", "vib_duration", "water_trend",
        "flood_pressure", "seismic_energy", "water_level_norm",
        "rain_intensity", "water_sq",
    ]
    X = df[feature_cols].values
    y = df["overall_risk"].values

    print(f"\n[2/5] Splitting data (80/20)...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=RANDOM_SEED
    )

    print(f"\n[3/5] Training RandomForestRegressor...")
    model = RandomForestRegressor(
        n_estimators=200,
        max_depth=12,
        min_samples_split=4,
        min_samples_leaf=2,
        max_features="sqrt",
        random_state=RANDOM_SEED,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    print(f"\n[4/5] Evaluating model...")
    y_pred = model.predict(X_test)
    mae  = mean_absolute_error(y_test, y_pred)
    r2   = r2_score(y_test, y_pred)
    print(f"      MAE  : {mae:.2f}%  (mean absolute error in risk %)")
    print(f"      R²   : {r2:.4f}")
    print(f"      RMSE : {np.sqrt(np.mean((y_test - y_pred)**2)):.2f}%")

    # Feature importances
    importances = sorted(
        zip(feature_cols, model.feature_importances_),
        key=lambda x: x[1], reverse=True
    )
    print(f"\n      Top feature importances:")
    for feat, imp in importances[:5]:
        print(f"        {feat:<22} {imp:.4f}")

    print(f"\n[5/5] Saving model to model.pkl ...")
    bundle = {
        "model":        model,
        "feature_cols": feature_cols,
        "version":      "1.0",
    }
    with open("model.pkl", "wb") as f:
        pickle.dump(bundle, f)

    print(f"\n✅ Model saved: model.pkl")
    print(f"   Features : {len(feature_cols)}")
    print(f"   Trees    : {model.n_estimators}")
    print(f"   MAE      : {mae:.2f}%")
    print("=" * 55)

    # Quick sanity check
    print("\n[SANITY] Quick prediction tests:")
    tests = [
        {"name": "All clear",        "inp": [0, 300,  0,   0,  0,  0]},
        {"name": "Moderate rain",    "inp": [1, 1200, 0,  60,  0, 10]},
        {"name": "Heavy flood",      "inp": [2, 3500, 0, 600,  0, 80]},
        {"name": "Earthquake",       "inp": [0, 500,  1,   0, 60,  0]},
        {"name": "Combined disaster","inp": [2, 3800, 1, 900, 90, 70]},
    ]
    for t in tests:
        # Build full feature vector with derived features
        r, w, v, rd, vd, wt = t["inp"]
        flood_p = w * rd / (4095 * 100 + 1)
        seis_e  = v * vd
        w_norm  = w / 4095.0
        rain_i  = r * rd / (2 * 100 + 1)
        w_sq    = w_norm ** 2
        feat = np.array([[r, w, v, rd, vd, wt, flood_p, seis_e, w_norm, rain_i, w_sq]])
        pred = model.predict(feat)[0]
        print(f"  {t['name']:<22} → {pred:.1f}%")


if __name__ == "__main__":
    train()