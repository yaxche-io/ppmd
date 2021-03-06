from __future__ import division, print_function, absolute_import
__author__ = "W.R.Saunders"
__copyright__ = "Copyright 2016, W.R.Saunders"
__license__ = "GPL"

# system level
import ctypes
import numpy as np
import collections

# package level
from ppmd import access, runtime

from ppmd.lib.common import ctypes_map

int32 = ctypes.c_int32
int32_str = 'int'

int64 = ctypes.c_int64
int64_str = 'int64_t'

uint8_str = 'uint8_t'

long_str = 'long'

double = ctypes.c_double
double_str = 'double'




mpi_type_map = {ctypes.c_double: 'MPI_DOUBLE', ctypes.c_int: 'MPI_INT', ctypes.c_long: 'MPI_LONG'}

###############################################################################
# Get available memory.
###############################################################################
def available_free_memory():
    """
    Get available free memory in bytes.
    :return: Free memory in bytes.
    """
    try:
        with open('/proc/meminfo', 'r') as mem_info:
            mem_read = mem_info.readlines()

            _free = int(mem_read[1].split()[1])
            _buff = int(mem_read[2].split()[1])
            _cached = int(mem_read[3].split()[1])

            return (_free + _buff + _cached) * 1024
    except:
        return (2 ** 64) - 1


###############################################################################
# Pointer arithmetic for ctypes
###############################################################################


def pointer_offset(ptr=None, offset=0):
    """
    Add offset number of bytes to pointer ptr, returns ctypes void ptr
    :param ptr:     original pointer
    :param offset:  offset in bytes
    """

    vpv = ctypes.cast(ptr, ctypes.c_void_p).value
    vpv += offset
    return ctypes.c_void_p(vpv)

def _make_array(initial_value=None, dtype=None, nrow=None, ncol=None):
    """
    dat initialiser
    """

    if initial_value is not None:
        if type(initial_value) is np.ndarray:
            return _create_from_existing(initial_value, dtype)
        elif not isinstance(initial_value, collections.abc.Iterable):
            return _create_from_existing(np.array([initial_value],
                                                  dtype=dtype), dtype)
        else:
            return _create_from_existing(np.array(list(initial_value),
                                                  dtype=dtype), dtype)
    else:
        return _create_zeros(nrow=nrow, ncol=ncol, dtype=dtype)


def _create_zeros(nrow=None, ncol=None, dtype=ctypes.c_double):



    assert ncol is not None, "Make 1D arrays using ncol not nrow"
    if nrow is not None:
        return np.zeros([int(nrow), int(ncol)], dtype=dtype)
    else:
        return np.zeros(int(ncol), dtype=dtype)


def _create_from_existing(ndarray=None, dtype=None):
    if ndarray.dtype != dtype and dtype is not None:
        ndarray = ndarray.astype(dtype)

    return np.array(ndarray)



###############################################################################
# Array.
###############################################################################

class _Array(object):
    @property
    def ctypes_data(self):
        raise NotImplementedError
    def ctypes_data_access(self, mode=access.RW, pair=False):
        raise NotImplementedError
    def ctypes_data_post(self, mode=access.RW):
        raise NotImplementedError
    @property
    def ctype(self):
         raise NotImplementedError

class Array(_Array):
    """
    Basic dynamic memory array on host, with some methods.
    """
    def __init__(self, initial_value=None, name=None, ncomp=1, dtype=ctypes.c_double):
        """
        Creates scalar with given initial value.
        """

        self.idtype = dtype
        self.data = _make_array(initial_value=initial_value,
                                    dtype=dtype,
                                    ncol=ncomp)
        
        self._ptr = None
        self._ptr_count = 0
        self._ptr_id = 0

        self._version = 0
        self.name = name

    
    def _update_ptr(self):
        self._ptr = self.data.ctypes.get_as_parameter()
        # ids are only unique for the lifetime of the object, but his gives some
        # defense to the underlying array being swapped out under us.
        self._ptr_id = id(self.data)

    @property
    def ctype(self):
        return ctypes_map[self.dtype]

    @property
    def ncomp(self):
        return self.data.shape[0]

    @property
    def size(self):
        return self.data.shape[0] * ctypes.sizeof(self.dtype)

    @property
    def ctypes_data(self):

        if self._ptr is None:
            self._update_ptr()

        if self._ptr_count % 100 == 0:
            assert self._ptr.value == self.data.ctypes.get_as_parameter().value
        
        assert self._ptr_id == id(self.data)

        self._ptr_count += 1
        return self._ptr

    def ctypes_data_access(self, mode=access.RW, pair=False):
        if mode is access.INC0:
            self.zero()

        return self.ctypes_data

    def ctypes_data_post(self, mode=access.RW):
        pass

    def realloc(self, length):

        if length != self.ncomp:

            assert ctypes.sizeof(self.dtype) * length < available_free_memory(),\
                "host.Array realloc error: Not enough free memory. Requested: " +\
                str(ctypes.sizeof(self.dtype) * length) + " have: " +\
                str(available_free_memory())

            self.data = np.resize(self.data, length)
            self._ptr = None

    def zero(self):
        self.data.fill(0)

    @property
    def dtype(self):
        return self.idtype

    @property
    def end(self):
        """
        Returns end index of array.
        """
        return self.ncomp - 1

    @property
    def version(self):
        """
        Get the version of this array.
        :return int version:
        """
        return self._version

    def inc_version(self, inc=1):
        """
        Increment the version by the specified amount
        :param int inc: amount to increment version by.
        """
        self._version += int(inc)

    def __getitem__(self, ix):
        return self.data[ix]

    def __setitem__(self, ix, val):
        self.data[ix] = val

    def __len__(self):
        return self.ncomp



################################################################################################
# Matrix.
################################################################################################

class Matrix(object):
    """
    Basic dynamic memory matrix on host, with some methods.
    """
    def __init__(self, nrow=1, ncol=1, initial_value=None, dtype=ctypes.c_double):
        self.idtype = dtype

        self._dat = _make_array(initial_value=initial_value,
                                 dtype=dtype,
                                 nrow=nrow,
                                 ncol=ncol)

        self._version = 0

        self._ptr = None

    @property
    def version(self):
        """
        Get the version of this array.
        :return int version:
        """
        return self._version

    def inc_version(self, inc=1):
        """
        Increment the version by the specified amount
        :param int inc: amount to increment version by.
        """
        self._version += int(inc)

    @property
    def data(self):
        return self._dat

    @data.setter
    def data(self, value):
        self._dat = value
        self._ptr = None

    @property
    def nrow(self):
        return self.data.shape[0]

    @property
    def ncol(self):
        return self.data.shape[1]

    @property
    def size(self):
        return self._dat.nbytes
    @property
    def ctype(self):
        return ctypes_map[self.dtype]
    @property
    def ctypes_data(self):
        return self._dat.ctypes.data_as(ctypes.POINTER(self.dtype))

    def ctypes_data_access(self, mode=access.RW, pair=False):
        """
        :arg access mode: Access type required by the calling method.
        :return: The pointer to the data.
        """
        return self._dat.ctypes.data_as(ctypes.POINTER(self.dtype))

    def ctypes_data_post(self, mode=access.RW):
        pass

    def realloc(self, nrow, ncol):

        assert ctypes.sizeof(self.dtype) * nrow * ncol < available_free_memory(), "host.Matrix realloc error: Not enough free memory."


        if self.ncol != ncol or self.nrow != nrow:
            self._ptr = None
            self._dat = np.resize(self.data,[nrow, ncol])



    def zero(self):
        self.data.fill(self.idtype(0))

    @property
    def dtype(self):
        return self.idtype


###############################################################################
# Blank arrays/matrices
###############################################################################

NullIntArray = Array(dtype=ctypes.c_int)
NullDoubleArray = Array(dtype=ctypes.c_double)
NullByteArray = Array(dtype=ctypes.c_byte)
NullIntMatrix = Matrix(dtype=ctypes.c_int)
NullDoubleMatrix = Matrix(dtype=ctypes.c_double)

def null_matrix(dtype):
    """
    Return a Null*Matrix based on passed type.
    :param dtype: Data type of Null matrix.
    :return: Null Matrix.
    """

    if dtype is ctypes.c_double:
        return NullDoubleMatrix
    elif dtype is ctypes.c_int:
        return NullIntMatrix

###############################################################################
# tmp space for threading
###############################################################################

class ThreadSpace(object):
    def __init__(self, n, dtype):
        self.pointers = np.zeros(runtime.NUM_THREADS, dtype=ctypes.c_void_p)
        self.data = []
        self.n = n
        for nx in range(runtime.NUM_THREADS):
            self.data.append(np.zeros(n, dtype=dtype))
            self.pointers[nx] = self.data[-1].ctypes.get_as_parameter().value

    @property
    def ctypes_data(self):
        return self.pointers.ctypes.get_as_parameter()




