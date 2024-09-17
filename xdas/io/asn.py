import json

import h5py
import numpy as np
import zmq

from xdas.core.coordinates import get_sampling_interval

from ..core.dataarray import DataArray
from ..virtual import VirtualSource


def read(fname):
    with h5py.File(fname, "r") as file:
        header = file["header"]
        t0 = np.datetime64(round(header["time"][()] * 1e9), "ns")
        dt = np.timedelta64(round(1e9 * header["dt"][()]), "ns")
        dx = header["dx"][()] * np.median(np.diff(header["channels"]))
        data = VirtualSource(file["data"])
    nt, nx = data.shape
    time = {"tie_indices": [0, nt - 1], "tie_values": [t0, t0 + (nt - 1) * dt]}
    distance = {"tie_indices": [0, nx - 1], "tie_values": [0.0, (nx - 1) * dx]}
    return DataArray(data, {"time": time, "distance": distance})


class ZMQSubscriber:
    def __init__(self, address):
        """
        Initializes a ZMQStream object.

        Parameters
        ----------
        address : str
            The address to connect to.
        """
        self.address = address
        self._connect(self.address)
        message = self._get_message()
        self._update_header(message)

    def __iter__(self):
        return self

    def __next__(self):
        message = self._get_message()
        if not self._is_packet(message):
            self._update_header(message)
            return self.__next__()
        else:
            return self._unpack(message)

    def _connect(self, address):
        context = zmq.Context()
        socket = context.socket(zmq.SUB)
        socket.connect(address)
        socket.setsockopt_string(zmq.SUBSCRIBE, "")
        self._socket = socket

    def _get_message(self):
        return self._socket.recv()

    def _is_packet(self, message):
        return len(message) == self.packet_size

    def _update_header(self, message):
        header = json.loads(message.decode("utf-8"))
        self.packet_size = 8 + header["bytesPerPackage"] * header["nPackagesPerMessage"]
        self.shape = (header["nPackagesPerMessage"], header["nChannels"])
        self.dtype = np.float32 if header["dataType"] == "float" else np.int16
        roiTable = header["roiTable"][0]
        di = roiTable["roiStart"] * header["dx"]
        de = roiTable["roiEnd"] * header["dx"]
        self.distance = {
            "tie_indices": [0, header["nChannels"] - 1],
            "tie_values": [di, de],
        }
        self.delta = float_to_timedelta(header["dt"], header["dtUnit"])

    def _unpack(self, message):
        t0 = np.frombuffer(message[:8], "datetime64[ns]").reshape(())
        data = np.frombuffer(message[8:], self.dtype).reshape(self.shape)
        time = {
            "tie_indices": [0, self.shape[0] - 1],
            "tie_values": [t0, t0 + (self.shape[0] - 1) * self.delta],
        }
        return DataArray(data, {"time": time, "distance": self.distance})


class ZMQPublisher:
    """
    A class to stream data using ZeroMQ.

    Parameters
    ----------
    address : str
        The address to bind the ZeroMQ socket.

    Attributes
    ----------
    address : str
        The address where the ZeroMQ is bound to.

    Methods
    -------
    submit(da)
        Submits the data array for publishing.

    Examples
    --------
    >>> import xdas as xd
    >>> from xdas.io.asn import ZMQPublisher

    >>> da = xd.synthetics.randn_wavefronts()

    >>> port = xd.io.get_free_port()
    >>> address = f"tcp://localhost:{port}"
    >>> publisher = ZMQPublisher(address)
    >>> chunks = xd.split(da, 10)
    >>> for chunk in chunks:
    ...     publisher.submit(chunk)

    """

    def __init__(self, address):
        self.address = address
        self._connect(address)
        self._header = None

    @property
    def header(self):
        return self._header

    @header.setter
    def header(self, header):
        self._header = header
        self.socket.setsockopt(zmq.XPUB_WELCOME_MSG, json.dumps(header).encode("utf-8"))

    def submit(self, da):
        self._send(da)

    def write(self, da):
        self._send(da)

    def _connect(self, address):
        context = zmq.Context()
        socket = context.socket(zmq.XPUB)
        socket.setsockopt(zmq.XPUB_VERBOSE, True)
        socket.bind(address)
        self.socket = socket

    @staticmethod
    def _get_header(da):
        da = da.transpose("time", "distance")
        header = {
            "bytesPerPackage": da.dtype.itemsize * da.shape[1],
            "nPackagesPerMessage": da.shape[0],
            "nChannels": da.shape[1],
            "dataType": "float" if da.dtype == np.float32 else "short",
            "dx": get_sampling_interval(da, "distance"),
            "dt": get_sampling_interval(da, "time"),
            "dtUnit": "s",
            "dxUnit": "m",
            "roiTable": [{"roiStart": 0, "roiEnd": da.shape[1] - 1, "roiDec": 1}],
        }
        return header

    def _send(self, da):
        da = da.transpose("time", "distance")
        header = self._get_header(da)
        if self.header is None:
            self.header = header
        if not header == self.header:
            self.header = header
            self._send_header()
        self._send_data(da)

    def _send_header(self):
        message = json.dumps(self.header).encode("utf-8")
        self._send_message(message)

    def _send_data(self, da):
        da = da.transpose("time", "distance")
        t0 = da["time"][0].values.astype("datetime64[ns]")
        data = da.values
        message = t0.tobytes() + data.tobytes()
        self._send_message(message)

    def _send_message(self, message):
        self.socket.send(message)


def float_to_timedelta(value, unit):
    """
    Converts a floating-point value to a timedelta object.

    Parameters
    ----------
    value : float
        The value to be converted.
    unit : str
        The unit of the value. Valid units are 'ns' (nanoseconds), 'us' (microseconds),
        'ms' (milliseconds), and 's' (seconds).

    Returns
    -------
    timedelta
        The converted timedelta object.

    Example
    -------
    >>> float_to_timedelta(1.5, 'ms')
    numpy.timedelta64(1500000,'ns')
    """
    conversion_factors = {
        "ns": 1e0,
        "us": 1e3,
        "ms": 1e6,
        "s": 1e9,
    }
    conversion_factor = conversion_factors[unit]
    return np.timedelta64(round(value * conversion_factor), "ns")
