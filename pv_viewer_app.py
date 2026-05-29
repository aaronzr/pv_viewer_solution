#!/usr/bin/env python3
"""Standalone archived PV viewer with a Qt GUI and matplotlib canvas."""

from __future__ import annotations

import datetime as dt
import sys
from dataclasses import dataclass
from typing import Dict, Tuple
from zoneinfo import ZoneInfo

import matplotlib.dates as mdates
import numpy as np
import requests
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

try:
    from PyQt5 import QtCore, QtWidgets
except ImportError:
    from PySide6 import QtCore, QtWidgets


ARCHIVER_URL = "http://lcls-archapp.slac.stanford.edu/retrieval/data/getData.json"
TIMEOUT_SECONDS = 20.0
LOCAL_TZ = ZoneInfo("America/Los_Angeles")

# Display label -> (pv_name, y-axis label)
PV_DEFS: Dict[str, Tuple[str, str]] = {
    "GDET 241 - Pulse Energy (HXR)": ("GDET:FEE1:241:ENRC", "Energy (mJ)"),
    "GMD - Pulse Energy (SXR)": ("EM1K0:GMD:HPS:milliJoulesPerPulse", "Energy (mJ)"),
    "QUAD IN20:121 - Magnet": ("QUAD:IN20:121:BCTRL", "Field (kG)"),
    "BPM IN20:221 - X Position": ("BPMS:IN20:221:X", "Position (mm)"),
}


def _to_utc_str(t: dt.datetime) -> str:
    """Convert a datetime to the ISO-8601 UTC format expected by the archiver."""
    if t.tzinfo is None:
        t = t.replace(tzinfo=LOCAL_TZ)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def fetch_pv_range(pv_name: str, start: dt.datetime, end: dt.datetime) -> tuple[list[dt.datetime], np.ndarray]:
    """Fetch archived data for *pv_name* over [start, end]."""
    response = requests.get(
        ARCHIVER_URL,
        params={"pv": pv_name, "from": _to_utc_str(start), "to": _to_utc_str(end)},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    payload = response.json()
    if not payload or "data" not in payload[0]:
        raise RuntimeError(f"No data returned for PV: {pv_name}")

    data = payload[0]["data"]
    if not data:
        raise RuntimeError(f"Empty data returned for PV: {pv_name}")

    secs = np.array([d["secs"] + d.get("nanos", 0) * 1e-9 for d in data])
    vals = np.array([d["val"] for d in data], dtype=float)
    timestamps = [dt.datetime.fromtimestamp(s, tz=LOCAL_TZ) for s in secs]
    return timestamps, vals


@dataclass
class TimeRange:
    start: dt.datetime
    end: dt.datetime


class PVViewer(QtWidgets.QWidget):
    """Qt widget for plotting four archived PVs on one canvas."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PV Viewer")
        self.resize(1200, 850)

        self.figure = Figure(figsize=(12, 8), constrained_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar(self.canvas, self)

        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.addWidget(QtWidgets.QLabel("Start:"))
        self.start_picker = QtWidgets.QDateTimeEdit(self)
        self.start_picker.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_picker.setCalendarPopup(True)
        controls_layout.addWidget(self.start_picker)

        controls_layout.addWidget(QtWidgets.QLabel("End:"))
        self.end_picker = QtWidgets.QDateTimeEdit(self)
        self.end_picker.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_picker.setCalendarPopup(True)
        controls_layout.addWidget(self.end_picker)

        self.refresh_button = QtWidgets.QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.refresh_plots)
        controls_layout.addWidget(self.refresh_button)
        controls_layout.addStretch(1)

        self.status_label = QtWidgets.QLabel("")

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.addLayout(controls_layout)
        root_layout.addWidget(self.toolbar)
        root_layout.addWidget(self.canvas)
        root_layout.addWidget(self.status_label)

        self._set_default_range()
        self.refresh_plots()

    def _set_default_range(self) -> None:
        # Default to the most recent 8 hours.
        end = dt.datetime.now(LOCAL_TZ)
        start = end - dt.timedelta(hours=8)
        self._set_picker_values(TimeRange(start=start, end=end))

    def _set_picker_values(self, timerange: TimeRange) -> None:
        start_qdt = QtCore.QDateTime.fromString(
            timerange.start.strftime("%Y-%m-%d %H:%M:%S"),
            "yyyy-MM-dd HH:mm:ss",
        )
        end_qdt = QtCore.QDateTime.fromString(
            timerange.end.strftime("%Y-%m-%d %H:%M:%S"),
            "yyyy-MM-dd HH:mm:ss",
        )
        self.start_picker.setDateTime(start_qdt)
        self.end_picker.setDateTime(end_qdt)

    def _get_timerange(self) -> TimeRange:
        start = self.start_picker.dateTime().toPyDateTime().replace(tzinfo=LOCAL_TZ)
        end = self.end_picker.dateTime().toPyDateTime().replace(tzinfo=LOCAL_TZ)
        return TimeRange(start=start, end=end)

    def refresh_plots(self) -> None:
        timerange = self._get_timerange()
        if timerange.end <= timerange.start:
            self.status_label.setText("End time must be after start time.")
            return

        self.refresh_button.setEnabled(False)
        self.status_label.setText("Fetching data...")
        QtWidgets.QApplication.processEvents()

        self.figure.clear()
        axes = self.figure.subplots(2, 2, sharex=False)
        axes_flat = list(np.ravel(axes))

        for ax, (label, (pv_name, y_label)) in zip(axes_flat, PV_DEFS.items()):
            ax.set_title(label, fontsize=10)
            ax.set_xlabel("Time (local)")
            ax.set_ylabel(y_label)
            try:
                timestamps, values = fetch_pv_range(pv_name, timerange.start, timerange.end)
                ax.plot(timestamps, values, linewidth=0.8, color="steelblue")
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M", tz=LOCAL_TZ))
                ax.tick_params(axis="x", rotation=20)
            except Exception as exc:
                ax.text(
                    0.5,
                    0.5,
                    f"Error fetching data:\n{exc}",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                    color="firebrick",
                    fontsize=9,
                )

        self.canvas.draw_idle()
        self.refresh_button.setEnabled(True)
        self.status_label.setText("Plot refreshed.")


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    widget = PVViewer()
    widget.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())