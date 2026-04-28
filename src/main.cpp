/*
 * Self-Healing Smart Infrastructure System
 * ESP32 Firmware — Raw Sensor Output Only
 * All risk logic lives in backend.py
 */

#include <Arduino.h>
#include <ESP32Servo.h>


Servo gateServo;
String command = "";
int currentLevel = -1;
// ===== PIN DEFINITIONS =====
#define RAIN_AO    34   // Rain sensor analog (intensity)
#define RAIN_DO    21   // Rain sensor digital (wet/dry threshold)
#define WATER_PIN  35   // Water level sensor analog
#define VIB_PIN    27   // Vibration sensor digital


#define GREEN_LED 26
#define RED1 25
#define RED2 33
#define RED3 18
#define SERVO_PIN  13   // Valve actuator

// ===== CALIBRATION =====
#define RAIN_WET_THRESHOLD  1800   // ADC below this = WET
#define RAIN_MOD_THRESHOLD  3000   // ADC below this = MODERATE
#define WATER_ADC_SAMPLES   8      // Averaging samples for stability

void driveActuators(int riskLevel) {
  // riskLevel 0-3 sent back from backend via serial (optional feature)
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(RED1, LOW);
  digitalWrite(RED2, LOW);
  digitalWrite(RED3, LOW);

  switch (riskLevel) {
    case 0:
      digitalWrite(GREEN_LED, HIGH);
      break;
    case 1:
      digitalWrite(RED1, HIGH);
      break;
    case 2:
      digitalWrite(RED1, HIGH);
      digitalWrite(RED2, HIGH);
      break;
    case 3:
      digitalWrite(RED1, HIGH);
      digitalWrite(RED2, HIGH);
      digitalWrite(RED3, HIGH);
      break;
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  gateServo.attach(13);  // same as your SERVO_PIN
  gateServo.write(0);    // start OPEN
  pinMode(RAIN_DO, INPUT);
  pinMode(VIB_PIN, INPUT);
  pinMode(GREEN_LED, OUTPUT);
  pinMode(RED1, OUTPUT);
  pinMode(RED2, OUTPUT);
  pinMode(RED3, OUTPUT);

  // All LEDs off initially
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(RED1, LOW);
  digitalWrite(RED2, LOW);
  digitalWrite(RED3, LOW);

  delay(200);
  Serial.println("{\"status\":\"BOOT_OK\"}");
}

void controlGate(int lvl) {
  if (lvl == currentLevel) return; // prevent jitter

  currentLevel = lvl;

  int angle;

  switch (lvl) {
    case 0:
    case 1:
      angle = 0;   // OPEN
      break;
    case 2:
      angle = 45;  // PARTIAL
      break;
    case 3:
      angle = 90;  // CLOSED
      break;
    default:
      angle = 0;
  }

  gateServo.write(angle);
}
void readCommand() {
  while (Serial.available()) {
    char c = Serial.read();

    if (c == '\n') {
      if (command.startsWith("ACT:")) {
        int lvl = command.substring(4).toInt();
        controlGate(lvl);
      }
      command = "";
    } else {
      command += c;
    }
  }
}
void loop() {

  readCommand();

  // ===== READ RAIN =====
  int rainRaw = analogRead(RAIN_AO);
  int rainDO  = digitalRead(RAIN_DO);

  String rainStatus;
  if (rainDO == LOW || rainRaw < RAIN_WET_THRESHOLD) {
    rainStatus = "WET";
  } else if (rainRaw < RAIN_MOD_THRESHOLD) {
    rainStatus = "MODERATE";
  } else {
    rainStatus = "DRY";
  }

  // ===== WATER =====
  long waterSum = 0;
  for (int i = 0; i < WATER_ADC_SAMPLES; i++) {
    waterSum += analogRead(WATER_PIN);
    delay(2);
  }
  int waterRaw = waterSum / WATER_ADC_SAMPLES;

  // ===== VIBRATION =====
  String vibStatus = digitalRead(VIB_PIN) ? "YES" : "NO";

  // ===== RISK CALCULATION (0–100) =====
  int riskScore = 0;

  // Rain impact
  if (rainStatus == "WET") {
    riskScore += 40;
  } else if (rainStatus == "MODERATE") {
    riskScore += 20;
  }

  // Water impact (dominant factor)
  int waterPercent = map(waterRaw, 500, 3000, 0, 100);
  waterPercent = constrain(waterPercent, 0, 100);
  riskScore += waterPercent * 7 / 10;

  // Vibration impact
  if (vibStatus == "YES") {
    riskScore += 30;
  }

  // Clamp
  if (riskScore > 100) riskScore = 100;

  // ===== CONVERT TO LEVEL =====
  int fallbackLevel;

  if (riskScore < 25) fallbackLevel = 0;
  else if (riskScore < 50) fallbackLevel = 1;
  else if (riskScore < 75) fallbackLevel = 2;
  else fallbackLevel = 3;

  // ===== FINAL DECISION =====
  // Backend only overrides if HIGH risk
  int riskLevel;

  if (currentLevel >= 2) {
    riskLevel = currentLevel;
  } else {
    riskLevel = fallbackLevel;
  }

  // ===== DEBUG =====
  Serial.print("WaterRaw: "); Serial.print(waterRaw);
  Serial.print(" | Water%: "); Serial.print(waterPercent);
  Serial.print(" | Score: "); Serial.print(riskScore);
  Serial.print(" | Level: "); Serial.println(riskLevel);

  // ===== ACTUATION =====
  driveActuators(riskLevel);

  // ===== SEND JSON =====
  Serial.print("{\"rain\":\"");
  Serial.print(rainStatus);
  Serial.print("\",\"water\":");
  Serial.print(waterRaw);
  Serial.print(",\"vibration\":\"");
  Serial.print(vibStatus);
  Serial.println("\"}");

  delay(500);
}