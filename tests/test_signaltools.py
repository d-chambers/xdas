import dask.array as da
import numpy as np
import scipy.signal as sp

from xdas.database import Coordinate, Database
from xdas.signaltools import LFilter, SignalProcessingChain


class TestSignal:
    def test_signal(self):
        fs = 125
        ks = 1 / 10
        data = da.random.normal(size=(1000, 100))
        time = Coordinate([0, data.shape[0] - 1], [0.0, (data.shape[0] - 1) / fs])
        distance = Coordinate([0, data.shape[1] - 1], [0.0, (data.shape[1] - 1) / ks])
        xarr = Database(data, {"time": time, "distance": distance})
        b, a = sp.iirfilter(4, 0.5, btype="lowpass")
        lfilter = LFilter(b, a, "time")
        result_direct = lfilter(xarr)
        chunk_size = 100
        lfilter.reset()
        result_chunks = xarr.copy()
        for k in range(xarr.shape[0] // chunk_size):
            query = {"time": slice(k * chunk_size, (k + 1) * chunk_size)}
            result_chunks[query] = lfilter(xarr[query]).data
        lfilter.reset()
        chain = SignalProcessingChain([lfilter])
        out = chain.process(xarr, "time", chunk_size)
        out = np.concatenate([x.data for x in out])
        assert np.allclose(result_chunks.data, result_direct.data)
        assert np.allclose(out, result_direct.data)
        