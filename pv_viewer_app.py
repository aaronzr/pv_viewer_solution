"""
PV Viewer — Standalone PyQt5 application.
Displays archived pulse-energy PVs in a 2x2 subplot grid with interactive
matplotlib controls (zoom, pan, home, save).
"""

import sys
import datetime as dt
import re
from zoneinfo import ZoneInfo

import numpy as np
import requests
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QMessageBox, QDateTimeEdit, QLineEdit, QComboBox, QShortcut,
)
from PyQt5.QtCore import QDateTime, Qt
from PyQt5.QtGui import QKeySequence
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar,
)
from matplotlib.figure import Figure
import matplotlib.dates as mdates

ARCHIVER_URL = "http://lcls-archapp.slac.stanford.edu/retrieval/data/getData.json"
TIMEOUT_SECONDS = 20.0
LOCAL_TZ = ZoneInfo("America/Los_Angeles")
MAX_PLOT_POINTS = 1000
RELATIVE_TIME_RE = re.compile(r"^-(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")

PV_DEFS = {
    "GMD — Pulse Energy (SXR)":      ("EM1K0:GMD:HPS:milliJoulesPerPulse",  "Energy (mJ)"),
    "XGMD — Pulse Energy (SXR)":     ("EM2K0:XGMD:HPS:milliJoulesPerPulse", "Energy (mJ)"),
    "GDET 241 — Pulse Energy (HXR)": ("GDET:FEE1:241:ENRC",                 "Energy (mJ)"),
    "GDET 361 — Pulse Energy (HXR)": ("GDET:FEE1:361:ENRC",                 "Energy (mJ)"),
}


def _to_utc_str(t: dt.datetime) -> str:
    if t.tzinfo is None:
        t = t.replace(tzinfo=LOCAL_TZ)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def fetch_pv(pv_name: str, start: dt.datetime, end: dt.datetime):
    response = requests.get(
        ARCHIVER_URL,
        params={"pv": pv_name, "from": _to_utc_str(start), "to": _to_utc_str(end)},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload or "data" not in payload[0]:
        return [], np.array([])
    data = payload[0]["data"]
    secs = np.array([d["secs"] + d.get("nanos", 0) * 1e-9 for d in data])
    vals = np.array([d["val"] for d in data], dtype=float)
    timestamps = [dt.datetime.fromtimestamp(s, tz=LOCAL_TZ) for s in secs]
    return timestamps, vals


def downsample_series(timestamps, values, max_points: int = MAX_PLOT_POINTS):
    if len(values) <= max_points:
        return timestamps, values

    idx = np.linspace(0, len(values) - 1, max_points, dtype=int)
    sampled_times = [timestamps[i] for i in idx]
    sampled_values = values[idx]
    return sampled_times, sampled_values


class PVViewerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PV Viewer")
        self.setMinimumSize(1000, 700)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self._build_controls(layout)

        # --- Matplotlib figure with subplots ---
        self.figure = Figure(figsize=(10, 7), tight_layout=True)
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setFocusPolicy(Qt.StrongFocus)
        self.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.toolbar = NavigationToolbar(self.canvas, self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)

        self._wire_hotkeys()

        # Default to last 8 hours on startup.
        self.set_last_8_hours()
        self.refresh_plots()

    def _build_controls(self, parent_layout: QVBoxLayout):
        row1 = QHBoxLayout()
        now_local = dt.datetime.now(LOCAL_TZ).replace(second=0, microsecond=0)
        start_local = now_local - dt.timedelta(hours=8)

        row1.addWidget(QLabel("Start:"))
        self.start_input = QDateTimeEdit()
        self.start_input.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_input.setCalendarPopup(True)
        self.start_input.setDateTime(QDateTime(start_local.year, start_local.month, start_local.day,
                               start_local.hour, start_local.minute, start_local.second))
        row1.addWidget(self.start_input)

        self.start_text = QLineEdit("-8h")
        self.start_text.setPlaceholderText("relative/absolute (e.g. -8h, 2026-06-01 08:00:00)")
        self.start_text.setClearButtonEnabled(True)
        self.start_text.setMinimumWidth(300)
        row1.addWidget(self.start_text)

        row1.addWidget(QLabel("End:"))
        self.end_input = QDateTimeEdit()
        self.end_input.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.end_input.setCalendarPopup(True)
        self.end_input.setDateTime(QDateTime(now_local.year, now_local.month, now_local.day,
                             now_local.hour, now_local.minute, now_local.second))
        row1.addWidget(self.end_input)

        self.end_text = QLineEdit("now")
        self.end_text.setPlaceholderText("relative/absolute (e.g. now, -5m, 2026-06-01T16:00:00)")
        self.end_text.setClearButtonEnabled(True)
        self.end_text.setMinimumWidth(240)
        row1.addWidget(self.end_text)

        parent_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("View:"))
        self.view_selector = QComboBox()
        self.view_selector.addItem("All PVs")
        for label in PV_DEFS:
            self.view_selector.addItem(label)
        self.view_selector.currentIndexChanged.connect(self.refresh_plots)
        row2.addWidget(self.view_selector)

        self.last_8h_btn = QPushButton("Last 8h")
        self.last_8h_btn.clicked.connect(self.set_last_8_hours)
        row2.addWidget(self.last_8h_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_plots)
        row2.addWidget(self.refresh_btn)

        hotkey_hint = QLabel("Hotkeys: z=zoom, p=pan, r=reset, left=back, right=forward")
        row2.addWidget(hotkey_hint)
        row2.addStretch()
        parent_layout.addLayout(row2)

    def _wire_hotkeys(self):
        bindings = [
            ("z", self.toolbar.zoom),
            ("p", self.toolbar.pan),
            ("r", self.toolbar.home),
            ("Left", self.toolbar.back),
            ("Right", self.toolbar.forward),
        ]
        self._shortcuts = []
        for key, handler in bindings:
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ApplicationShortcut)
            shortcut.activated.connect(handler)
            self._shortcuts.append(shortcut)

    def _on_canvas_click(self, _event):
        self.start_text.clearFocus()
        self.end_text.clearFocus()
        self.start_input.clearFocus()
        self.end_input.clearFocus()
        self.canvas.setFocus(Qt.MouseFocusReason)

    def set_last_8_hours(self):
        now_local = dt.datetime.now(LOCAL_TZ).replace(second=0, microsecond=0)
        start_local = now_local - dt.timedelta(hours=8)
        self.start_input.setDateTime(QDateTime(start_local.year, start_local.month, start_local.day,
                                               start_local.hour, start_local.minute, start_local.second))
        self.end_input.setDateTime(QDateTime(now_local.year, now_local.month, now_local.day,
                                             now_local.hour, now_local.minute, now_local.second))
        self.start_text.setText("-8h")
        self.end_text.setText("now")

    @staticmethod
    def _qdatetime_to_local(qt_dt: QDateTime) -> dt.datetime:
        py_dt = qt_dt.toPyDateTime()
        if py_dt.tzinfo is None:
            return py_dt.replace(tzinfo=LOCAL_TZ)
        return py_dt.astimezone(LOCAL_TZ)

    @staticmethod
    def _parse_absolute_time(text: str) -> dt.datetime:
        cleaned = text.strip().replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=LOCAL_TZ)
        return parsed.astimezone(LOCAL_TZ)

    @staticmethod
    def _parse_relative_time(text: str, now_local: dt.datetime) -> dt.datetime:
        if text == "now":
            return now_local

        match = RELATIVE_TIME_RE.match(text)
        if not match:
            raise ValueError(
                "Relative time must look like -5m, -8h, -1d16h, or now."
            )

        days, hours, minutes, seconds = match.groups()
        if not any([days, hours, minutes, seconds]):
            raise ValueError("Relative duration is empty.")

        delta = dt.timedelta(
            days=int(days or 0),
            hours=int(hours or 0),
            minutes=int(minutes or 0),
            seconds=int(seconds or 0),
        )
        return now_local - delta

    def _resolve_time_input(self, text_input: QLineEdit, picker: QDateTimeEdit, now_local: dt.datetime) -> dt.datetime:
        raw = text_input.text().strip()
        if not raw:
            return self._qdatetime_to_local(picker.dateTime())

        lowered = raw.lower()
        if lowered == "now" or lowered.startswith("-"):
            resolved = self._parse_relative_time(lowered, now_local)
        else:
            resolved = self._parse_absolute_time(raw)

        picker.setDateTime(QDateTime(resolved.year, resolved.month, resolved.day,
                                     resolved.hour, resolved.minute, resolved.second))
        return resolved

    def _active_pv_items(self):
        selected = self.view_selector.currentText()
        if selected == "All PVs":
            return list(PV_DEFS.items())
        return [(selected, PV_DEFS[selected])]

    def _build_axes(self, plot_count: int):
        self.figure.clear()
        if plot_count == 1:
            return [self.figure.subplots(1, 1)]
        axes_vertical = self.figure.subplots(plot_count, 1, squeeze=False)
        return [row[0] for row in axes_vertical]

    def refresh_plots(self):
        now_local = dt.datetime.now(LOCAL_TZ)
        try:
            start = self._resolve_time_input(self.start_text, self.start_input, now_local)
            end = self._resolve_time_input(self.end_text, self.end_input, now_local)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid time input", str(exc))
            return

        if start >= end:
            QMessageBox.warning(self, "Invalid time range", "Start time must be earlier than end time.")
            return

        pv_items = self._active_pv_items()
        axes = self._build_axes(len(pv_items))

        for ax, (label, (pv_name, y_label)) in zip(axes, pv_items):
            ax.clear()
            ax.set_title(label, fontsize=10)
            ax.set_ylabel(y_label, fontsize=8)
            ax.set_xlabel("Time (local)", fontsize=8)
            try:
                timestamps, values = fetch_pv(pv_name, start, end)
                if len(timestamps) > 0:
                    timestamps, values = downsample_series(timestamps, values)
                    ax.plot(timestamps, values, linewidth=0.7, color="steelblue")
                    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=LOCAL_TZ))
                    for tick in ax.get_xticklabels():
                        tick.set_rotation(30)
                        tick.set_fontsize(7)
                else:
                    ax.text(0.5, 0.5, "No data", ha="center", va="center",
                            transform=ax.transAxes, color="gray")
            except Exception as exc:
                ax.text(0.5, 0.5, f"Error:\n{exc}", ha="center", va="center",
                        transform=ax.transAxes, color="firebrick", fontsize=8)

        self.figure.tight_layout()
        self.canvas.draw()


def main():
    app = QApplication(sys.argv)
    window = PVViewerWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
