"""Standalone Qt/matplotlib PV archive viewer."""

from __future__ import annotations

import datetime as dt
import sys

import matplotlib.dates as mdates
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT
from matplotlib.figure import Figure

from pv_data import LOCAL_TZ, PV_DEFS, fetch_pv_range, pv_by_label

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
except ImportError:  # pragma: no cover - depends on the deployed Qt binding.
    from PySide6 import QtCore, QtGui, QtWidgets


ALL_PVS_LABEL = "All PVs"


class PVPlotCanvas(FigureCanvasQTAgg):
    """Matplotlib canvas that can plot one PV or all configured PVs."""

    def __init__(self) -> None:
        self.figure = Figure(figsize=(11, 7), constrained_layout=True)
        super().__init__(self.figure)
        self._axes = []

    def plot(self, labels: list[str], start: dt.datetime, end: dt.datetime) -> None:
        self.figure.clear()
        if len(labels) == 1:
            axes = [self.figure.add_subplot(1, 1, 1)]
        else:
            axes = list(self.figure.subplots(2, 2, squeeze=False).ravel())

        for ax, label in zip(axes, labels):
            pv_def = pv_by_label(label)
            ax.set_title(pv_def.label, fontsize=10)
            ax.set_ylabel(pv_def.y_label)
            ax.set_xlabel("Time (local)")
            ax.grid(True, alpha=0.25)

            try:
                timestamps, values = fetch_pv_range(pv_def.name, start, end)
                ax.plot(timestamps, values, linewidth=0.8, color="steelblue")
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=LOCAL_TZ))
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

        self._axes = axes
        self.draw_idle()


class PVViewer(QtWidgets.QMainWindow):
    """Main window for selecting an archive range and refreshing plots."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PV Viewer")
        self.resize(1180, 820)

        self.canvas = PVPlotCanvas()
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.pv_selector = QtWidgets.QComboBox()
        self.pv_selector.addItem(ALL_PVS_LABEL)
        self.pv_selector.addItems([pv_def.label for pv_def in PV_DEFS])

        now = dt.datetime.now(LOCAL_TZ).replace(microsecond=0)
        self.start_edit = self._make_datetime_edit(now - dt.timedelta(hours=8))
        self.end_edit = self._make_datetime_edit(now)
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("PV"))
        controls.addWidget(self.pv_selector, stretch=2)
        controls.addWidget(QtWidgets.QLabel("Start"))
        controls.addWidget(self.start_edit)
        controls.addWidget(QtWidgets.QLabel("End"))
        controls.addWidget(self.end_edit)
        controls.addWidget(self.refresh_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.toolbar)
        layout.addLayout(controls)
        layout.addWidget(self.canvas, stretch=1)

        central = QtWidgets.QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Ready")

        self._install_hotkeys()
        self.refresh()

    def _make_datetime_edit(self, value: dt.datetime):
        edit = QtWidgets.QDateTimeEdit()
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        edit.setDateTime(QtCore.QDateTime(value))
        return edit

    def _selected_labels(self) -> list[str]:
        selected = self.pv_selector.currentText()
        if selected == ALL_PVS_LABEL:
            return [pv_def.label for pv_def in PV_DEFS]
        return [selected]

    def _datetime_from_edit(self, edit) -> dt.datetime:
        value = edit.dateTime().toPyDateTime()
        if value.tzinfo is None:
            return value.replace(tzinfo=LOCAL_TZ)
        return value.astimezone(LOCAL_TZ)

    def refresh(self) -> None:
        start = self._datetime_from_edit(self.start_edit)
        end = self._datetime_from_edit(self.end_edit)
        if end <= start:
            QtWidgets.QMessageBox.warning(
                self, "Invalid time range", "End time must be later than start time."
            )
            return

        self.statusBar().showMessage("Fetching archive data...")
        QtWidgets.QApplication.setOverrideCursor(QtGui.QCursor(QtCore.Qt.WaitCursor))
        try:
            self.canvas.plot(self._selected_labels(), start, end)
            self.statusBar().showMessage(
                f"Showing {start:%Y-%m-%d %H:%M:%S} to {end:%Y-%m-%d %H:%M:%S}"
            )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def _install_hotkeys(self) -> None:
        shortcuts = {
            "r": self.toolbar.home,
            "p": self.toolbar.pan,
            "z": self.toolbar.zoom,
            QtCore.Qt.Key_Left: self.toolbar.back,
            QtCore.Qt.Key_Right: self.toolbar.forward,
        }
        shortcut_cls = getattr(QtWidgets, "QShortcut", QtGui.QShortcut)
        for key, callback in shortcuts.items():
            shortcut = shortcut_cls(QtGui.QKeySequence(key), self)
            shortcut.activated.connect(callback)


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    viewer = PVViewer()
    viewer.show()
    return getattr(app, "exec", app.exec_)()


if __name__ == "__main__":
    raise SystemExit(main())
