"""Tests for the PV Viewer application."""

import datetime as dt
import os
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from pv_viewer_app import (
    _to_utc_str,
    downsample,
    fetch_pv,
    PV_DEFS,
    LOCAL_TZ,
)


# ── Unit tests for utility functions ──────────────────────────────────────────


class TestToUtcStr:
    def test_aware_datetime(self):
        t = dt.datetime(2024, 6, 15, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        result = _to_utc_str(t)
        assert result == "2024-06-15T19:00:00.000Z"

    def test_naive_datetime_assumes_local(self):
        t = dt.datetime(2024, 1, 15, 8, 0, 0)
        result = _to_utc_str(t)
        assert result == "2024-01-15T16:00:00.000Z"


class TestDownsample:
    def test_no_downsample_when_under_limit(self):
        ts = list(range(100))
        vals = np.arange(100, dtype=float)
        ts_out, vals_out = downsample(ts, vals, max_points=200)
        assert len(ts_out) == 100
        assert len(vals_out) == 100

    def test_downsamples_when_over_limit(self):
        ts = list(range(5000))
        vals = np.arange(5000, dtype=float)
        ts_out, vals_out = downsample(ts, vals, max_points=1000)
        assert len(ts_out) == 1000
        assert len(vals_out) == 1000

    def test_preserves_first_and_last(self):
        ts = list(range(2000))
        vals = np.arange(2000, dtype=float)
        ts_out, vals_out = downsample(ts, vals, max_points=500)
        assert ts_out[0] == 0
        assert ts_out[-1] == 1999


class TestFetchPV:
    def test_successful_fetch(self):
        mock_data = [
            {
                "data": [
                    {"secs": 1700000000, "nanos": 0, "val": 1.5},
                    {"secs": 1700000001, "nanos": 500000000, "val": 2.5},
                ]
            }
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = mock_data
        mock_response.raise_for_status = MagicMock()

        with patch("pv_viewer_app.requests.get", return_value=mock_response):
            start = dt.datetime(2023, 11, 14, 0, 0, 0, tzinfo=LOCAL_TZ)
            end = dt.datetime(2023, 11, 15, 0, 0, 0, tzinfo=LOCAL_TZ)
            timestamps, values = fetch_pv("TEST:PV", start, end)

        assert len(timestamps) == 2
        assert len(values) == 2
        assert values[0] == 1.5
        assert values[1] == 2.5

    def test_empty_response_raises(self):
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()

        with patch("pv_viewer_app.requests.get", return_value=mock_response):
            start = dt.datetime(2023, 11, 14, 0, 0, 0, tzinfo=LOCAL_TZ)
            end = dt.datetime(2023, 11, 15, 0, 0, 0, tzinfo=LOCAL_TZ)
            with pytest.raises(RuntimeError, match="No data returned"):
                fetch_pv("TEST:PV", start, end)


# ── GUI tests (use PyQt5 directly, no pytest-qt to avoid PySide6 conflict) ───


def _make_mock_response():
    mock_data = [
        {
            "data": [
                {"secs": 1700000000 + i, "nanos": 0, "val": float(i)}
                for i in range(10)
            ]
        }
    ]
    mock_response = MagicMock()
    mock_response.json.return_value = mock_data
    mock_response.raise_for_status = MagicMock()
    return mock_response


@pytest.fixture(scope="module")
def gui_window():
    """Create the application window with mocked data fetching."""
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt5.QtWidgets import QApplication
    from pv_viewer_app import PVViewerWindow

    _app = QApplication.instance() or QApplication([])
    with patch("pv_viewer_app.requests.get", return_value=_make_mock_response()):
        window = PVViewerWindow()
    yield window
    window.close()


class TestGUI:
    def test_window_title(self, gui_window):
        assert gui_window.windowTitle() == "PV Viewer"

    def test_default_view_is_all(self, gui_window):
        assert gui_window._view_all is True
        assert gui_window._view_combo.currentIndex() == 0

    def test_initial_plot_has_4_axes(self, gui_window):
        axes = gui_window._figure.get_axes()
        assert len(axes) == 4

    def test_switch_to_single_pv(self, gui_window):
        with patch("pv_viewer_app.requests.get", return_value=_make_mock_response()):
            gui_window._view_combo.setCurrentIndex(1)
            assert gui_window._view_all is False
            axes = gui_window._figure.get_axes()
            assert len(axes) == 1

    def test_switch_back_to_all(self, gui_window):
        with patch("pv_viewer_app.requests.get", return_value=_make_mock_response()):
            gui_window._view_combo.setCurrentIndex(0)
            assert gui_window._view_all is True
            axes = gui_window._figure.get_axes()
            assert len(axes) == 4

    def test_refresh_button_exists(self, gui_window):
        assert gui_window._refresh_btn is not None
        assert gui_window._refresh_btn.text() == "&Refresh"

    def test_time_range_edits_exist(self, gui_window):
        assert gui_window._start_edit is not None
        assert gui_window._end_edit is not None

    def test_toolbar_exists(self, gui_window):
        assert gui_window._toolbar is not None
