from mpi4py import MPI
import sys
import ctypes as ct

mpi_map = {ct.c_double: MPI.DOUBLE, ct.c_int: MPI.INT}

###############################################################################################################
# MDMPI
###############################################################################################################

class MDMPI(object):
    """
    Class to store a MPI communicator such that it can be used everywhere (bottom level of hierarchy).
    """
    def __init__(self):
        self._COMM = MPI.COMM_WORLD
        self._p = (0, 0, 0)

    @property
    def comm(self):
        """
        Return the current communicator.
        """
        return self._COMM

    @comm.setter
    def comm(self, new_comm=None):
        """
        Set the current communicator.
        """
        assert new_comm is not None, "MDMPI error: no new communicator assigned."
        self._COMM = new_comm

    def __call__(self):
        """
        Return the current communicator.
        """
        return self._COMM

    @property
    def rank(self):
        """
        Return the current rank.
        """
        if self._COMM is not None:
            return self._COMM.Get_rank()
        else:
            return 0

    @property
    def nproc(self):
        """
        Return the current size.
        """
        if self._COMM is not None:
            return self._COMM.Get_size()
        else:
            return 1

    @property
    def top(self):
        """
        Return the current topology.
        """
        if self._COMM is not None:
            return self._COMM.Get_topo()[2][::-1]
        else:
            return 0, 0, 0

    @property
    def dims(self):
        """
        Return the current dimensions.
        """
        if self._COMM is not None:
            return self._COMM.Get_topo()[0][::-1]
        else:
            return 1, 1, 1

    @property
    def periods(self):
        """
        Return the current periods.
        """
        if self._COMM is not None:
            return self._COMM.Get_topo()[1][::-1]
        else:
            return self._p

    def set_periods(self, p=None):
        """
        set periods (if for some reason mpi4py does not set these this prives a soln.
        """
        assert p is not None, "Error no periods passed"
        self._p = p

    def barrier(self):
        """
        alias to comm barrier method.
        """

        # MPI.COMM_WORLD.Barrier()
        if self._COMM is not None:
            self._COMM.Barrier()


    def print_str(self, *args):
        """
        Method to print on rank 0 to stdout
        """

        if self.rank == 0:
            _s = ''
            for ix in args:
                _s += str(ix)+ ' '
            print _s
            sys.stdout.flush()

        self.barrier()

    def _check_comm(self):
        self._top = self._COMM.Get_topo()[2][::-1]
        self._per = self._COMM.Get_topo()[1][::-1]
        self._dims = self._COMM.Get_topo()[0][::-1]

    @property
    def query_boundary_exist(self):
        """
        Return for each direction:
        Flag if process is a boundary edge or interior edge 1 or 0.

        Xl 0, Xu 1
        Yl 2, Yu 3
        Zl 4, Zu 5

        """

        self._check_comm()

        _sf = range(6)
        for ix in range(3):
            if self._top[ix] == 0:
                _sf[2 * ix] = 1
            else:
                _sf[2 * ix] = 0
            if self._top[ix] == self._dims[ix] - 1:
                _sf[2 * ix + 1] = 1
            else:
                _sf[2 * ix + 1] = 0
        return _sf

    @property
    def query_halo_exist(self):
        """
        Return for each direction:
        Flag if process has a halo on each face.

        Xl 0, Xu 1
        Yl 2, Yu 3
        Zl 4, Zu 5

        """

        self._check_comm()

        _sf = range(6)
        for ix in range(3):
            if self._top[ix] == 0:
                _sf[2 * ix] = self._per[ix]
            else:
                _sf[2 * ix] = 1
            if self._top[ix] == self._dims[ix] - 1:
                _sf[2 * ix + 1] = self._per[ix]
            else:
                _sf[2 * ix + 1] = 1
        return _sf

    def shift(self, offset=(0, 0, 0)):
        """
        Returns rank of process found at a given offset, will return -1 if no process exists.
        """

        self._check_comm()

        _x = self._top[0] + offset[0]
        _y = self._top[1] + offset[1]
        _z = self._top[2] + offset[2]

        _r = [_x % self._dims[0], _y % self._dims[1], _z % self._dims[2]]

        if (_r[0] != _x) and self._per[0] == 0:
            return -1
        if (_r[1] != _y) and self._per[1] == 0:
            return -1
        if (_r[2] != _z) and self._per[2] == 0:
            return -1

        return _r[0] + _r[1] * self._dims[0] + _r[2] * self._dims[0] * self._dims[1]

###########################################################################################################
# MPI_HANDLE
###########################################################################################################

# Main MPI communicatior used by program.

MPI_HANDLE = MDMPI()
Status = MPI.Status