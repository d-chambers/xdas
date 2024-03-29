import os
import tempfile
from tempfile import TemporaryDirectory

import numpy as np
import scipy.signal as sp

import xdas
import xdas.atoms as atoms
import xdas.signal as xp
from xdas.atoms import IIRFilter, PartialAtom, PartialStateAtom
from xdas.core import chunk, concatenate
from xdas.signal import lfilter
from xdas.synthetics import generate
from xdas.xarray import mean


class TestPartialAtom:
    def test_init(self):
        sequence = xdas.Sequential(
            [
                xdas.PartialAtom(xp.taper, dim="time"),
                xdas.PartialAtom(xp.taper, dim="distance"),
                xdas.PartialAtom(np.abs),
                xdas.PartialAtom(np.square),
            ]
        )


class TestProcessing:
    def test_sequence(self):
        # Generate a temporary dataset
        db = generate()

        # Declare sequence to execute
        sequence = xdas.Sequential(
            [
                xdas.PartialAtom(np.abs),
                xdas.PartialAtom(np.square, name="some square"),
                xdas.PartialAtom(mean, dim="time"),
            ]
        )

        # Sequence processing
        result1 = sequence(db)
        # Manual processing
        result2 = mean(np.abs(db) ** 2, dim="time")

        # Test
        assert np.allclose(result1.values, result2.values)


class TestDecorator:
    def test_decorator(self):
        a = [1, 1]
        b = [1, 1]
        atom = lfilter(b, a, ..., "time")
        statefull = lfilter(b, a, ..., "time", zi=...)
        assert isinstance(atom, PartialAtom)
        assert isinstance(statefull, PartialStateAtom)
        assert statefull.state == {"zi": "init"}


class TestFilters:
    def test_iirfilter(self):
        db = generate()
        chunks = chunk(db, 6, "time")

        sos = sp.iirfilter(4, 10.0, btype="lowpass", fs=50.0, output="sos")
        data = sp.sosfilt(sos, db.values, axis=0)
        expected = db.copy(data=data)

        atom = IIRFilter(4, 10.0, "lowpass", dim="time")
        monolithic = atom(db)

        atom = IIRFilter(4, 10.0, "lowpass", dim="time")
        chunked = concatenate([atom(chunk, chunk="time") for chunk in chunks], "time")

        assert monolithic.equals(expected)
        assert chunked.equals(expected)

        with TemporaryDirectory() as dirpath:
            path = os.path.join(dirpath, "state.nc")

            atom_a = IIRFilter(4, 10.0, "lowpass", dim="time")
            chunks_a = [atom_a(chunk, chunk="time") for chunk in chunks[:3]]
            atom_a.save_state(path)

            atom_b = IIRFilter(4, 10.0, "lowpass", dim="time")
            atom_b.load_state(path)
            chunks_b = [atom_b(chunk, chunk="time") for chunk in chunks[3:]]

            result = concatenate(chunks_a + chunks_b, "time")
            assert result.equals(expected)

    def test_downsample(self):
        db = generate()
        chunks = chunk(db, 6, "time")
        expected = db.isel(time=slice(None, None, 3))
        atom = atoms.DownSample(3, "time")
        result = atom(db)
        assert result.equals(expected)
        result = concatenate([atom(chunk, chunk="time") for chunk in chunks], "time")
        assert result.equals(expected)

    def test_upsample(self):
        db = generate()
        chunks = chunk(db, 6, "time")
        atom = atoms.UpSample(3, "time")
        expected = atom(db)
        result = concatenate([atom(chunk, chunk="time") for chunk in chunks], "time")
        assert result.equals(expected)
