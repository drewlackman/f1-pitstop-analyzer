"""
Unit tests for src/analyze.py.
Shared fixtures (sample_csv, sample_df, flagged_df) are defined in conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# load_data
# ---------------------------------------------------------------------------

class TestLoadData:
    def test_loads_valid_csv(self, sample_df):
        assert len(sample_df) > 0
        assert "driver" in sample_df.columns
        assert "team" in sample_df.columns

    def test_raises_when_file_missing(self, tmp_path):
        from src.analyze import load_data

        with pytest.raises(FileNotFoundError):
            load_data(tmp_path / "does_not_exist.csv")

    def test_raises_on_missing_columns(self, tmp_path):
        from src.analyze import load_data

        bad = pd.DataFrame({"lap_number": [1], "driver_number": [44]})
        csv = tmp_path / "bad.csv"
        bad.to_csv(csv, index=False)
        with pytest.raises(ValueError, match="Missing required columns"):
            load_data(csv)

    def test_drops_null_durations(self, tmp_path):
        from src.analyze import load_data
        from tests.conftest import SAMPLE_ROWS

        rows = dict(SAMPLE_ROWS)
        rows["pit_duration"] = list(rows["pit_duration"])
        rows["pit_duration"][0] = None
        pd.DataFrame(rows).to_csv(tmp_path / "pit.csv", index=False)

        df = load_data(tmp_path / "pit.csv")
        assert df["pit_duration"].isna().sum() == 0

    def test_drops_zero_and_negative_durations(self, tmp_path):
        from src.analyze import load_data
        from tests.conftest import SAMPLE_ROWS

        rows = dict(SAMPLE_ROWS)
        rows["pit_duration"] = [0, -5, 24.5, 25.0, 23.8, 26.0]
        pd.DataFrame(rows).to_csv(tmp_path / "pit.csv", index=False)

        df = load_data(tmp_path / "pit.csv")
        assert (df["pit_duration"] > 0).all()

    def test_unknown_driver_gets_fallback_label(self, tmp_path):
        from src.analyze import load_data
        from tests.conftest import SAMPLE_ROWS

        rows = dict(SAMPLE_ROWS)
        rows["driver_number"] = [999, 999, 16, 16, 1, 55]
        pd.DataFrame(rows).to_csv(tmp_path / "pit.csv", index=False)

        df = load_data(tmp_path / "pit.csv")
        unknown = df[df["driver_number"] == 999]
        assert (unknown["driver"] == "#999").all()
        assert (unknown["team"] == "Unknown").all()


# ---------------------------------------------------------------------------
# flag_outliers
# ---------------------------------------------------------------------------

class TestFlagOutliers:
    def test_adds_is_outlier_column(self, flagged_df):
        assert "is_outlier" in flagged_df.columns
        assert flagged_df["is_outlier"].dtype == bool

    def test_detects_obvious_outlier(self, flagged_df):
        # The 74.7 s stop is clearly an outlier vs 23-26 s normal stops
        outlier_rows = flagged_df[flagged_df["is_outlier"]]
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
    def test_returns_expected_keys(self, flagged_df):
        from src.analyze import race_summary

        summary = race_summary(flagged_df)
        for key in ("count", "outliers", "min", "max", "mean", "median", "std", "p25", "p75"):
            assert key in summary, f"Missing key: {key}"

    def test_min_lte_median_lte_max(self, flagged_df):
        from src.analyze import race_summary

        s = race_summary(flagged_df)
        assert s["min"] <= s["median"] <= s["max"]

    def test_outlier_count_positive(self, flagged_df):
        from src.analyze import race_summary

        s = race_summary(flagged_df)
        assert s["outliers"] >= 1  # the 74.7 s stop


# ---------------------------------------------------------------------------
# driver_stats
# ---------------------------------------------------------------------------

class TestDriverStats:
    def test_contains_all_expected_columns(self, flagged_df):
        from src.analyze import driver_stats

        stats = driver_stats(flagged_df)
        for col in ("driver", "team", "stops", "best", "worst", "mean", "median", "std"):
            assert col in stats.columns

    def test_sorted_by_median(self, flagged_df):
        from src.analyze import driver_stats

        stats = driver_stats(flagged_df)
        medians = stats["median"].tolist()
        assert medians == sorted(medians)

    def test_stop_counts_sum_to_total(self, flagged_df):
        from src.analyze import driver_stats

        stats = driver_stats(flagged_df)
        assert stats["stops"].sum() == len(flagged_df)


# ---------------------------------------------------------------------------
# team_stats
# ---------------------------------------------------------------------------

class TestTeamStats:
    def test_contains_required_columns(self, flagged_df):
        from src.analyze import team_stats

        stats = team_stats(flagged_df)
        for col in ("team", "stops", "best", "mean", "median", "std"):
            assert col in stats.columns

    def test_sorted_by_median(self, flagged_df):
        from src.analyze import team_stats

        stats = team_stats(flagged_df)
        medians = stats["median"].tolist()
        assert medians == sorted(medians)


# ---------------------------------------------------------------------------
# --format flag (export stats)
# ---------------------------------------------------------------------------

class TestFormatFlag:
    def _run_main(self, sample_csv, tmp_path, fmt):
        import argparse
        from src.analyze import main

        args = argparse.Namespace(
            csv=str(sample_csv),
            out_dir=str(tmp_path),
            no_plot=True,
            verbose=False,
            format=fmt,
        )
        main(args)

    def test_csv_export_creates_files(self, sample_csv, tmp_path):
        self._run_main(sample_csv, tmp_path, "csv")
        stem = sample_csv.stem
        assert (tmp_path / f"{stem}_drivers.csv").exists()
        assert (tmp_path / f"{stem}_teams.csv").exists()

    def test_json_export_creates_files(self, sample_csv, tmp_path):
        self._run_main(sample_csv, tmp_path, "json")
        stem = sample_csv.stem
        assert (tmp_path / f"{stem}_drivers.json").exists()
        assert (tmp_path / f"{stem}_teams.json").exists()

    def test_json_export_is_valid_json(self, sample_csv, tmp_path):
        import json

        self._run_main(sample_csv, tmp_path, "json")
        stem = sample_csv.stem
        data = json.loads((tmp_path / f"{stem}_drivers.json").read_text())
        assert isinstance(data, list)
        assert len(data) > 0
