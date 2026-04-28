'''
import pandas as pd
import os

files = [
    "data/india_weather_rainfall_data.csv",
    "data/flood_risk_dataset_india.csv",
    "data/earthquake_data_tsunami.csv"
]

for f in files:
    print("\nChecking:", f)

    if not os.path.exists(f):
        print("❌ File NOT FOUND")
        continue

    df = pd.read_csv(f)
    print("✅ Loaded")
    print("Columns:", df.columns.tolist())
    '''