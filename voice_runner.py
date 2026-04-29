import time
import requests
import pyttsx3
from voice_engine import build_voice_output

engine = pyttsx3.init()
engine.setProperty('rate', 175)

last_spoken = ""

def get_data():
    try:
        res = requests.get("http://127.0.0.1:8001/voice", timeout=1)
        data = res.json()

        return {
            "flood": int(data["flood"]),
            "rain": int(data["rain"]),
            "earthquake": int(data["earthquake"]),
            "vibration": data["vibration"]
        }
    except:
        return {
            "flood": 0,
            "rain": 0,
            "earthquake": 0,
            "vibration": "NO"
        }

def run_voice():
    global last_spoken

    while True:
        data = get_data()

        output = build_voice_output(
            data["flood"],
            data["rain"],
            data["earthquake"],
            data["vibration"],
            previous_output=last_spoken
        )

        text = output.spoken_text

        # ?? KEY: avoid annoying repetition
        if text != last_spoken:
            print("\n>>> VOICE <<<")
            print(text)

            engine.say(text)
            engine.runAndWait()

            last_spoken = text

        # ?? Dynamic timing (VERY IMPORTANT FOR DEMO)
        dominant = max(data["flood"], data["rain"], data["earthquake"])

        if dominant < 25:
            time.sleep(4)
        elif dominant < 50:
            time.sleep(3)
        elif dominant < 85:
            time.sleep(2)
        else:
            time.sleep(1)

if __name__ == "__main__":
    print("?? Voice system started")
    run_voice()
