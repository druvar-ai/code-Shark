# ⚡ code-Shark — Real-Time Disaster Prediction & Automated Dam Control System

A real-time **self-predictive infrastructure system** that monitors environmental conditions, predicts disaster risks, and automatically triggers preventive actions such as dam gate control.

---

## 🔍 Problem

Floods and structural failures often occur **without early warning**, leading to delayed response and severe damage.

Existing systems are:
- Reactive (respond after failure)
- Limited to single-risk detection
- Lacking real-time automation

---

## 🚀 Solution

**code-Shark** integrates IoT + Machine Learning to create a **predictive and automated safety system**.

It:
- Continuously monitors environmental conditions  
- Predicts disaster risks in real time  
- Automatically triggers preventive actions (e.g., dam gate control)  

---

## 🏗️ System Architecture

---

## ⚙️ Features

- 📡 Real-time sensor monitoring (rain, water level, vibration)  
- 🧠 Multi-risk prediction (Flood, Earthquake, Rain)  
- 🤖 ML-based risk analysis (Random Forest)  
- 📈 Future risk prediction (10s, 30s, 60s)  
- ⚡ Automated dam gate control using servo motor  
- 📊 Live dashboard with real-time visualization  

---

## 🧠 Why This Matters

### 🔗 End-to-End System  
Combines **hardware + ML + automation** — not just simulation or prediction.

### ⚡ Prediction + Action  
Goes beyond prediction by **automatically controlling infrastructure** (dam gate).

### 📡 Real-Time Intelligence  
Processes **live sensor data**, not static datasets.

### 💸 Low-Cost & Deployable  
Built with ESP32 and affordable sensors → practical for real-world use.

### 🌐 Multi-Risk Awareness  
Simultaneously evaluates:
- Flood risk  
- Earthquake risk  
- Rainfall impact  

---

## 🛠️ Tech Stack

- **Hardware:** ESP32, Rain Sensor, Water Level Sensor, Vibration Sensor, Servo Motor  
- **Backend:** FastAPI (Python)  
- **Frontend:** Streamlit Dashboard  
- **Machine Learning:** Scikit-learn (Random Forest)  
- **Data:** Kaggle datasets (weather, flood, earthquake)  

---
## 🎥 Demo Video
This video demonstrates real-time sensor input, risk prediction, and automated response.
[Watch Demo](https://drive.google.com/file/d/1IZu_eGx6h3srM2G9VE9Ag8M9N6jW14an/view?usp=sharing)

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
