import csv
import json
import os
import time
from datetime import datetime

import requests


# =========================
# USER SETTINGS
# =========================

BASE_URL = "http://127.0.0.1:49099/values"
TEMP_CHANNELS = [1, 2, 5, 6]

HEATER_PATH = "mapper.bflegacy.boolean.heater"

LOG_DIR = r"C:\Users\quantumuser\bluefors-temp-control\logs"
TIMEOUT = 5


# =========================
# UTILITY FUNCTIONS
# =========================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_file():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def write_log(log_path, message):
    line = f"[{now()}] {message}"
    print(line)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def post_json(url, body):
    response = requests.post(
        url,
        data=json.dumps(body),
        headers={"Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json() if response.text.strip() else None


def get_value_node(path):
    url = f"{BASE_URL}/{path}"
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    data = response.json()
    return data["data"][path]["content"]


def extract_value(content):
    if "latest_valid_value" in content and content["latest_valid_value"] is not None:
        return content["latest_valid_value"]["value"]
    return content["latest_value"]["value"]


def get_temp(channel):
    path = f"mapper.heater_mappings_bftc.device.c{channel}.temperature"
    content = get_value_node(path)
    return float(extract_value(content))


def heater_is_on(value):
    v = str(value).strip().lower()
    return v in {"1", "true", "on"}


def get_heater_state():
    content = get_value_node(HEATER_PATH)
    return extract_value(content)


def set_heater_state(log_path, on):
    value = "1" if on else "0"
    action = "ON" if on else "OFF"
    write_log(log_path, f"Sending heater {action} command to {HEATER_PATH}")

    body = {
        "data": {
            HEATER_PATH: {
                "content": {
                    "value": value
                }
            }
        }
    }

    post_json(BASE_URL + "/", body)


def heater_off(log_path):
    set_heater_state(log_path, on=False)


# =========================
# MAIN
# =========================

def main():
    ensure_log_dir()

    stamp = now_file()
    csv_path = os.path.join(LOG_DIR, f"shutdown_{stamp}.csv")
    txt_path = os.path.join(LOG_DIR, f"shutdown_{stamp}.txt")

    write_log(txt_path, "Shutdown script started")

    row = {
        "timestamp": now(),
        "heater_before": "",
        "heater_after": "",
        "result": "",
    }

    # =========================
    # READ TEMPERATURES
    # =========================

    for ch in TEMP_CHANNELS:
        try:
            t = get_temp(ch)
            row[f"C{ch}_K"] = t
            write_log(txt_path, f"C{ch} temperature = {t}")
        except Exception as e:
            row[f"C{ch}_K"] = ""
            write_log(txt_path, f"Failed to read C{ch}: {e}")

    # =========================
    # READ HEATER STATE
    # =========================

    try:
        state = get_heater_state()
        row["heater_before"] = state
        write_log(txt_path, f"Heater state before = {state}")
    except Exception as e:
        write_log(txt_path, f"Failed to read heater: {e}")
        return

    # =========================
    # TURN HEATER OFF IF NEEDED
    # =========================

    if heater_is_on(state):
        write_log(txt_path, "Heater is ON")

        try:
            heater_off(txt_path)
            time.sleep(2)

            state2 = get_heater_state()
            row["heater_after"] = state2

            if heater_is_on(state2):
                row["result"] = "OFF command sent, but heater still appears ON"
            else:
                row["result"] = "Turned OFF"

            write_log(txt_path, f"Heater after command = {state2}")

        except Exception as e:
            row["result"] = "FAILED"
            write_log(txt_path, f"Heater OFF failed: {e}")

    else:
        row["heater_after"] = state
        row["result"] = "Already OFF"
        write_log(txt_path, "Heater already OFF")

    # =========================
    # SAVE CSV
    # =========================

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=row.keys())
        writer.writeheader()
        writer.writerow(row)

    write_log(txt_path, "CSV saved")
    write_log(txt_path, "Shutdown script finished")


if __name__ == "__main__":
    main()
