## Progress Log — code-Shark

### Day 1 — System Setup
- Defined problem: early warning for infrastructure failure
- Selected sensors: rain, water level, vibration (ESP32)
- Built basic ESP32 firmware for raw sensor output
- Established serial communication with backend

### Day 2 — Backend + Dashboard
- Developed FastAPI backend to receive sensor data
- Implemented real-time dashboard (Streamlit)
- Added live telemetry (rain, water, vibration)
- Designed initial risk calculation logic

### Day 3 — ML Integration
- Collected datasets (rainfall, flood, earthquake)
- Built preprocessing pipeline for unified dataset
- Trained RandomForest model for risk prediction
- Integrated ML model into backend

### Day 4 — Prediction & Automation
- Implemented timeline-based risk prediction
- Separated risk types (flood, earthquake, rain)
- Added actuator control (servo as dam gate)
- Enabled automatic response based on flood risk

### Final — Optimization & Testing
- Improved data balancing and model accuracy
- Cleaned repository and structured code
- Verified real-time system flow (ESP32 → Backend → Dashboard)
- Final testing and debugging

### Next Improvements
- Add alert notifications (SMS / mobile)
- Enhance prediction accuracy with more data
- Deploy system for real-world usage