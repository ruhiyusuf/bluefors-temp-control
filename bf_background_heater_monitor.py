import json
import os
import time
from datetime import datetime

import requests


# ============================================================
# USER SETTINGS
# ============================================================

BASE_URL = "http://127.0.0.1:49099/values"

C1_TEMP_PATH = "mapper.heater_mappings_bftc.device.c1.temperature"
HEATER_PATH = "mapper.bflegacy.boolean.heater"

# Temperature threshold
TEMP_LIMIT_K = 300.0

# Timing
CHECK_INTERVAL_S = 10
REQUEST_TIMEOUT_S = 5
API_STARTUP_GRACE_S = 120

# Event logging
LOG_DIR = r"C:\Users\quantumuser\bluefors-temp-control"
EVENT_LOG_FILE = os.path.join(LOG_DIR, "events.txt")


# ============================================================
# UTILITIES
# ============================================================

def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_log_dir():
    os.makedirs(LOG_DIR, exist_ok=True)


def log_event(message):
    line = f"[{now()}] {message}"

    print(line)

    with open(EVENT_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_value_node(path):
    url = f"{BASE_URL}/{path}"

    response = requests.get(
        url,
        timeout=REQUEST_TIMEOUT_S,
    )

    response.raise_for_status()

    data = response.json()

    if "data" not in data:
        raise RuntimeError(f"No 'data' field returned for path: {path}")

    if path not in data["data"]:
        raise RuntimeError(f"Path not found in response: {path}")

    return data["data"][path]["content"]


def extract_value(content):
    if (
        "latest_valid_value" in content
        and content["latest_valid_value"] is not None
    ):
        return content["latest_valid_value"]["value"]

    if (
        "latest_value" in content
        and content["latest_value"] is not None
    ):
        return content["latest_value"]["value"]

    raise RuntimeError("No valid value found")


def post_json(url, body):
    response = requests.post(
        url,
        data=json.dumps(body),
        headers={"Content-Type": "application/json"},
        timeout=REQUEST_TIMEOUT_S,
    )

    response.raise_for_status()

    if response.text.strip():
        return response.json()

    return None


# ============================================================
# BLUEFORS READS
# ============================================================

def get_c1_temp():
    content = get_value_node(C1_TEMP_PATH)
    return float(extract_value(content))


def get_heater_state():
    content = get_value_node(HEATER_PATH)
    return extract_value(content)


def heater_is_on(value):
    v = str(value).strip().lower()

    return v in {
        "1",
        "true",
        "on",
    }


# ============================================================
# HEATER CONTROL
# ============================================================

def set_heater_off():
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


# ============================================================
# WAIT FOR API
# ============================================================

def wait_for_api_ready():
    start_time = time.time()

    while True:
        try:
            c1_temp = get_c1_temp()
            heater_state = get_heater_state()

            log_event(
                f"Bluefors API ready | "
                f"C1 = {c1_temp:.3f} K | "
                f"Heater = {heater_state}"
            )

            return

        except Exception as e:
            elapsed = time.time() - start_time

            if elapsed < API_STARTUP_GRACE_S:
                print(
                    f"[{now()}] Waiting for API... "
                    f"({elapsed:.0f}s) | {repr(e)}"
                )
            else:
                print(
                    f"[{now()}] API still unavailable after "
                    f"{elapsed:.0f}s | {repr(e)}"
                )

            time.sleep(CHECK_INTERVAL_S)


# ============================================================
# MAIN LOOP
# ============================================================

def main():
    ensure_log_dir()

    log_event("=" * 70)
    log_event("Bluefors heater safety monitor started")
    log_event(f"C1 temperature limit = {TEMP_LIMIT_K:.3f} K")

    wait_for_api_ready()

    while True:
        try:
            c1_temp = get_c1_temp()
            heater_state = get_heater_state()

            # ------------------------------------------------
            # TEMP ABOVE LIMIT
            # ------------------------------------------------

            if c1_temp > TEMP_LIMIT_K:

                log_event(
                    f"TEMP LIMIT EXCEEDED | "
                    f"C1 = {c1_temp:.3f} K | "
                    f"Limit = {TEMP_LIMIT_K:.3f} K"
                )

                if heater_is_on(heater_state):

                    log_event(
                        "4K heater is ON while temperature "
                        "is above limit. Turning heater OFF."
                    )

                    set_heater_off()

                    time.sleep(2)

                    new_state = get_heater_state()

                    if heater_is_on(new_state):

                        log_event(
                            "ERROR: Heater still appears ON "
                            "after OFF command"
                        )

                    else:

                        log_event(
                            "SUCCESS: 4K heater turned OFF"
                        )

                else:

                    log_event(
                        "Temperature above limit, but "
                        "heater already OFF"
                    )

        except Exception as e:

            print(
                f"[{now()}] Read failed: {repr(e)}"
            )

        time.sleep(CHECK_INTERVAL_S)


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
