import json
import requests

BASE_URL = "http://127.0.0.1:49099/values"
TIMEOUT = 5

URLS = [
    f"{BASE_URL}/mapper.heater_mappings_bftc.device.c1/temperature",
    f"{BASE_URL}/mapper.heater_mappings_bftc.device.c2/temperature",
    f"{BASE_URL}/mapper.heater_mappings_bftc.device.c5/temperature",
    f"{BASE_URL}/mapper.heater_mappings_bftc.device.c6/temperature",
    f"{BASE_URL}/driver.bftc.data.heaters.heater_1/active",
]

for url in URLS:
    print("\n" + "=" * 80)
    print("TESTING URL:")
    print(url)

    try:
        r = requests.get(url, timeout=TIMEOUT)
        print("STATUS CODE:", r.status_code)
        print("RAW TEXT:")
        print(r.text[:2000])

        try:
            data = r.json()
            print("TOP-LEVEL JSON KEYS:", list(data.keys()))
            if "data" in data:
                print("DATA KEYS:", list(data["data"].keys()))
        except Exception as je:
            print("JSON PARSE FAILED:", je)

    except Exception as e:
        print("REQUEST FAILED:", repr(e))
