"""
preprocess.py
Loads real-world CSVs (if available) from ./data/ directory,
applies feature engineering, and saves final_dataset.csv for training.

If no real CSVs are present, generates a fully synthetic dataset
with realistic disaster physics.

Run:  python preprocess.py
Then: python train_model.py
"""

import os
import numpy as np
import pandas as pd

DATA_DIR     = "data"
OUTPUT_FILE  = "final_dataset.csv"
RANDOM_SEED  = 42

np.random.seed(RANDOM_SEED)

# ================================================================
#  REAL DATASET COLUMN MAPPINGS
#  Map known public dataset column names → our internal names.
#  Add entries here if you attach different CSVs.
# ================================================================
COLUMN_MAPS = {
    # Rain / rainfall datasets
    "rainfall":         "rainfall_mm",
    "rainfall_mm":      "rainfall_mm",
    "rain":             "rainfall_mm",
    "precipitation":    "rainfall_mm",
    "prcp":             "rainfall_mm",

    # Water level / flood datasets
    "water_level":      "water_level",
    "water level (m)":  "water_level",
    "stage":            "water_level",
    "level":            "water_level",
    "discharge":        "water_level",
    "flood_occurred":   "flood_label",
    "flood occurred":   "flood_label",
    "flood":            "flood_label",

    # Earthquake / vibration datasets
    "magnitude":        "magnitude",
    "mag":              "magnitude",
    "richter":          "magnitude",
    "seismic_activity": "magnitude",
}


# ================================================================
#  HELPER: NORMALISE COLUMN NAMES
# ================================================================
def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lower() for c in df.columns]
    rename = {}
    for col in df.columns:
        if col in COLUMN_MAPS:
            rename[col] = COLUMN_MAPS[col]
    return df.rename(columns=rename)


# ================================================================
#  LOAD CSVs FROM ./data/
# ================================================================
def load_csvs() -> dict:
    datasets = {}
    if not os.path.isdir(DATA_DIR):
        print(f"[PREPROCESS] No ./data/ directory found — using synthetic data only.")
        return datasets

    for fname in os.listdir(DATA_DIR):
        if not fname.lower().endswith(".csv"):
            continue
        path = os.path.join(DATA_DIR, fname)
        try:
            df = pd.read_csv(path, low_memory=False)
            df = normalise_columns(df)
            datasets[fname] = df
            print(f"[PREPROCESS] Loaded: {fname}  ({len(df)} rows, cols: {list(df.columns)[:6]}...)")
        except Exception as e:
            print(f"[PREPROCESS] Skipping {fname}: {e}")

    return datasets


# ================================================================
#  EXTRACT USEFUL ROWS FROM REAL DATA
# ================================================================
def extract_rain_features(datasets: dict) -> pd.DataFrame:
    """Pull rainfall_mm from any suitable CSV."""
    frames = []
    for name, df in datasets.items():
        if "rainfall_mm" not in df.columns:
            continue
        sub = df[["rainfall_mm"]].dropna()
        sub["rainfall_mm"] = pd.to_numeric(sub["rainfall_mm"], errors="coerce")
        sub = sub.dropna()
        frames.append(sub)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def extract_water_features(datasets: dict) -> pd.DataFrame:
    frames = []
    for name, df in datasets.items():
        if "water_level" not in df.columns:
            continue
        sub = df[["water_level"]].dropna()
        sub["water_level"] = pd.to_numeric(sub["water_level"], errors="coerce")
        sub = sub.dropna()
        # Normalise to 0-10000 scale if values look like meters (0-20)
        if sub["water_level"].max() < 50:
            sub["water_level"] = sub["water_level"] * 500
        frames.append(sub)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def extract_vibration_features(datasets: dict) -> pd.DataFrame:
    frames = []
    for name, df in datasets.items():
        if "magnitude" not in df.columns:
            continue
        sub = df[["magnitude"]].dropna()
        sub["magnitude"] = pd.to_numeric(sub["magnitude"], errors="coerce")
        sub = sub.dropna()
        frames.append(sub)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ================================================================
#  SYNTHETIC DATA GENERATOR (physics-inspired)
# ================================================================
def generate_synthetic(n: int = 10000) -> pd.DataFrame:
    """
    Generate realistic samples covering all disaster scenarios.
    Returns DataFrame with full feature set + risk labels.
    """
    print(f"[PREPROCESS] Generating {n} synthetic samples...")
    rows = []

    scenarios = {
        "normal":           {"n_frac": 0.25, "rain_range": (0, 1),   "water_range": (100,  1000), "vib_p": 0.02, "risk_range": (0,  18)},
        "light_rain":       {"n_frac": 0.12, "rain_range": (1, 2),   "water_range": (500,  1800), "vib_p": 0.01, "risk_range": (8,  30)},
        "heavy_rain":       {"n_frac": 0.12, "rain_range": (2, 2),   "water_range": (1500, 4000), "vib_p": 0.02, "risk_range": (35, 70)},
        "flood":            {"n_frac": 0.10, "rain_range": (2, 2),   "water_range": (3500, 9500), "vib_p": 0.05, "risk_range": (65,100)},
        "mild_vibration":   {"n_frac": 0.10, "rain_range": (0, 1),   "water_range": (100,  1500), "vib_p": 0.90, "risk_range": (15, 45)},
        "earthquake":       {"n_frac": 0.10, "rain_range": (0, 2),   "water_range": (100,  3000), "vib_p": 0.98, "risk_range": (55, 95)},
        "combined":         {"n_frac": 0.08, "rain_range": (2, 2),   "water_range": (4000, 9800), "vib_p": 0.90, "risk_range": (80,100)},
        "recovery":         {"n_frac": 0.08, "rain_range": (0, 1),   "water_range": (800,  3500), "vib_p": 0.05, "risk_range": (10, 50)},
        "noise":            {"n_frac": 0.05, "rain_range": (0, 2),   "water_range": (0,   10000), "vib_p": 0.50, "risk_range": (0, 100)},
    }

    for scen, cfg in scenarios.items():
        n_s = max(1, int(n * cfg["n_frac"]))
        r_lo, r_hi = cfg["rain_range"]
        w_lo, w_hi = cfg["water_range"]

        for _ in range(n_s):
            # Raw sensor values
            rain_enc  = int(np.random.randint(r_lo, r_hi + 1))
            water     = float(np.random.uniform(w_lo, w_hi))
            vibration = 1 if np.random.random() < cfg["vib_p"] else 0

            # Duration features (simulate history)
            rain_dur  = float(np.random.exponential(30)) if rain_enc > 0 else 0.0
            vib_dur   = float(np.random.exponential(20)) if vibration else 0.0
            water_trend = float(np.random.uniform(-30, 80)) if rain_enc > 0 else float(np.random.uniform(-10, 10))

            # Risk labels
            risk_lo, risk_hi = cfg["risk_range"]
            overall_risk = float(np.random.uniform(risk_lo, risk_hi))
            # Add physics-based noise
            overall_risk += float(np.random.normal(0, 3))
            overall_risk  = float(np.clip(overall_risk, 0, 100))

            # Individual risks derived from overall + scenario
            flood_base  = overall_risk * 0.6 + (water / 10000.0) * 30
            quake_base  = overall_risk * 0.5 + vibration * vib_dur * 0.4
            rain_base   = overall_risk * 0.4 + rain_enc * 20 + (rain_dur / 100.0) * 15

            flood_risk  = float(np.clip(flood_base  + np.random.normal(0, 4), 0, 100))
            quake_risk  = float(np.clip(quake_base  + np.random.normal(0, 4), 0, 100))
            rain_risk   = float(np.clip(rain_base   + np.random.normal(0, 4), 0, 100))

            rows.append({
                "rain_encoded":  rain_enc,
                "water":         water,
                "vibration":     vibration,
                "rain_duration": rain_dur,
                "vib_duration":  vib_dur,
                "water_trend":   water_trend,
                "flood_risk":    flood_risk,
                "earthquake_risk": quake_risk,
                "rain_risk":     rain_risk,
                "overall_risk":  overall_risk,
            })

    return pd.DataFrame(rows)


# ================================================================
#  MERGE REAL + SYNTHETIC DATA
# ================================================================
def merge_with_real(synth_df: pd.DataFrame, datasets: dict) -> pd.DataFrame:
    rain_df  = extract_rain_features(datasets)
    water_df = extract_water_features(datasets)
    vib_df   = extract_vibration_features(datasets)

    extra_rows = []

    # Augment synthetic rows with real distribution samples
    if not rain_df.empty:
        print(f"[PREPROCESS] Augmenting with {len(rain_df)} real rain readings...")
        for _, row in rain_df.sample(min(len(rain_df), 1000), random_state=RANDOM_SEED).iterrows():
            mm = row["rainfall_mm"]
            if mm > 150:  rain_enc, risk_add = 2, 40
            elif mm > 50: rain_enc, risk_add = 1, 20
            else:         rain_enc, risk_add = 0, 0
            water = float(np.clip(mm * 30 + np.random.normal(0, 200), 0, 10000))
            overall_risk = float(np.clip(risk_add + np.random.uniform(0, 25) + np.random.normal(0, 3), 0, 100))
            extra_rows.append({
                "rain_encoded": rain_enc, "water": water, "vibration": 0,
                "rain_duration": float(np.random.uniform(0, 200)),
                "vib_duration": 0.0, "water_trend": float(mm / 50),
                "flood_risk": float(np.clip(overall_risk * 0.7, 0, 100)),
                "earthquake_risk": float(np.random.uniform(0, 10)),
                "rain_risk": float(np.clip(rain_enc * 25 + np.random.uniform(0, 20), 0, 100)),
                "overall_risk": overall_risk,
            })

    if not water_df.empty:
        print(f"[PREPROCESS] Augmenting with {len(water_df)} real water level readings...")
        for _, row in water_df.sample(min(len(water_df), 800), random_state=RANDOM_SEED).iterrows():
            wl = float(np.clip(row["water_level"], 0, 10000))
            rain_enc = 2 if wl > 6000 else (1 if wl > 2000 else 0)
            overall_risk = float(np.clip((wl / 10000) * 90 + np.random.normal(0, 5), 0, 100))
            extra_rows.append({
                "rain_encoded": rain_enc, "water": wl, "vibration": 0,
                "rain_duration": float(np.random.uniform(0, 300)),
                "vib_duration": 0.0, "water_trend": float(np.random.uniform(-10, 60)),
                "flood_risk": float(np.clip(overall_risk * 1.1, 0, 100)),
                "earthquake_risk": float(np.random.uniform(0, 15)),
                "rain_risk": float(np.clip(rain_enc * 25 + np.random.uniform(0, 20), 0, 100)),
                "overall_risk": overall_risk,
            })

    if not vib_df.empty:
        print(f"[PREPROCESS] Augmenting with {len(vib_df)} real vibration/earthquake readings...")
        for _, row in vib_df.sample(min(len(vib_df), 600), random_state=RANDOM_SEED).iterrows():
            mag = float(np.clip(row["magnitude"], 0, 10))
            vib = 1 if mag >= 3.5 else 0
            vib_dur = float(mag * 5 + np.random.uniform(0, 20))
            quake_risk = float(np.clip(mag * 12 + np.random.normal(0, 5), 0, 100))
            overall_risk = float(np.clip(quake_risk * 0.8 + np.random.uniform(0, 15), 0, 100))
            extra_rows.append({
                "rain_encoded": 0, "water": float(np.random.uniform(100, 1000)),
                "vibration": vib, "rain_duration": 0.0,
                "vib_duration": vib_dur,
                "water_trend": float(np.random.uniform(-5, 5)),
                "flood_risk": float(np.random.uniform(0, 20)),
                "earthquake_risk": quake_risk,
                "rain_risk": float(np.random.uniform(0, 10)),
                "overall_risk": overall_risk,
            })

    if extra_rows:
        extra_df = pd.DataFrame(extra_rows)
        merged   = pd.concat([synth_df, extra_df], ignore_index=True)
        print(f"[PREPROCESS] Merged dataset: {len(merged)} rows total.")
        return merged

    return synth_df


# ================================================================
#  FEATURE ENGINEERING
# ================================================================
def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Interaction features (physics-inspired)
    df["flood_pressure"] = (df["water"] * df["rain_duration"]) / (10000 * 100 + 1)
    df["seismic_energy"] = df["vibration"] * df["vib_duration"]
    df["water_norm"]     = df["water"] / 10000.0
    df["rain_intensity"] = df["rain_encoded"] * df["rain_duration"] / (2 * 100 + 1)
    df["water_sq"]       = df["water_norm"] ** 2

    # Time-exponential saturation (more physically accurate)
    df["rain_sat"]       = 1 - np.exp(-df["rain_duration"] / 200.0)
    df["vib_sat"]        = 1 - np.exp(-df["vib_duration"]  / 30.0)

    return df


# ================================================================
#  VALIDATION
# ================================================================
def validate(df: pd.DataFrame) -> pd.DataFrame:
    print("\n[PREPROCESS] === VALIDATION ===")
    print(f"  Total rows        : {len(df)}")
    print(f"  Null values:\n{df.isnull().sum().to_string()}")
    print(f"\n  Rain distribution :")
    print(f"    DRY(0)={len(df[df.rain_encoded==0])}, MOD(1)={len(df[df.rain_encoded==1])}, WET(2)={len(df[df.rain_encoded==2])}")
    print(f"  Vibration         : {df.vibration.value_counts().to_dict()}")
    print(f"  Overall risk      : min={df.overall_risk.min():.1f}  max={df.overall_risk.max():.1f}  mean={df.overall_risk.mean():.1f}")
    print(f"  Water range       : {df.water.min():.0f} – {df.water.max():.0f}")

    # Drop rows with nulls after engineering
    before = len(df)
    df = df.dropna()
    if len(df) < before:
        print(f"  Dropped {before - len(df)} null rows.")

    return df


# ================================================================
#  MAIN
# ================================================================
def main():
    print("=" * 55)
    print("  Self-Healing Infrastructure — Data Preprocessing")
    print("=" * 55)

    # Step 1: Load any real CSVs
    datasets = load_csvs()

    # Step 2: Synthetic base
    synth_df = generate_synthetic(n=10000)

    # Step 3: Merge with real data
    merged_df = merge_with_real(synth_df, datasets)

    # Step 4: Feature engineering
    print("\n[PREPROCESS] Applying feature engineering...")
    final_df = engineer_features(merged_df)

    # Step 5: Validate
    final_df = validate(final_df)

    # Step 6: Save
    final_df.to_csv(OUTPUT_FILE, index=False)
    print(f"\n✅ Saved: {OUTPUT_FILE}  ({len(final_df)} rows, {len(final_df.columns)} features)")
    print(f"\n   Columns: {list(final_df.columns)}")
    print("=" * 55)
    print("\nNext step:  python train_model.py")


if __name__ == "__main__":
    main()