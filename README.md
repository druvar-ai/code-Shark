# code-Shark — AI-Powered Infrastructure Safety System

An intelligent early warning system that predicts and prevents infrastructure disasters using real-time IoT data and machine learning.

---

## Problem

Infrastructure failures (floods, structural damage, seismic activity) often occur without timely warnings, leading to loss of life and property.

---

## Solution

code-Shark uses ESP32-based sensors and machine learning to:
- Monitor environmental conditions in real time
- Predict disaster risks (Flood, Earthquake, Rain)
- Automatically trigger preventive actions (e.g., dam gate control)

---

## System Architecture

ESP32 Sensors → Serial Data → FastAPI Backend → ML Model → Dashboard → Actuator Control

---

## Features

-  Real-time sensor monitoring (rain, water level, vibration)
-  Multi-risk prediction (Flood, Earthquake, Rain)
-  ML-based risk analysis (RandomForest)
-  Timeline-based future prediction
-  Automated dam gate control using servo motor
-  Live dashboard with risk visualization

---

##  Tech Stack

- **Hardware:** ESP32, Sensors (Rain, Water Level, Vibration), Servo
- **Backend:** FastAPI (Python)
- **Frontend:** Streamlit Dashboard
- **ML:** Scikit-learn (RandomForest)
- **Data:** Kaggle datasets (weather, flood, earthquake)

---

##  How to Run

# Install dependencies
```bash
pip install -r requirements.txt
# Train ML model
python preprocess.py
python train_model.py

# Start backend
uvicorn backend:app --reload

# Run dashboard
streamlit run app.py

# (Optional) Run simulator
python simulator.py