"""
Unit tests for src/analyze.py.
"""

from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(**overrides) -> pd.DataFrame:
    """Return a minimal valid pit-stop DataFrame for testing."""
    base = {
        "pit_duration": [24.5, 25.1, 23.8, 26.0, 74.7, 24.9],
        "lap_number":   [10,   15,   20,   25,   1,    30  ],
        "driver_number":[44,   44,   16,   16,   1,    55  ],
        "meeting_key":  [1229] * 6,
        "session_key":  [9472] * 6,
    }
    base.update(overrides)
    return pd.DataFrame(base)


# ---------------------------------------------------------------------------
# load_data
# ---------------------------------------------------------------------------

class TestLoadData:
    def test_loads_valid_csv(self, tmp_path: Path):
        from src.analyze import load_data

        df_raw = _make_df()
        csv = tmp_path / "pit.csv"
        df_raw.to_csv(csv, index=False)

        df = load_data(csv)
        # Non-zero, non-null rows kept; driver/team columns added
        assert len(df) > 0
        assert "driver" in df.columns
        assert "team" in df.columns

    def test_raises_when_file_missing(self, tmp_path: Path):
        from src.analyze import load_data

        with pytest.raises(FileNotFoundError):
            load_data(tmp_path / "does_not_exist.csv")

    def test_raises_on_missing_columns(self, tmp_path: Path):
        from src.analyze import load_data

        bad = pd.DataFrame({"lap_number": [1], "driver_number": [44]})
        csv = tmp_path / "bad.csv"
        bad.to_csv(csv, index=False)
        with pytest.raises(ValueError, match="Missing required columns"):
            load_data(csv)

    def test_drops_null_durations(self, tmp_path: Path):
        from src.analyze import load_data

        df_raw = _make_df()
        df_raw.loc[0, "pit_duration"] = None  # inject null
        csv = tmp_path / "pit.csv"
        df_raw.to_csv(csv, index=False)

        df = load_data(csv)
        assert df["pit_duration"].isna().sum() == 0

    def test_drops_zero_and_negative_durations(self, tmp_path: Path):
        from src.analyze import load_data

        df_raw = _make_df(pit_duration=[0, -5, 24.5, 25.0, 23.8, 26.0])
        csv = tmp_path / "pit.csv"
        df_raw.to_csv(csv, index=False)

        df = load_data(csv)
        assert (df["pit_duration"] > 0).all()

    def test_unknown_driver_gets_fallback_label(self, tmp_path: Path):
        from src.analyze import load_data

        df_raw = _make_df(driver_number=[999, 999, 16, 16, 1, 55])
        csv = tmp_path / "pit.csv"
        df_raw.to_csv(csv, index=False)

        df = load_data(csv)
        unknown_rows = df[df["driver_number"] == 999]
        assert (unknown_rows["driver"] == "#999").all()
        assert (unknown_rows["team"] == "Unknown").all()


# ---------------------------------------------------------------------------
# flag_outliers
# ---------------------------------------------------------------------------

class TestFlagOutliers:
    def _base(self) -> pd.DataFrame:
        from src.analyze import load_data
        import tempfile, os

        df_raw = _make_df()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            df_raw.to_csv(f, index=False)
            name = f.name
        df = load_data(Path(name))
        os.unlink(name)
        return df

    def test_adds_is_outlier_column(self):
        from src.analyze import flag_outliers

        df = self._base()
        df = flag_outliers(df)
        assert "is_outlier" in df.columns
        assert df["is_outlier"].dtype == bool

    def test_detects_obvious_outlier(self):
        from src.analyze import flag_outliers

        df = self._base()
        # The 74.7s stop is clearly an outlier vs 23-26s normal stops
        df = flag_outliers(df)
        outlier_rows = df[df["is_outlier"]]
        assert not outlier_rows.empty
        assert outlier_rows["pit_duration"].max() > 50

    def test_no_outliers_in_uniform_data(self):
        from src.analyze import flag_outliers

        df = pd.DataFrame({
            "pit_duration": [24.0, 24.1, 24.2, 24.3, 24.4],
            "lap_number":   [10, 15, 20, 25, 30],
            "driver_number":[44, 44, 16, 16, 55],
            "driver": ["HAM", "HAM", "LEC", "LEC", "SAI"],
            "team":   ["Mercedes"] * 3 + ["Ferrari"] * 2,
        })
        df = flag_outliers(df)
        assert df["is_outlier"].sum() == 0


# ---------------------------------------------------------------------------
# race_summary
# ---------------------------------------------------------------------------

class TestRaceSummary:
    def _flagged(self) -> pd.DataFrame:
        from src.analyze import load_data, flag_outliers
        import tempfile, os

        df_raw = _make_df()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            df_raw.to_csv(f, index=False)
            name = f.name
        df = flag_outliers(load_data(Path(name)))
        os.unlink(name)
        return df

    def test_returns_expected_keys(self):
        from src.analyze import race_summary

        summary = race_summary(self._flagged())
        for key in ("count", "outliers", "min", "max", "mean", "median", "std", "p25", "p75"):
            assert key in summary, f"Missing key: {key}"

    def test_min_lte_median_lte_max(self):
        from src.analyze import race_summary

        s = race_summary(self._flagged())
        assert s["min"] <= s["median"] <= s["max"]

    def test_outlier_count_positive(self):
        from src.analyze import race_summary

        s = race_summary(self._flagged())
        assert s["outliers"] >= 1  # the 74.7 s stop


# ---------------------------------------------------------------------------
# driver_stats
# ---------------------------------------------------------------------------

class TestDriverStats:
    def _df(self) -> pd.DataFrame:
        from src.analyze import load_data, flag_outliers
        import tempfile, os

        df_raw = _make_df()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            df_raw.to_csv(f, index=False)
            name = f.name
        df = flag_outliers(load_data(Path(name)))
        os.unlink(name)
        return df

    def test_contains_all_expected_columns(self):
        from src.analyze import driver_stats

        stats = driver_stats(self._df())
        for col in ("driver", "team", "stops", "best", "worst", "mean", "median", "std"):
            assert col in stats.columns

    def test_sorted_by_median(self):
        from src.analyze import driver_stats

        stats = driver_stats(self._df())
        medians = stats["median"].tolist()
        assert medians == sorted(medians)

    def test_stop_counts_sum_to_total(self):
        from src.analyze import driver_stats

        df = self._df()
        stats = driver_stats(df)
        assert stats["stops"].sum() == len(df)


# ---------------------------------------------------------------------------
# team_stats
# ---------------------------------------------------------------------------

class TestTeamStats:
    def _df(self) -> pd.DataFrame:
        from src.analyze import load_data, flag_outliers
        import tempfile, os

        df_raw = _make_df()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            df_raw.to_csv(f, index=False)
            name = f.name
        df = flag_outliers(load_data(Path(name)))
        os.unlink(name)
        return df

    def test_contains_required_columns(self):
        from src.analyze import team_stats

        stats = team_stats(self._df())
        for col in ("team", "stops", "best", "mean", "median", "std"):
            assert col in stats.columns

    def test_sorted_by_median(self):
        from src.analyze import team_stats

        stats = team_stats(self._df())
        medians = stats["median"].tolist()
        assert medians == sorted(medians)
