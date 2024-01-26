import h5py
import numpy as np

from ..database import Database
from ..virtual import DataSource


def read(fname):
    with h5py.File(fname, "r") as file:
        acquisition = file["Acquisition"]
        dx = acquisition.attrs["SpatialSamplingInterval"]
        rawdata = acquisition["Raw[0]"]["RawData"]
        t = rawdata.attrs["PartStartTime"]
        tstart = np.datetime64(rawdata.attrs["PartStartTime"][:-1])
        tend = np.datetime64(rawdata.attrs["PartEndTime"][:-1])
        data = DataSource(rawdata)
    nt, nd = data.shape
    time = {"tie_indices": [0, nt - 1], "tie_values": [tstart, tend]}
    distance = {"tie_indices": [0, nd - 1], "tie_values": [0.0, (nd - 1) * dx]}
    return Database(data, {"time": time, "distance": distance})
