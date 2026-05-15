import json
import os
import time
from datetime import datetime

import requests


# =========================
# USER SETTINGS
# =========================

BASE_URL = "http://127.0.0.1:49099/values"

C1_TEMP_PATH = "mapper.heater_mappings_bftc.device.c1.temperature"
HEATER_PATH = "mapper.bflegacy.boolean.heater"

LOG_DIR = r"C:\Users\quantumuser\bluefors-temp-control\logs"

TEMP_LIMIT_K = 300.0

CHECK_INTERVAL_S = 10
READ_TIMEOUT_S = 5

API_STARTUP_GRACE_S = 120
REQUIRED_GOOD_READS = 2


# =========================
# UTILITY FUNCTIONS
# =========================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def today_file():
    return datetime.now().strftime("%Y%m%d")


def ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def get_log_path():
    return os.path.join(LOG_DIR, f"heater_safety_monitor_{today_file()}.txt")


def write_log(message):
    log_path = get_log_path()
    line = f"[{now()}] {message}"
    print(line)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_value_node(path):
    url = f"{BASE_URL}/{path}"

    response = requests.get(url, timeout=READ_TIMEOUT_S)
    response.raise_for_status()

    data = response.json()

    if "data" not in data:
        raise RuntimeError(f"No 'data' field returned for {path}")

    if path not in data["data"]:
        raise RuntimeError(f"Path {path} not found in API response")

    return data["data"][path]["content"]


def extract_value(content):
    if "latest_valid_value" in content and content["latest_valid_value"] is not None:
        return content["latest_valid_value"]["value"]

    if "latest_value" in content and content["latest_value"] is not None:
        return content["latest_value"]["value"]

    raise RuntimeError("No valid value found in content")


def post_json(url, body):
    response = requests.post(
        url,
        data=json.dumps(body),
        headers={"Content-Type": "application/json"},
        timeout=READ_TIMEOUT_S,
    )

    response.raise_for_status()

    if response.text.strip():
        return response.json()

    return None


def get_c1_temp():
    content = get_value_node(C1_TEMP_PATH)
    return float(extract_value(content))


def get_heater_state():
    content = get_value_node(HEATER_PATH)
    return extract_value(content)


def heater_is_on(value):
    v = str(value).strip().lower()
    return v in {"1", "true", "on"}


def set_heater_off():
    write_log(f"Sending 4K heater OFF command to {HEATER_PATH}")

    body = {
        "data": {
            HEATER_PATH: {
                "content": {
                    "value": "0"
                }
            }
        }
    }

    post_json(BASE_URL + "/", body)


# =========================
# API STARTUP WAIT
# =========================

def wait_for_api_ready():
    write_log("Waiting for Bluefors API to become ready...")

    start = time.time()

    while True:
        try:
            c1_temp = get_c1_temp()
            heater_state = get_heater_state()

            write_log(f"API ready. C1 = {c1_temp:.3f} K, heater = {heater_state}")
            return

        except Exception as e:
            elapsed = time.time() - start

            if elapsed < API_STARTUP_GRACE_S:
                write_log(f"API not ready yet after {elapsed:.0f}s: {repr(e)}")
            else:
                write_log(
                    f"API still not ready after {elapsed:.0f}s. "
                    "Continuing to retry in background."
                )

            time.sleep(CHECK_INTERVAL_S)


# =========================
# MAIN MONITOR LOOP
# =========================

def main():
    ensure_log_dir()

    write_log("=" * 80)
    write_log("4K heater safety monitor started")
    write_log(f"C1 temperature limit = {TEMP_LIMIT_K} K")
    write_log(f"Check interval = {CHECK_INTERVAL_S} seconds")
    write_log(f"Required good reads before action = {REQUIRED_GOOD_READS}")

    wait_for_api_ready()

    good_reads = 0

    while True:
        try:
            c1_temp = get_c1_temp()
            heater_state = get_heater_state()

            good_reads += 1

            write_log(
                f"C1 = {c1_temp:.3f} K, "
                f"heater = {heater_state}, "
                f"good_reads = {good_reads}"
            )

            if good_reads < REQUIRED_GOOD_READS:
                write_log("Waiting for another valid read before taking action.")
                time.sleep(CHECK_INTERVAL_S)
                continue

            if c1_temp > TEMP_LIMIT_K:
                write_log(
                    f"WARNING: C1 temperature above limit: "
                    f"{c1_temp:.3f} K > {TEMP_LIMIT_K:.3f} K"
                )

                if heater_is_on(heater_state):
                    write_log("4K heater is ON while C1 is above limit. Turning heater OFF.")

                    set_heater_off()

                    time.sleep(2)

                    new_state = get_heater_state()
                    write_log(f"Heater state after OFF command = {new_state}")

                    if heater_is_on(new_state):
                        write_log("ERROR: Heater still appears ON after OFF command")
                    else:
                        write_log("SUCCESS: 4K heater is OFF")

                else:
                    write_log("C1 above limit, but 4K heater is already OFF. No action needed.")

        except Exception as e:
            good_reads = 0
            write_log(f"Read/check failed. Resetting good-read counter: {repr(e)}")

        time.sleep(CHECK_INTERVAL_S)


if __name__ == "__main__":
    main()
