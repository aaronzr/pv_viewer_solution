import datetime as dt

import numpy as np
import pytest

from pv_data import LOCAL_TZ, downsample_series, fetch_pv_range, to_utc_archiver_string


def test_to_utc_archiver_string_treats_naive_datetime_as_local():
    local_time = dt.datetime(2026, 1, 15, 12, 30, 5)

    assert to_utc_archiver_string(local_time) == "2026-01-15T20:30:05.000Z"


def test_downsample_series_keeps_first_and_last_points():
    timestamps = [
        dt.datetime(2026, 1, 1, tzinfo=LOCAL_TZ) + dt.timedelta(seconds=i)
        for i in range(10)
    ]
    values = np.arange(10, dtype=float)

    sampled_timestamps, sampled_values = downsample_series(timestamps, values, max_points=4)

    assert len(sampled_timestamps) == 4
    assert sampled_timestamps[0] == timestamps[0]
    assert sampled_timestamps[-1] == timestamps[-1]
    np.testing.assert_array_equal(sampled_values, np.array([0.0, 3.0, 6.0, 9.0]))


def test_fetch_pv_range_builds_request_and_parses_payload():
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return [
                {
                    "data": [
                        {"secs": 1_767_200_400, "nanos": 0, "val": 1.5},
                        {"secs": 1_767_200_401, "nanos": 500_000_000, "val": 2.5},
                    ]
                }
            ]

    class Session:
        def __init__(self):
            self.calls = []

        def get(self, url, params, timeout):
            self.calls.append((url, params, timeout))
            return Response()

    session = Session()
    start = dt.datetime(2026, 1, 1, 8, 0, tzinfo=LOCAL_TZ)
    end = start + dt.timedelta(minutes=5)

    timestamps, values = fetch_pv_range(
        "TEST:PV", start, end, session=session, timeout=3.0
    )

    assert session.calls[0][1]["pv"] == "TEST:PV"
    assert session.calls[0][1]["from"] == to_utc_archiver_string(start)
    assert session.calls[0][1]["to"] == to_utc_archiver_string(end)
    assert session.calls[0][2] == 3.0
    assert timestamps[0].tzinfo == LOCAL_TZ
    np.testing.assert_array_equal(values, np.array([1.5, 2.5]))


def test_fetch_pv_range_rejects_invalid_range():
    start = dt.datetime(2026, 1, 1, 8, 0, tzinfo=LOCAL_TZ)

    with pytest.raises(ValueError, match="End time"):
        fetch_pv_range("TEST:PV", start, start)
