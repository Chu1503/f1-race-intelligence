"""
Run this to find which 2025 sessions have actual lap data.
"""
import httpx
import time

print("Fetching 2025 race sessions...")
r = httpx.get(
    "https://api.openf1.org/v1/sessions",
    params={"session_type": "Race", "year": "2025"},
    timeout=15
)
sessions = r.json()
print(f"Found {len(sessions)} race sessions in 2025\n")

for s in sessions[-5:]:
    key = s["session_key"]
    country = s["country_name"]
    date = s["date_start"][:10]
    print(f"key={key} | {country} | {date}")
    time.sleep(1.2)
    r2 = httpx.get(
        "https://api.openf1.org/v1/laps",
        params={"session_key": key, "lap_number": 1},
        timeout=10
    )
    count = len(r2.json()) if r2.status_code == 200 else 0
    has = "USE THIS" if count > 0 else "no data"
    print(f"  -> laps status={r2.status_code}, records={count}  [{has}]\n")