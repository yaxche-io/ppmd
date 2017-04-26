__author__ = "W.R.Saunders"
__copyright__ = "Copyright 2016, W.R.Saunders"
__license__ = "GPL"

# system level
from mpi4py import MPI
import sys
import ctypes as ct
import numpy as np
import atexit
import Queue

#package level
import compiler


if not MPI.Is_initialized():
    MPI.Init()


# priority queue for module cleanup.
_CLEANUP_QUEUE = Queue.PriorityQueue()
_CLEANUP_QUEUE.put((50, MPI.Finalize))

def _atexit_queue():
    while not _CLEANUP_QUEUE.empty():
        item = _CLEANUP_QUEUE.get()
        item[1]()


atexit.register(_atexit_queue)




mpi_map = {ct.c_double: MPI.DOUBLE, ct.c_int: MPI.INT, int: MPI.INT}

recv_modifiers = [
    [-1, -1, -1],  # 0
    [0, -1, -1],  # 1
    [1, -1, -1],  # 2
    [-1, 0, -1],  # 3
    [0, 0, -1],  # 4
    [1, 0, -1],  # 5
    [-1, 1, -1],  # 6
    [0, 1, -1],  # 7
    [1, 1, -1],  # 8

    [-1, -1, 0],  # 9
    [0, -1, 0],  # 10
    [1, -1, 0],  # 11
    [-1, 0, 0],  # 12
    [1, 0, 0],  # 13
    [-1, 1, 0],  # 14
    [0, 1, 0],  # 15
    [1, 1, 0],  # 16

    [-1, -1, 1],  # 17
    [0, -1, 1],  # 18
    [1, -1, 1],  # 19
    [-1, 0, 1],  # 20
    [0, 0, 1],  # 21
    [1, 0, 1],  # 22
    [-1, 1, 1],  # 23
    [0, 1, 1],  # 24
    [1, 1, 1],  # 25
]

tuple_to_direction = {}
for idx, dir in enumerate(recv_modifiers):
    tuple_to_direction[str(dir)] = idx

def enum(**enums):
    return type('Enum', (), enums)

decomposition = enum(spatial=0, particle=1)

# default to spatial decomposition
decomposition_method = decomposition.spatial

Status = MPI.Status


def all_reduce(array):
    rarr = np.zeros_like(array)
    MPI.COMM_WORLD.Allreduce(
        array,
        rarr
    )
    return rarr

###############################################################################
# shared memory mpi handle
###############################################################################

class MPISHM(object):
    """
    This class controls two mpi communicators (assuming MPI3 or higher). 

    The first communicator from:
        MPI_Comm_split_type(..., MPI_COMM_TYPE_SHARED,...).
    
    The second a communicator between rank 0 of the shared memory regions.
    """

    def __init__(self):
        self.init = False
        self.inter_comm = None
        self.intra_comm = None

    def _init_comms(self):
        """
        Initialise the communicators.
        """

        if not self.init:
            assert MPI.VERSION >= 3, "MPI ERROR: mpi4py is not built against"\
                + " a MPI3 or higher MPI distribution."

            self.intra_comm = MPI.COMM_WORLD.Split_type(MPI.COMM_TYPE_SHARED)

            if self.intra_comm.Get_rank() == 0:
                colour = 0
            else:
                colour = MPI.UNDEFINED

            self.inter_comm = MPI.COMM_WORLD.Split(color=colour)

            self.init = True

    def _print_comm_info(self):
        self._init_comms()
        print self.intra_comm.Get_rank(), self.intra_comm.Get_size()
        if self.intra_comm.Get_rank() == 0:
            print self.inter_comm.Get_rank(), self.inter_comm.Get_size()

    def get_intra_comm(self):
        """
        get communicator for shared memory region.
        """
        self._init_comms()
        return self.intra_comm

    def get_inter_comm(self):
        """
        get communicator between shared memory regions.
        """
        self._init_comms()
        if self.intra_comm.Get_rank() != 0:
            print "warning this MPI comm is undefined on this rank"
        return self.inter_comm

###############################################################################
# shared memory default
###############################################################################

SHMMPI_HANDLE = MPISHM()


###############################################################################
# shared memory mpi handle
###############################################################################



class SHMWIN(object):
    """
    Create a shared memory window in each shared memory region
    """
    def __init__(self, size=None, intracomm=None):
        """
        Allocate a shared memory region.
        :param size: Number of bytes per process.
        :param intracomm: Intracomm to use.
        """
        assert size is not None, "No size passed"
        assert intracomm is not None, "No intracomm passed"
        self._swin = MPI.Win()
        """temp window object."""
        self.win = self._swin.Allocate_shared(size=size, comm=intracomm)
        """Win instance with shared memory allocated"""

        assert self.win.model == MPI.WIN_UNIFIED, "Memory model is not MPI_WIN_UNIFIED"

        self.size = size
        """Size in allocated per process in intercomm"""
        self.intercomm = intracomm
        """Intercomm for RMA shared memory window"""
        self.base = ct.c_void_p(self.win.Get_attr(MPI.WIN_BASE))
        """base pointer for calling rank in shared memory window"""


    def _test(self):
        lib = ct.cdll.LoadLibrary("/home/wrs20/md_workspace/test1.so")

        self.win.Fence()
        MPI.COMM_WORLD.Barrier()

        ptr = ct.c_void_p(self.win.Get_attr(MPI.WIN_BASE))

###############################################################################
# MPI_HANDLE
###############################################################################

def print_str_on_0(comm, *args):
    """
    Method to print on rank 0 to stdout
    """

    if comm.Get_rank() == 0:
        _s = ''
        for ix in args:
            _s += str(ix) + ' '
        print _s
        sys.stdout.flush()

    comm.Barrier()

###############################################################################
# cartcomm functions
###############################################################################


def create_cartcomm(comm, dims, periods, reorder_flag):
    """
    Create an mpi cart on the current comm
    """
    COMM = comm.Create_cart(dims, periods, reorder_flag)
    return COMM


def cartcomm_get_move_send_recv_ranks(comm):

    send_ranks = range(26)
    recv_ranks = range(26)

    for ix in range(26):
        direction = recv_modifiers[ix]
        send_ranks[ix] = cartcomm_shift(comm, direction, ignore_periods=True)
        recv_ranks[ix] = cartcomm_shift(comm,
                                        (-1 * direction[0],
                                        -1 * direction[1],
                                        -1 * direction[2]),
                                        ignore_periods=True)
    return send_ranks, recv_ranks




def cartcomm_shift(comm, offset=(0, 0, 0), ignore_periods=False):
    """
    Returns rank of process found at a given offset, will return -1 if no process exists.

    :arg tuple offset: 3-tuple offset from current process.
    """

    if type(offset) is int:
        offset = recv_modifiers[offset]

    _top = comm.Get_topo()[2][::-1]
    _per = comm.Get_topo()[1][::-1]
    _dims = comm.Get_topo()[0][::-1]

    _x = _top[0] + offset[0]
    _y = _top[1] + offset[1]
    _z = _top[2] + offset[2]

    _r = [_x % _dims[0], _y % _dims[1], _z % _dims[2]]

    if not ignore_periods:

        if (_r[0] != _x) and _per[0] == 0:
            return -1
        if (_r[1] != _y) and _per[1] == 0:
            return -1
        if (_r[2] != _z) and _per[2] == 0:
            return -1

    return _r[0] + _r[1] * _dims[0] + _r[2] * _dims[0] * _dims[1]


def cartcomm_top(comm):
    """
    Return the current topology.
    """
    if comm is not None:
        return comm.Get_topo()[2][::-1]
    else:
        return 0, 0, 0

def cartcomm_dims(comm):
    """
    Return the current dimensions.
    """
    if comm is not None:
        return comm.Get_topo()[0][::-1]
    else:
        return 1, 1, 1

def cartcomm_periods(comm):
    """
    Return the current periods.
    """
    if comm is not None:
        return comm.Get_topo()[1][::-1]
    else:
        return 1,1,1