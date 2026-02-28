"""
Download F1 pit stop data from the OpenF1 API and save as CSV.

Usage:
    python src/download_pitstops_openf1.py
    python src/download_pitstops_openf1.py --year 2024 --country Bahrain
    python src/download_pitstops_openf1.py --year 2023 --country Italy --session Race
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests

BASE = "https://api.openf1.org/v1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def get_session_key(year: int, country_name: str, session_name: str = "Race") -> int:
    """
    Find the OpenF1 session_key for a given year/country/session_name.

    Args:
        year: F1 season year (e.g. 2024).
        country_name: Country of the race (e.g. "Bahrain", "Italy").
        session_name: Session type ("Race", "Qualifying", "Sprint", etc.).

    Returns:
        Integer session key used by OpenF1 endpoints.

    Raises:
        ValueError: If no matching session is found.
        requests.HTTPError: If the API request fails.
    """
    url = f"{BASE}/sessions"
    params: dict[str, Any] = {
        "year": year,
        "country_name": country_name,
        "session_name": session_name,
    }
    log.info("Querying session key: year=%s, country=%s, session=%s", year, country_name, session_name)
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data: list[dict[str, Any]] = r.json()

    if not data:
        raise ValueError(
            f"No sessions found for year={year}, country_name={country_name}, session_name={session_name}"
        )

    # Pick the latest entry by date_start if multiple results are returned
    data_sorted = sorted(data, key=lambda x: x.get("date_start", ""))
    session_key = int(data_sorted[-1]["session_key"])
    log.info("Resolved session_key=%s", session_key)
    return session_key


def download_pit_csv(session_key: int, out_csv: Path) -> pd.DataFrame:
    """
    Download pit-lane events for a session and write them to CSV.

    Args:
        session_key: OpenF1 session identifier.
        out_csv: Destination path for the CSV file.

    Returns:
        DataFrame of the downloaded pit-stop records.

    Raises:
        requests.HTTPError: If the API request fails.
    """
    url = f"{BASE}/pit"
    params: dict[str, Any] = {"session_key": session_key, "csv": "true"}
    log.info("Downloading pit stop data for session_key=%s …", session_key)
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_csv.write_bytes(r.content)
    log.info("Saved raw CSV → %s", out_csv)

    df = pd.read_csv(out_csv)
    log.info("Downloaded %d pit stops with columns: %s", len(df), list(df.columns))
    return df


def main(args: argparse.Namespace | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Download F1 pit stop data from OpenF1 API.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--year", type=int, default=2024, help="F1 season year")
    parser.add_argument("--country", dest="country_name", default="Bahrain", help="Race country name")
    parser.add_argument("--session", dest="session_name", default="Race", help="Session type")
    parser.add_argument("--out-dir", default="data", help="Output directory for CSV files")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    if args is None:
        args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    session_key = get_session_key(args.year, args.country_name, args.session_name)

    slug = args.country_name.lower().replace(" ", "_")
    out_csv = Path(args.out_dir) / f"pit_{args.year}_{slug}.csv"

    df = download_pit_csv(session_key, out_csv)

    print(f"\nSaved: {out_csv}")
    print(f"Rows:  {len(df)}")
    print(f"Cols:  {list(df.columns)}")

    if "pit_duration" in df.columns:
        print(f"\nPit duration summary (seconds):")
        print(df["pit_duration"].describe().to_string())


if __name__ == "__main__":
    main()
