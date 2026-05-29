"""Archive access and PV metadata for the PV viewer."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
import requests


ARCHIVER_URL = "http://lcls-archapp.slac.stanford.edu/retrieval/data/getData.json"
TIMEOUT_SECONDS = 20.0
LOCAL_TZ = ZoneInfo("America/Los_Angeles")
MAX_POINTS = 1000


@dataclass(frozen=True)
class PVDefinition:
    """Display metadata for one process variable."""

    label: str
    name: str
    y_label: str


PV_DEFS: tuple[PVDefinition, ...] = (
    PVDefinition("GDET 241 - Pulse Energy (HXR)", "GDET:FEE1:241:ENRC", "Energy (mJ)"),
    PVDefinition(
        "GMD - Pulse Energy (SXR)",
        "EM1K0:GMD:HPS:milliJoulesPerPulse",
        "Energy (mJ)",
    ),
    PVDefinition("QUAD IN20:121 - Magnet", "QUAD:IN20:121:BCTRL", "Field (kG)"),
    PVDefinition("BPM IN20:221 - X Position", "BPMS:IN20:221:X", "Position (mm)"),
)


def _with_local_tz(t: dt.datetime) -> dt.datetime:
    if t.tzinfo is None:
        return t.replace(tzinfo=LOCAL_TZ)
    return t


def to_utc_archiver_string(t: dt.datetime) -> str:
    """Convert a datetime to the UTC string expected by the archive appliance."""

    return (
        _with_local_tz(t)
        .astimezone(dt.timezone.utc)
        .strftime("%Y-%m-%dT%H:%M:%S.000Z")
    )


def pv_by_label(label: str) -> PVDefinition:
    """Return the PV definition matching a display label."""

    for pv_def in PV_DEFS:
        if pv_def.label == label:
            return pv_def
    raise KeyError(f"Unknown PV label: {label}")


def downsample_series(
    timestamps: list[dt.datetime], values: np.ndarray, max_points: int = MAX_POINTS
) -> tuple[list[dt.datetime], np.ndarray]:
    """Evenly downsample long series to keep interactive plotting responsive."""

    if len(timestamps) <= max_points or max_points <= 0:
        return timestamps, values

    indices = np.linspace(0, len(timestamps) - 1, max_points, dtype=int)
    return [timestamps[i] for i in indices], values[indices]


def fetch_pv_range(
    pv_name: str,
    start: dt.datetime,
    end: dt.datetime,
    *,
    session=requests,
    timeout: float = TIMEOUT_SECONDS,
    max_points: int = MAX_POINTS,
) -> tuple[list[dt.datetime], np.ndarray]:
    """Fetch archived data for *pv_name* between *start* and *end*."""

    start = _with_local_tz(start)
    end = _with_local_tz(end)
    if end <= start:
        raise ValueError("End time must be later than start time")

    response = session.get(
        ARCHIVER_URL,
        params={
            "pv": pv_name,
            "from": to_utc_archiver_string(start),
            "to": to_utc_archiver_string(end),
        },
        timeout=timeout,
    )
    response.raise_for_status()

    payload = response.json()
    if not payload or "data" not in payload[0] or not payload[0]["data"]:
        raise RuntimeError(f"No data returned for PV: {pv_name}")

    data = payload[0]["data"]
    seconds = np.array([point["secs"] + point.get("nanos", 0) * 1e-9 for point in data])
    values = np.array([point["val"] for point in data], dtype=float)
    timestamps = [dt.datetime.fromtimestamp(sec, tz=LOCAL_TZ) for sec in seconds]
    return downsample_series(timestamps, values, max_points=max_points)


def fetch_pv(
    pv_name: str, hours_back: float = 8.0
) -> tuple[list[dt.datetime], np.ndarray]:
    """Fetch archived data for *pv_name* covering the last *hours_back* hours."""

    end = dt.datetime.now(LOCAL_TZ)
    start = end - dt.timedelta(hours=hours_back)
    return fetch_pv_range(pv_name, start, end)
