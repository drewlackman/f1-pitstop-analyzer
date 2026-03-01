"""
Shared pytest fixtures for the F1 pitstop analyzer test suite.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Raw sample data used across multiple test modules
# ---------------------------------------------------------------------------

SAMPLE_ROWS = {
    "pit_duration": [24.5, 25.1, 23.8, 26.0, 74.7, 24.9],
    "lap_number":   [10,   15,   20,   25,   1,    30],
    "driver_number":[44,   44,   16,   16,   1,    55],
    "meeting_key":  [1229, 1229, 1229, 1229, 1229, 1229],
    "session_key":  [9472, 9472, 9472, 9472, 9472, 9472],
}


@pytest.fixture()
def sample_csv(tmp_path: Path) -> Path:
    """Write SAMPLE_ROWS to a temp CSV and return its path."""
    csv = tmp_path / "pit_2024_bahrain.csv"
    pd.DataFrame(SAMPLE_ROWS).to_csv(csv, index=False)
    return csv


@pytest.fixture()
def sample_df(sample_csv: Path) -> pd.DataFrame:
    """Return a loaded (driver/team columns added) DataFrame."""
    from src.analyze import load_data
    return load_data(sample_csv)


@pytest.fixture()
def flagged_df(sample_df: pd.DataFrame) -> pd.DataFrame:
    """Return sample_df with outlier flags applied."""
    from src.analyze import flag_outliers
    return flag_outliers(sample_df)


@pytest.fixture()
def multi_race_csvs(tmp_path: Path) -> list[Path]:
    """Create two race CSV files for multi-race comparison tests."""
    races = {
        "pit_2024_bahrain.csv": {
            "pit_duration": [24.5, 25.1, 23.8, 26.0, 24.9, 25.5],
            "lap_number":   [10, 15, 20, 25, 30, 35],
            "driver_number":[44, 44, 16, 16, 55, 55],
            "meeting_key":  [1229] * 6,
            "session_key":  [9472] * 6,
        },
        "pit_2024_saudi_arabia.csv": {
            "pit_duration": [23.0, 23.5, 24.1, 22.9, 23.8, 24.5],
            "lap_number":   [12, 18, 22, 28, 33, 38],
            "driver_number":[44, 44, 16, 16, 55, 55],
            "meeting_key":  [1230] * 6,
            "session_key":  [9480] * 6,
        },
    }
    paths = []
    for name, data in races.items():
        p = tmp_path / name
        pd.DataFrame(data).to_csv(p, index=False)
        paths.append(p)
    return paths
