# code-Shark — Real-Time Disaster Prediction & Automated Dam Control System

A real-time self-predictive system that monitors environmental conditions, predicts disaster risk, and automatically triggers preventive actions such as dam gate control.
---

## Problem

Infrastructure failures
Floods and structural failures in India often occur without real-time warning systems, leading to unpreventable damage and delayed response.

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

## Why This Matters

Unlike typical hackathon projects that focus only on prediction or only on hardware, code-Shark integrates real-time sensing, machine learning, and automated response into a single system.

End-to-End System
Combines ESP32 sensors, ML prediction, and live dashboard — not just a simulation.
Not Just Prediction — Action
Automatically triggers dam gate control using a servo motor when flood risk is high.
Real-Time Intelligence
Processes live sensor data (rain, water level, vibration) instead of static datasets.
Low-Cost & Deployable
Built using affordable sensors and ESP32, making it practical for real-world use in vulnerable regions.
Multi-Risk Awareness
Simultaneously evaluates flood, earthquake, and rainfall risks — most systems handle only one.

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
