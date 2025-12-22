from __future__ import annotations

import os
from typing import Any, Dict, List
import requests
import pandas as pd

BASE = "https://api.openf1.org/v1"


def get_session_key(year: int, country_name: str, session_name: str = "Race") -> int:
    """
    Find the OpenF1 session_key for a given year/country/session_name.
    """
    url = f"{BASE}/sessions"
    params = {"year": year, "country_name": country_name, "session_name": session_name}
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data: List[Dict[str, Any]] = r.json()

    if not data:
        raise ValueError(f"No sessions found for year={year}, country_name={country_name}, session_name={session_name}")

    # If multiple entries exist, pick the latest by date_start
    data_sorted = sorted(data, key=lambda x: x.get("date_start", ""))
    return int(data_sorted[-1]["session_key"])


def download_pit_csv(session_key: int, out_csv: str) -> None:
    """
    Download pit lane events for the session as CSV.
    OpenF1 supports CSV output using csv=true.  [oai_citation:1‡openf1.org](https://openf1.org/)
    """
    url = f"{BASE}/pit"
    params = {"session_key": session_key, "csv": "true"}  # CSV output supported by OpenF1
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, "wb") as f:
        f.write(r.content)


def main() -> None:
    year = 2024
    country_name = "Bahrain"   # change this to "Saudi Arabia", "Italy", etc.
    session_name = "Race"

    session_key = get_session_key(year, country_name, session_name=session_name)
    out_csv = f"data/pit_{year}_{country_name.lower().replace(' ', '_')}.csv"
    download_pit_csv(session_key, out_csv)

    # Quick sanity check (optional)
    df = pd.read_csv(out_csv)
    print("Saved:", out_csv)
    print("Rows:", len(df))
    print("Columns:", list(df.columns))


if __name__ == "__main__":
    main()