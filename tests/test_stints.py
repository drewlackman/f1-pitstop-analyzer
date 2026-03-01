"""
Unit tests for src/stints.py.
Uses the shared fixtures defined in conftest.py.
"""

from __future__ import annotations

import pytest
from pathlib import Path


class TestComputeStints:
    def test_returns_dataframe_with_required_columns(self, flagged_df):
        from src.stints import compute_stints

        stints = compute_stints(flagged_df, total_laps=57)
        for col in ("driver", "team", "stint", "start_lap", "end_lap", "length"):
            assert col in stints.columns

    def test_stint_numbers_are_sequential_per_driver(self, flagged_df):
        from src.stints import compute_stints

        stints = compute_stints(flagged_df, total_laps=57)
        for driver, grp in stints.groupby("driver"):
            numbers = grp.sort_values("stint")["stint"].tolist()
            assert numbers == list(range(1, len(numbers) + 1)), \
                f"{driver}: stint numbers not sequential: {numbers}"

    def test_stints_cover_full_race_distance(self, flagged_df):
        from src.stints import compute_stints

        total = 57
        stints = compute_stints(flagged_df, total_laps=total)
        for driver, grp in stints.groupby("driver"):
            total_laps_covered = grp["length"].sum()
            assert total_laps_covered == total, \
                f"{driver}: covered {total_laps_covered} of {total} laps"

    def test_start_and_end_laps_are_contiguous(self, flagged_df):
        from src.stints import compute_stints

        stints = compute_stints(flagged_df, total_laps=57)
        for driver, grp in stints.groupby("driver"):
            grp = grp.sort_values("stint")
            for i in range(len(grp) - 1):
                end = grp.iloc[i]["end_lap"]
                start_next = grp.iloc[i + 1]["start_lap"]
                assert start_next == end + 1, \
                    f"{driver}: gap between stint {i+1} and {i+2}"

    def test_length_equals_end_minus_start_plus_one(self, flagged_df):
        from src.stints import compute_stints

        stints = compute_stints(flagged_df, total_laps=57)
        for _, row in stints.iterrows():
            expected = row["end_lap"] - row["start_lap"] + 1
            assert row["length"] == expected

    def test_uses_max_pit_lap_as_fallback_when_total_laps_none(self, flagged_df):
        from src.stints import compute_stints

        # Should not raise, just warn
        stints = compute_stints(flagged_df, total_laps=None)
        assert len(stints) > 0

    def test_single_stop_driver_has_two_stints(self, sample_csv):
        """A driver with exactly one pit stop must have exactly two stints."""
        from src.analyze import flag_outliers, load_data
        from src.stints import compute_stints
        import pandas as pd

        df = flag_outliers(load_data(sample_csv))
        # driver 55 (SAI) has 1 stop in sample data
        df_sai = df[df["driver"] == "SAI"]
        if df_sai.empty:
            pytest.skip("SAI not in sample data")
        stints = compute_stints(df_sai, total_laps=57)
        assert len(stints) == 2


class TestDetectUndercuts:
    def test_returns_dataframe(self, flagged_df):
        from src.stints import detect_undercuts

        result = detect_undercuts(flagged_df)
        assert hasattr(result, "columns")

    def test_required_columns_present_when_not_empty(self, flagged_df):
        from src.stints import detect_undercuts

        result = detect_undercuts(flagged_df)
        if not result.empty:
            for col in ("driver_a", "team_a", "lap_a", "driver_b", "team_b", "lap_b", "gap_laps"):
                assert col in result.columns

    def test_gap_within_window(self, flagged_df):
        from src.stints import detect_undercuts

        window = 3
        result = detect_undercuts(flagged_df, window=window)
        if not result.empty:
            assert (result["gap_laps"] <= window).all()
            assert (result["gap_laps"] >= 1).all()

    def test_no_self_pairs(self, flagged_df):
        from src.stints import detect_undercuts

        result = detect_undercuts(flagged_df)
        if not result.empty:
            assert (result["driver_a"] != result["driver_b"]).all()

    def test_zero_window_returns_empty(self, flagged_df):
        from src.stints import detect_undercuts

        result = detect_undercuts(flagged_df, window=0)
        assert result.empty
