"""
Run this once locally to process all 2025 races and store the parquet files.
Commit the output in data/spark_output/historical/ to git so the data
ships with the deployment and is available without re-running.

Usage (from project root, venv active):
    python scripts/process_2025.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from spark_processing.batch_processor import process_historical_session

YEAR = 2025
TOTAL_ROUNDS = 24

failed = []

for round_num in range(1, TOTAL_ROUNDS + 1):
    out_path = f"data/spark_output/historical/{YEAR}_round{round_num}"
    if os.path.exists(out_path):
        print(f"[SKIP] {YEAR} R{round_num} — already processed")
        continue
    print(f"\n{'='*50}")
    print(f"Processing {YEAR} Round {round_num} ...")
    print(f"{'='*50}")
    try:
        df = process_historical_session(YEAR, round_num)
        if df.empty:
            print(f"[WARN] {YEAR} R{round_num} returned empty — skipping")
            failed.append(round_num)
        else:
            print(f"[OK]   {YEAR} R{round_num} — {len(df)} laps saved")
    except Exception as e:
        print(f"[FAIL] {YEAR} R{round_num} — {e}")
        failed.append(round_num)

print(f"\n{'='*50}")
print(f"Done. Failed rounds: {failed if failed else 'none'}")
