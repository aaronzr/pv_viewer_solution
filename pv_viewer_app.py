#!/usr/bin/env python3
"""
PV Viewer — Standalone PyQt5 application for viewing archived LCLS PV data.

Displays XGMD and GDet data from the archive appliance with interactive
matplotlib plots. Supports time range selection, refresh, single/all PV views,
hotkeys, and downsampling for long time ranges.
"""

import sys
import datetime as dt
from zoneinfo import ZoneInfo

import numpy as np
import requests
import matplotlib

matplotlib.use("Qt5Agg")

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QComboBox,
    QLabel,
    QDateTimeEdit,
    QMessageBox,
    QSizePolicy,
)
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtGui import QKeySequence

# ── Configuration ─────────────────────────────────────────────────────────────

ARCHIVER_URL = "http://lcls-archapp.slac.stanford.edu/retrieval/data/getData.json"
TIMEOUT_SECONDS = 20.0
LOCAL_TZ = ZoneInfo("America/Los_Angeles")
DEFAULT_HOURS_BACK = 8.0
MAX_POINTS = 1000

PV_DEFS = {
    "GDET 241 — Pulse Energy (HXR)": ("GDET:FEE1:241:ENRC", "Energy (mJ)"),
    "GMD — Pulse Energy (SXR)": ("EM1K0:GMD:HPS:milliJoulesPerPulse", "Energy (mJ)"),
    "QUAD IN20:121 — Magnet": ("QUAD:IN20:121:BCTRL", "Field (kG)"),
    "BPM IN20:221 — X Position": ("BPMS:IN20:221:X", "Position (mm)"),
}


# ── Data fetching ─────────────────────────────────────────────────────────────


def _to_utc_str(t: dt.datetime) -> str:
    if t.tzinfo is None:
        t = t.replace(tzinfo=LOCAL_TZ)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def downsample(timestamps, values, max_points=MAX_POINTS):
    if len(values) <= max_points:
        return timestamps, values
    indices = np.linspace(0, len(values) - 1, max_points, dtype=int)
    return [timestamps[i] for i in indices], values[indices]


def fetch_pv(pv_name: str, start: dt.datetime, end: dt.datetime):
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
    secs = np.array([d["secs"] + d.get("nanos", 0) * 1e-9 for d in data])
    vals = np.array([d["val"] for d in data], dtype=float)

    timestamps = [dt.datetime.fromtimestamp(s, tz=LOCAL_TZ) for s in secs]
    return timestamps, vals


# ── Main Window ───────────────────────────────────────────────────────────────


class PVViewerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PV Viewer")
        self.resize(1100, 800)

        self._pv_labels = list(PV_DEFS.keys())
        self._view_all = True

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Control bar ---
        controls = QHBoxLayout()
        layout.addLayout(controls)

        controls.addWidget(QLabel("From:"))
        self._start_edit = QDateTimeEdit()
        self._start_edit.setCalendarPopup(True)
        self._start_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        controls.addWidget(self._start_edit)

        controls.addWidget(QLabel("To:"))
        self._end_edit = QDateTimeEdit()
        self._end_edit.setCalendarPopup(True)
        self._end_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        controls.addWidget(self._end_edit)

        self._refresh_btn = QPushButton("&Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh)
        controls.addWidget(self._refresh_btn)

        controls.addWidget(QLabel("View:"))
        self._view_combo = QComboBox()
        self._view_combo.addItem("All PVs")
        for label in self._pv_labels:
            self._view_combo.addItem(label)
        self._view_combo.currentIndexChanged.connect(self._on_view_changed)
        controls.addWidget(self._view_combo)

        # --- Matplotlib canvas ---
        self._figure = plt.figure(figsize=(11, 8))
        self._canvas = FigureCanvas(self._figure)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._toolbar = NavigationToolbar(self._canvas, self)
        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)

        # --- Set default time range (last 8 hours) ---
        now = dt.datetime.now(LOCAL_TZ)
        start = now - dt.timedelta(hours=DEFAULT_HOURS_BACK)
        self._start_edit.setDateTime(self._to_qdatetime(start))
        self._end_edit.setDateTime(self._to_qdatetime(now))

        # --- Initial plot ---
        self._on_refresh()

    def _to_qdatetime(self, t: dt.datetime) -> QDateTime:
        return QDateTime(
            t.year, t.month, t.day, t.hour, t.minute, t.second
        )

    def _get_time_range(self):
        qstart = self._start_edit.dateTime()
        qend = self._end_edit.dateTime()
        start = dt.datetime(
            qstart.date().year(), qstart.date().month(), qstart.date().day(),
            qstart.time().hour(), qstart.time().minute(), qstart.time().second(),
            tzinfo=LOCAL_TZ,
        )
        end = dt.datetime(
            qend.date().year(), qend.date().month(), qend.date().day(),
            qend.time().hour(), qend.time().minute(), qend.time().second(),
            tzinfo=LOCAL_TZ,
        )
        return start, end

    def _on_view_changed(self, index):
        self._view_all = index == 0
        self._on_refresh()

    def _on_refresh(self):
        start, end = self._get_time_range()
        self._figure.clear()

        if self._view_all:
            self._plot_all(start, end)
        else:
            label = self._view_combo.currentText()
            self._plot_single(label, start, end)

        self._figure.tight_layout()
        self._canvas.draw()

    def _plot_all(self, start, end):
        for i, label in enumerate(self._pv_labels):
            ax = self._figure.add_subplot(4, 1, i + 1)
            self._plot_on_axis(ax, label, start, end)

    def _plot_single(self, label, start, end):
        ax = self._figure.add_subplot(1, 1, 1)
        self._plot_on_axis(ax, label, start, end)

    def _plot_on_axis(self, ax, label, start, end):
        pv_name, y_label = PV_DEFS[label]
        ax.set_title(label, fontsize=10)
        ax.set_ylabel(y_label)
        ax.set_xlabel("Time (local)")

        try:
            timestamps, values = fetch_pv(pv_name, start, end)
            timestamps, values = downsample(timestamps, values)
            ax.plot(timestamps, values, linewidth=0.8, color="steelblue")
            ax.xaxis.set_major_formatter(
                mdates.DateFormatter("%H:%M", tz=LOCAL_TZ)
            )
            self._figure.autofmt_xdate(rotation=30)
        except Exception as exc:
            ax.text(
                0.5, 0.5, f"Error:\n{exc}",
                ha="center", va="center", transform=ax.transAxes,
                color="firebrick", fontsize=9,
            )

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Z:
            self._toolbar.zoom()
        elif key == Qt.Key_P:
            self._toolbar.pan()
        elif key == Qt.Key_R:
            self._toolbar.home()
        elif key == Qt.Key_Left:
            self._toolbar.back()
        elif key == Qt.Key_Right:
            self._toolbar.forward()
        else:
            super().keyPressEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────


def main():
    app = QApplication(sys.argv)
    window = PVViewerWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
