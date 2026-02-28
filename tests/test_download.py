"""
Unit tests for src/download_pitstops_openf1.py.
Uses unittest.mock to avoid real network calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


SESSION_FIXTURE = [
    {
        "session_key": 9472,
        "session_name": "Race",
        "country_name": "Bahrain",
        "year": 2024,
        "date_start": "2024-03-02T15:00:00",
    }
]

PIT_CSV_CONTENT = (
    "date,driver_number,lap_number,meeting_key,pit_duration,session_key\n"
    "2024-03-02 15:06:11,27,1,1229,36.6,9472\n"
    "2024-03-02 15:19:05,24,9,1229,25.2,9472\n"
)


class TestGetSessionKey:
    def _mock_response(self, data):
        mock = MagicMock()
        mock.json.return_value = data
        mock.raise_for_status.return_value = None
        return mock

    def test_returns_integer_key(self):
        from src.download_pitstops_openf1 import get_session_key

        with patch("src.download_pitstops_openf1.requests.get") as mock_get:
            mock_get.return_value = self._mock_response(SESSION_FIXTURE)
            key = get_session_key(2024, "Bahrain", "Race")

        assert isinstance(key, int)
        assert key == 9472

    def test_picks_latest_session_when_multiple(self):
        from src.download_pitstops_openf1 import get_session_key

        multi = [
            {**SESSION_FIXTURE[0], "session_key": 100, "date_start": "2024-03-01"},
            {**SESSION_FIXTURE[0], "session_key": 200, "date_start": "2024-03-02"},
        ]
        with patch("src.download_pitstops_openf1.requests.get") as mock_get:
            mock_get.return_value = self._mock_response(multi)
            key = get_session_key(2024, "Bahrain", "Race")

        assert key == 200

    def test_raises_on_empty_response(self):
        from src.download_pitstops_openf1 import get_session_key

        with patch("src.download_pitstops_openf1.requests.get") as mock_get:
            mock_get.return_value = self._mock_response([])
            with pytest.raises(ValueError, match="No sessions found"):
                get_session_key(2024, "Nowhere", "Race")

    def test_passes_correct_params(self):
        from src.download_pitstops_openf1 import get_session_key

        with patch("src.download_pitstops_openf1.requests.get") as mock_get:
            mock_get.return_value = self._mock_response(SESSION_FIXTURE)
            get_session_key(2023, "Italy", "Qualifying")

        _, kwargs = mock_get.call_args
        params = kwargs.get("params", mock_get.call_args[0][1] if len(mock_get.call_args[0]) > 1 else {})
        # params may be positional
        call_kwargs = mock_get.call_args.kwargs
        call_params = call_kwargs.get("params", {})
        assert call_params.get("year") == 2023
        assert call_params.get("country_name") == "Italy"
        assert call_params.get("session_name") == "Qualifying"


class TestDownloadPitCsv:
    def _mock_csv_response(self):
        mock = MagicMock()
        mock.content = PIT_CSV_CONTENT.encode()
        mock.raise_for_status.return_value = None
        return mock

    def test_creates_csv_file(self, tmp_path: Path):
        from src.download_pitstops_openf1 import download_pit_csv

        out = tmp_path / "pit.csv"
        with patch("src.download_pitstops_openf1.requests.get") as mock_get:
            mock_get.return_value = self._mock_csv_response()
            df = download_pit_csv(9472, out)

        assert out.exists()
        assert len(df) == 2

    def test_returns_dataframe(self, tmp_path: Path):
        from src.download_pitstops_openf1 import download_pit_csv

        out = tmp_path / "pit.csv"
        with patch("src.download_pitstops_openf1.requests.get") as mock_get:
            mock_get.return_value = self._mock_csv_response()
            result = download_pit_csv(9472, out)

        assert isinstance(result, pd.DataFrame)
        assert "pit_duration" in result.columns

    def test_creates_parent_directories(self, tmp_path: Path):
        from src.download_pitstops_openf1 import download_pit_csv

        out = tmp_path / "nested" / "dir" / "pit.csv"
        with patch("src.download_pitstops_openf1.requests.get") as mock_get:
            mock_get.return_value = self._mock_csv_response()
            download_pit_csv(9472, out)

        assert out.exists()
