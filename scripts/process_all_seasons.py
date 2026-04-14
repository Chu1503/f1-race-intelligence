"""
    python scripts/process_all_seasons.py --years 2023            # add 2023
    python scripts/process_all_seasons.py --years 2023 2024 2025  # all three
    python scripts/process_all_seasons.py --years 2025 --force    # reprocess 2025
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import time
import requests
from loguru import logger
from logger_config import setup_logging

setup_logging()

JOLPICA_BASE = "https://api.jolpi.ca/ergast/f1"


def get_completed_rounds(year: int) -> list[tuple[int, str]]:
    """
    Fetch all completed rounds for a year.
    """
    try:
        r = requests.get(
            f"{JOLPICA_BASE}/{year}/results.json?limit=1000", timeout=15
        )
        races = r.json()["MRData"]["RaceTable"]["Races"]
        result = []
        for race in races:
            rnum = int(race["round"])
            name = race["raceName"].replace(" Grand Prix", " GP")
            result.append((rnum, name))
        logger.info(f"{year}: found {len(result)} completed rounds")
        return result
    except Exception as e:
        logger.error(f"Could not fetch completed rounds for {year}: {e}")
        return []


def already_processed(year: int, round_number: int) -> bool:
    path = f"data/spark_output/historical/{year}_round{round_number}"
    return os.path.exists(path) and len(os.listdir(path)) > 0


def draw_progress(current: int, total: int, label: str, width: int = 40) -> None:
    filled = int(width * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * current / total) if total > 0 else 0
    print(f"\r  [{bar}] {pct:3d}%  {current}/{total}  {label:<40}", end="", flush=True)


def process_round(year: int, round_number: int, race_name: str, force: bool = False) -> bool:
    try:
        from spark_processing.batch_processor import process_historical_session
        df = process_historical_session(year=year, round_number=round_number)
        if df is not None and len(df) > 0:
            return True
        else:
            logger.warning(f"\n  EMPTY {year} R{round_number} {race_name} — no laps returned")
            return False
    except Exception as e:
        logger.error(f"\n  FAILED {year} R{round_number} {race_name}: {e}")
        return False


def format_race_label(year: int, round_number: int, race_name: str) -> str:
    return f"{year} R{round_number}: {race_name}"


def main():
    parser = argparse.ArgumentParser(description="Bulk process F1 race seasons")
    parser.add_argument(
        "--years", nargs="+", type=int, default=[2024, 2025],
        help="Years to process (default: 2024 2025). Add 2023 with --years 2023 2024 2025"
    )
    parser.add_argument(
        "--rounds", nargs="+", type=int, default=None,
        help="Specific round numbers to process (default: all completed rounds)"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-process even if data already exists"
    )
    parser.add_argument(
        "--delay", type=float, default=3.0,
        help="Seconds to wait between rounds (default: 3)"
    )
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print(f"  F1 Race Intelligence — Bulk Data Processor")
    print(f"  Seasons: {args.years}")
    print("=" * 60)

    all_work: list[tuple[int, int, str, bool]] = []  # (year, round, name, skip)
    for year in args.years:
        rounds_info = get_completed_rounds(year)
        if args.rounds:
            rounds_info = [(r, n) for r, n in rounds_info if r in args.rounds]
        for rnum, rname in sorted(rounds_info):
            skip = not args.force and already_processed(year, rnum)
            all_work.append((year, rnum, rname, skip))

    to_process = [(y, r, n) for y, r, n, skip in all_work if not skip]
    to_skip    = [(y, r, n) for y, r, n, skip in all_work if skip]

    print(f"\n  Total rounds found:     {len(all_work)}")
    print(f"  Already processed:      {len(to_skip)} (will skip)")
    print(f"  To process now:         {len(to_process)}")

    if to_skip:
        print(f"\n  Skipping already processed:")
        for y, r, n in to_skip:
            print(f"    ✓ {format_race_label(y, r, n)}")

    if not to_process:
        print("\n  Nothing to process: all rounds already exist.")
        print("  Use --force to reprocess existing data.")
        print("=" * 60 + "\n")
        return True

    print(f"\n  Starting processing ({len(to_process)} rounds)...\n")

    succeeded = 0
    failed = 0
    failed_list: list[str] = []

    for i, (year, round_num, race_name) in enumerate(to_process):
        label = format_race_label(year, round_num, race_name)
        draw_progress(i, len(to_process), f"Processing: {label}")

        start = time.time()
        ok = process_round(year, round_num, race_name, force=args.force)
        elapsed = time.time() - start

        if ok:
            succeeded += 1
            draw_progress(i + 1, len(to_process), f"✓ {label} ({elapsed:.0f}s)")
            print()
        else:
            failed += 1
            failed_list.append(label)
            draw_progress(i + 1, len(to_process), f"✗ FAILED: {label}")
            print()

        if i < len(to_process) - 1:
            time.sleep(args.delay)

    print("\n" + "=" * 60)
    print(f"  COMPLETE")
    print(f"  ✓ Succeeded: {succeeded}")
    print(f"  ✗ Failed:    {failed}")
    print(f"  ↷ Skipped:   {len(to_skip)}")

    if failed_list:
        print(f"\n  Failed rounds (rerun script to retry):")
        for label in failed_list:
            print(f"    ✗ {label}")

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)