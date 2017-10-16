__author__ = "W.R.Saunders"
__copyright__ = "Copyright 2016, W.R.Saunders"
__license__ = "GPL"

import scipy
from math import log, ceil
from ppmd.coulomb.octal import *
import numpy as np
from ppmd import runtime
from ppmd.lib import build
import ctypes
import os
import math
from scipy.special import sph_harm, lpmv

_SRC_DIR = os.path.dirname(os.path.realpath(__file__))

REAL = ctypes.c_double
UINT64 = ctypes.c_uint64
INT64 = ctypes.c_int64
INT32 = ctypes.c_int32

def _numpy_ptr(arr):
    return arr.ctypes.data_as(ctypes.c_void_p)

def _check_dtype(arr, dtype):
    if arr.dtype != dtype:
        raise RuntimeError('Bad data type. Expected: {} Found: {}.'.format(
            str(dtype), str(arr.dtype)))

class PyFMM(object):
    def __init__(self, domain, N, eps=10.**-6, shared_memory=False,
                 dtype=ctypes.c_double):

        self.L = int(-1*log(eps,2))
        """Number of multipole expansion coefficients"""
        self.R = int(ceil(log(N, 8)))
        """Number of levels in octal tree."""
        self.dtype = dtype
        """Floating point datatype used."""
        self.domain = domain


        ncomp = (self.L**2) * 2
        # define the octal tree and attach data to the tree.
        self.tree = OctalTree(self.R, domain.comm)
        self.tree_plain = OctalDataTree(self.tree, ncomp, 'plain', dtype)
        self.tree_halo = OctalDataTree(self.tree, ncomp, 'halo', dtype)
        self.tree_parent = OctalDataTree(self.tree, ncomp, 'parent', dtype)
        self.entry_data = EntryData(self.tree, ncomp, dtype)

        self._tcount = runtime.OMP_NUM_THREADS if runtime.OMP_NUM_THREADS is \
            not None else 1
        self._thread_allocation = np.zeros(1, dtype=INT32)

        # load contribution computation library
        with open(str(_SRC_DIR) + \
                          '/FMMSource/ParticleContribution.cpp') as fh:
            cpp = fh.read()
        with open(str(_SRC_DIR) + \
                          '/FMMSource/ParticleContribution.h') as fh:
            hpp = fh.read()
        self._contribution_lib = build.simple_lib_creator(hpp, cpp,
            'fmm_contrib')['particle_contribution']

        # pre compute A_n^m and 1/(A_n^m)
        self._a = np.zeros(shape=(self.L, self.L), dtype=dtype)
        self._ar = np.zeros(shape=(self.L, self.L), dtype=dtype)
        for lx in range(self.L):
            for mx in range(lx+1):
                a_l_m = ((-1.) ** lx)/math.sqrt(math.factorial(lx - mx) *\
                                                math.factorial(lx+mx))
                self._a[lx, mx] = a_l_m
                self._ar[lx, mx] = 1.0/a_l_m

        # As we have a "uniform" octal tree the values Y_l^m(\alpha, \beta)
        # can be pre-computed for the 8 children of a parent cell. Indexed
        # lexicographically.
        pi = math.pi
        alpha_beta = (
            (1.25 * pi, 0.75 * pi),
            (1.75 * pi, 0.75 * pi),
            (0.75 * pi, 0.75 * pi),
            (0.25 * pi, 0.75 * pi),
            (1.25 * pi, 0.25 * pi),
            (1.75 * pi, 0.25 * pi),
            (0.75 * pi, 0.25 * pi),
            (0.25 * pi, 0.25 * pi)
        )

        def re_lm(l,m): return (l**2) + l + m
        def im_lm(l,m): return (l**2) + l +  m + self.L**2

        self._yab = np.zeros(shape=(8, ncomp), dtype=dtype)
        for cx, child in enumerate(alpha_beta):
            for lx in range(self.L):
                mval = list(range(-1*lx, 1)) + list(range(1, lx+1))
                mxval = list(range(lx, -1, -1)) + list(range(1, lx+1))
                scipy_p = lpmv(mxval, lx, child[1])
                for mxi, mx in enumerate(mval):
                    val = math.sqrt(math.factorial(
                        lx - abs(mx))/math.factorial(lx + abs(mx)))
                    re_exp = np.cos(mx*child[0]) * val
                    im_exp = np.sin(mx*child[0]) * val

                    self._yab[cx, re_lm(lx, mx)] = scipy_p[mxi].real * re_exp
                    self._yab[cx, im_lm(lx, mx)] = scipy_p[mxi].imag * im_exp


    def _compute_cube_contrib(self, positions, charges):

        ns = self.tree.entry_map.cube_side_count
        cube_side_counts = np.array((ns, ns, ns), dtype=UINT64)
        if self._thread_allocation.size < self._tcount * \
                positions.npart_local + 1:
            self._thread_allocation = np.zeros(
                int(self._tcount*positions.npart_local*1.1 + 1),dtype=INT32)
        else:
            self._thread_allocation[:self._tcount:] = 0

        _check_dtype(positions, REAL)
        _check_dtype(charges, REAL)
        _check_dtype(self.domain.extent_internal, REAL)
        _check_dtype(self.entry_data.local_offset, UINT64)
        _check_dtype(self.entry_data.local_size, UINT64)
        _check_dtype(cube_side_counts, UINT64)
        _check_dtype(self.entry_data.data, REAL)
        _check_dtype(self._thread_allocation, INT32)

        err = self._contribution_lib(
            INT64(self.L),
            UINT64(positions.npart_local),
            INT32(self._tcount),
            positions.ctypes_data,
            charges.ctypes_data,
            self.domain.extent.ctypes_data,
            _numpy_ptr(self.entry_data.local_offset),
            _numpy_ptr(self.entry_data.local_size),
            _numpy_ptr(cube_side_counts),
            _numpy_ptr(self.entry_data.data),
            _numpy_ptr(self._thread_allocation)
        )
        if err < 0: raise RuntimeError('Negative return code: {}'.format(err))


    def _translate_m_to_m(self):
        pass














