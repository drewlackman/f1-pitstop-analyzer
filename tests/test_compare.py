"""
Unit tests for src/compare.py.
Uses the shared fixtures defined in conftest.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest


class TestLoadMultiple:
    def test_adds_race_column(self, multi_race_csvs):
        from src.compare import load_multiple

        combined = load_multiple(multi_race_csvs)
        assert "race" in combined.columns

    def test_race_labels_derived_from_filenames(self, multi_race_csvs):
        from src.compare import load_multiple

        combined = load_multiple(multi_race_csvs)
        races = combined["race"].unique().tolist()
        # Bahrain and Saudi Arabia CSVs should yield distinct labels
        assert len(races) == 2

    def test_total_rows_equals_sum_of_individual_files(self, multi_race_csvs):
        from src.compare import load_multiple
        from src.analyze import load_data, flag_outliers

        expected_total = sum(len(load_data(p)) for p in multi_race_csvs)
        combined = load_multiple(multi_race_csvs)
        assert len(combined) == expected_total

    def test_has_is_outlier_column(self, multi_race_csvs):
        from src.compare import load_multiple

        combined = load_multiple(multi_race_csvs)
        assert "is_outlier" in combined.columns

    def test_accepts_single_csv(self, sample_csv):
        from src.compare import load_multiple

        combined = load_multiple([sample_csv])
        assert len(combined) > 0
        assert combined["race"].nunique() == 1


class TestCompareTeams:
    def test_returns_pivot_with_race_columns(self, multi_race_csvs):
        from src.compare import load_multiple, compare_teams

        combined = load_multiple(multi_race_csvs)
        pivot = compare_teams(combined)
        assert isinstance(pivot, pd.DataFrame)
        assert pivot.shape[1] == 2  # two races

    def test_values_are_positive_medians(self, multi_race_csvs):
        from src.compare import load_multiple, compare_teams

        combined = load_multiple(multi_race_csvs)
        pivot = compare_teams(combined)
        assert (pivot.dropna() > 0).all().all()

    def test_teams_are_index(self, multi_race_csvs):
        from src.compare import load_multiple, compare_teams

        combined = load_multiple(multi_race_csvs)
        pivot = compare_teams(combined)
        assert pivot.index.name == "team"

    def test_single_race_pivot_has_one_column(self, sample_csv):
        from src.compare import load_multiple, compare_teams

        combined = load_multiple([sample_csv])
        pivot = compare_teams(combined)
        assert pivot.shape[1] == 1


class TestAutoDetectCsvs:
    def test_detects_pit_csvs_in_directory(self, multi_race_csvs, tmp_path):
        from src.compare import _auto_detect_csvs

        # multi_race_csvs are already in tmp_path
        data_dir = multi_race_csvs[0].parent
        found = _auto_detect_csvs(data_dir)
        assert len(found) == 2

    def test_ignores_non_pit_csvs(self, tmp_path):
        from src.compare import _auto_detect_csvs

        (tmp_path / "other_data.csv").write_text("a,b\n1,2\n")
        found = _auto_detect_csvs(tmp_path)
        assert len(found) == 0

    def test_returns_empty_list_for_empty_directory(self, tmp_path):
        from src.compare import _auto_detect_csvs

        found = _auto_detect_csvs(tmp_path)
        assert found == []
