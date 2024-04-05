import numpy as np
import scipy.signal as sp
import xarray as xr

import xdas
import xdas.signal as xp
from xdas.synthetics import generate


class TestSignal:
    def test_get_sample_spacing(self):
        s = (5.0 / 2) + 5.0 * np.arange(100)
        dt = np.timedelta64(8, "ms")
        t = np.datetime64(0, "s") + dt * np.arange(1000)
        shape = (6000, 1000)
        resolution = (np.timedelta64(8, "ms"), 5.0)
        starttime = np.datetime64("2023-01-01T00:00:00")
        db = xdas.DataArray(
            data=np.random.randn(*shape).astype("float32"),
            coords={
                "time": {
                    "tie_indices": [0, shape[0] - 1],
                    "tie_values": [
                        starttime,
                        starttime + resolution[0] * (shape[0] - 1),
                    ],
                },
                "distance": {
                    "tie_indices": [0, shape[1] - 1],
                    "tie_values": [0.0, resolution[1] * (shape[1] - 1)],
                },
            },
        )
        assert xp.get_sampling_interval(db, "time") == 0.008
        assert xp.get_sampling_interval(db, "distance") == 5.0

    def test_deterend(self):
        n = 100
        d = 5.0
        s = d * np.arange(n)
        da = xr.DataArray(np.arange(n), {"time": s})
        db = xdas.DataArray.from_xarray(da)
        db = xp.detrend(db)
        assert np.allclose(db.values, np.zeros(n))

    def test_differentiate(self):
        n = 100
        d = 5.0
        s = (d / 2) + d * np.arange(n)
        da = xr.DataArray(np.ones(n), {"distance": s})
        db = xdas.DataArray.from_xarray(da)
        db = xp.differentiate(db, midpoints=True)
        assert np.allclose(db.values, np.zeros(n - 1))

    def test_integrate(self):
        n = 100
        d = 5.0
        s = (d / 2) + d * np.arange(n)
        da = xr.DataArray(np.ones(n), {"distance": s})
        db = xdas.DataArray.from_xarray(da)
        db = xp.integrate(db, midpoints=True)
        assert np.allclose(db.values, db["distance"].values)

    def test_segment_mean_removal(self):
        n = 100
        d = 5.0
        s = (d / 2) + d * np.arange(n)
        limits = [0, 0.3 * n * d, n * d]
        s = np.linspace(0, 1000, n)
        data = np.zeros(n)
        da = xr.DataArray(data, {"distance": s})
        da.loc[{"distance": slice(limits[0], limits[1])}] = 1.0
        da.loc[{"distance": slice(limits[1], limits[2])}] = 2.0
        db = xdas.DataArray.from_xarray(da)
        db = xp.segment_mean_removal(db, limits)
        assert np.allclose(db.values, 0)

    def test_sliding_window_removal(self):
        n = 100
        d = 5.0
        s = (d / 2) + d * np.arange(n)
        s = np.linspace(0, 1000, n)
        data = np.ones(n)
        da = xr.DataArray(data, {"distance": s})
        db = xdas.DataArray.from_xarray(da)
        db = xp.sliding_mean_removal(db, 0.1 * n * d)
        assert np.allclose(db.values, 0)

    def test_medfilt(self):
        db = generate()
        result1 = xp.medfilt(db, {"distance": 3})
        result2 = xp.medfilt(db, {"time": 1, "distance": 3})
        assert result1.equals(result2)
        db.data = np.zeros(db.shape)
        assert db.equals(xp.medfilt(db, {"time": 7, "distance": 3}))

    def test_hilbert(self):
        db = generate()
        result = xp.hilbert(db, dim="time")
        assert np.allclose(db.values, np.real(result.values))

    def test_resample(self):
        db = generate()
        result = xp.resample(db, 100, dim="time", window="hamming", domain="time")
        assert result.sizes["time"] == 100

    def test_resample_poly(self):
        db = generate()
        result = xp.resample_poly(db, 2, 5, dim="time")
        assert result.sizes["time"] == 120

    def test_lfilter(self):
        db = generate()
        b, a = sp.iirfilter(4, 0.5, btype="low")
        result1 = xp.lfilter(b, a, db, "time")
        result2, zf = xp.lfilter(b, a, db, "time", zi=...)
        assert result1.equals(result2)

    def test_filtfilt(self):
        db = generate()
        b, a = sp.iirfilter(2, 0.5, btype="low")
        xp.filtfilt(b, a, db, "time", padtype=None)

    def test_sosfilter(self):
        db = generate()
        sos = sp.iirfilter(4, 0.5, btype="low", output="sos")
        result1 = xp.sosfilt(sos, db, "time")
        result2, zf = xp.sosfilt(sos, db, "time", zi=...)
        assert result1.equals(result2)

    def test_sosfiltfilt(self):
        db = generate()
        sos = sp.iirfilter(2, 0.5, btype="low", output="sos")
        xp.sosfiltfilt(sos, db, "time", padtype=None)
