from __future__ import print_function

import pytest
import ctypes
import numpy as np
import ppmd as md
import sys
np.set_printoptions(linewidth=200)

from ppmd.coulomb.octal import *

MPISIZE = md.mpi.MPI.COMM_WORLD.Get_size()
MPIRANK = md.mpi.MPI.COMM_WORLD.Get_rank()
MPIBARRIER = md.mpi.MPI.COMM_WORLD.Barrier


@pytest.fixture
def state():
    A = 1
    return A

class _fake_cartcomm(object):
    def __init__(self, dims):
        self.dims = dims

    def Get_topo(self):
        return (self.dims, self.dims, self.dims)

    def Get_cart_rank(self, index):
        lindex = sum(i*j for i,j in zip(index, self.dims))
        print(index, lindex)
        return lindex

    def Get_rank(self):
        return 0

@pytest.fixture(
    scope="module",
    params=(
            ((1,1,1), 1, ([0], [0], [0]), ([[0]], [[0]], [[0]])),
            ((2,2,2), 1, ([1], [1], [1]), ([[0, 1]], [[0, 1]], [[0, 1]])),
            ((3,3,3), 2, ([0,2], [0,2], [0,2]), ( [[0, 1],[1, 2]],
                                                  [[0, 1],[1, 2]],
                                                  [[0, 1],[1, 2]] )
            ),
            ((2,2,1), 2, ([0,1], [0,1], [0,0]), ( [[0],[1]],
                                                  [[0],[1]],
                                                  [[0],[0]] )
            )
    )
)
def fake_cartcomm(request):
    return request.param

@pytest.mark.skip('dev test')
def test_octal_cube_owner_map_1(fake_cartcomm):

    cc = _fake_cartcomm(fake_cartcomm[0])
    cube_count = fake_cartcomm[1]
    expected_owners = fake_cartcomm[2]
    expected_contribs = fake_cartcomm[3]

    o = cube_owner_map(cc, cube_count)

    owners, contribs, _, _ = o.compute_grid_ownership(
        cc.Get_topo()[0], cc.Get_topo()[2], cube_count)

    for ix, ox in enumerate(owners):
        assert ox == expected_owners[ix]
    for ix, ox in enumerate(contribs):
        assert ox == expected_contribs[ix]


@pytest.fixture(
    scope="module",
    params=(
            {
                'ncube': 1,
                'owners': (3,),
                'starts': {
                    0: [0, 3],
                    1: [0, 0],
                    2: [0, 0],
                    3: [0, 0]
                },
                'contribs': {
                    0: [1, 2, 3],
                    1: [],
                    2: [],
                    3: []
                },
                'sends': {
                    0: [-1],
                    1: [0],
                    2: [0],
                    3: [0]
                },
            },
            {
                'ncube': 3,
                'owners': (0, 0, 1, 0, 0, 1, 2, 2, 3,
                           0, 0, 1, 0, 0, 1, 2, 2, 3,
                           0, 0, 1, 0, 0, 1, 2, 2, 3),
                'starts': {
                    3: [0]*28,
                    2: [0]*8 + [1]*9 + [2]*9 + [3, 3],
                    1: [0]*6 + [1]*9 + [2]*9 + [3]*4,
                    0: [0]*2 + [1]*2 + [2] + [5] * 6 + [6, 6, 7] + [10] * 6 + \
                       [11, 11, 12] + [15] * 5
                },
                'contribs': {
                    0: [1, 2, 1, 2, 3] * 3,
                    1: [3, 3, 3],
                    2: [3, 3, 3],
                    3: []
                },
                'sends': {
                    0: [-1] * 27,
                    1: [-1, 0, -1, -1, 0, -1, -1, -1, -1] * 3,
                    2: [-1, -1, -1, 0, 0, -1, -1, -1, -1] * 3,
                    3: [-1, -1, -1, -1, 0, 1, -1, 2, -1] * 3
                },
            },
    )
)
def cube_size(request):
    return request.param

DEBUG = False

@pytest.mark.skipif("MPISIZE != 4")
def test_octal_cube_owner_map_2(cube_size):

    ncube = cube_size['ncube']
    dims = md.mpi.MPI.Compute_dims(MPISIZE, 3)

    if MPIRANK == 0 and DEBUG:
        print("DIMS", dims[::-1])

    cc = md.mpi.create_cartcomm(
        md.mpi.MPI.COMM_WORLD, dims[::-1], (1,1,1), True)

    o = cube_owner_map(cc, ncube)
    owners, contribs, _, _ = o.compute_grid_ownership(
        cc.Get_topo()[0], cc.Get_topo()[2], ncube)

    for rx in range(cc.Get_size()):
        if MPIRANK == rx and DEBUG:
            print(MPIRANK, "owners | contribs", owners, "|", contribs)
        md.mpi.MPI.COMM_WORLD.Barrier()

    cube_to_mpi = o.compute_map_product_owners(cc, owners)

    for rx in range(cc.Get_size()):
        if MPIRANK == rx and DEBUG:
            print(MPIRANK, "cube_to_mpi", cube_to_mpi)
        md.mpi.MPI.COMM_WORLD.Barrier()

    starts, con_ranks, send_ranks = o.compute_map_product_contribs(
        cc, cube_to_mpi, contribs)

    for rx in range(cc.Get_size()):
        if MPIRANK == rx and DEBUG:
            print(MPIRANK, starts, con_ranks, send_ranks)
        md.mpi.MPI.COMM_WORLD.Barrier()

    for i, ix in enumerate(send_ranks):
        assert ix == cube_size['sends'][MPIRANK][i], "{}|{}|{}:{}".format(
            MPIRANK, ix, i, cube_size['sends'][MPIRANK])
    for i, ix in enumerate(con_ranks):
        assert ix == cube_size['contribs'][MPIRANK][i]
    for i, ix in enumerate(starts):
        assert ix == cube_size['starts'][MPIRANK][i]


@pytest.fixture(
    scope="module",
    params=(
            {
                'ncube': 2,
                'owners': (3,),
                'starts': {
                    0: [0, 0, 1, 2, 3, 3, 4, 5, 6],
                    1: [0]*9,
                    2: [0]*9,
                    3: [0]*9
                },
                'contribs': {
                    0: [1, 2, 3, 1, 2, 3],
                    1: [],
                    2: [],
                    3: []
                },
                'sends': {
                    0: [-1, -1, -1, -1, -1, -1, -1, -1],
                    1: [-1, 0, -1, -1, -1, 0, -1, -1],
                    2: [-1, -1, 0, -1, -1, -1, 0, -1],
                    3: [-1, -1, -1, 0, -1, -1, -1, 0]
                },
            },
    )
)
def cube_size2(request):
    return request.param

@pytest.mark.skipif("MPISIZE != 4")
def test_octal_cube_owner_map_3(cube_size2):

    ncube = cube_size2['ncube']
    dims = md.mpi.MPI.Compute_dims(MPISIZE, 3)

    if MPIRANK == 0 and DEBUG:
        print("DIMS", dims[::-1])

    cc = md.mpi.create_cartcomm(
        md.mpi.MPI.COMM_WORLD, dims[::-1], (1,1,1), True)

    o = cube_owner_map(cc, ncube, True)
    owners, contribs, _, _ = o.compute_grid_ownership(
        cc.Get_topo()[0], cc.Get_topo()[2], ncube, True)

    for rx in range(cc.Get_size()):
        if MPIRANK == rx and DEBUG:
            print(MPIRANK, "owners | contribs", owners, "|", contribs)
        md.mpi.MPI.COMM_WORLD.Barrier()

    cube_to_mpi = o.compute_map_product_owners(cc, owners)

    for rx in range(cc.Get_size()):
        if MPIRANK == rx and DEBUG:
            print(MPIRANK, "cube_to_mpi", cube_to_mpi)
        md.mpi.MPI.COMM_WORLD.Barrier()

    starts, con_ranks, send_ranks = o.compute_map_product_contribs(
        cc, cube_to_mpi, contribs)

    for rx in range(cc.Get_size()):
        if MPIRANK == rx and DEBUG:
            print(MPIRANK, starts, con_ranks, send_ranks)
        md.mpi.MPI.COMM_WORLD.Barrier()

    for i, ix in enumerate(starts):
        assert ix == cube_size2['starts'][MPIRANK][i]
    for i, ix in enumerate(con_ranks):
        assert ix == cube_size2['contribs'][MPIRANK][i]
    for i, ix in enumerate(send_ranks):
        assert ix == cube_size2['sends'][MPIRANK][i], "{}|{}|{}:{}".format(
            MPIRANK, ix, i, cube_size2['sends'][MPIRANK])





@pytest.mark.skip
def test_octal_grid_level_1():
    level = 2
    dims = md.mpi.MPI.Compute_dims(MPISIZE, 3)

    if MPIRANK == 0 and DEBUG:
        print("DIMS", dims[::-1])

    cc = md.mpi.create_cartcomm(
        md.mpi.MPI.COMM_WORLD, dims[::-1], (1,1,1), True)

    grid_level = OctalGridLevel(level=level, parent_comm=cc)
    print('--')
    print(MPIRANK, grid_level.owners)

    # print(MPIRANK, 'new_comm', grid_level.new_comm)
    # print(MPIRANK, 'local_cube_size', grid_level.local_grid_cube_size)
    # print(MPIRANK, 'local_offset', grid_level.local_grid_offset)
    # print(MPIRANK, 'local_size_halo', grid_level.grid_cube_size)

@pytest.mark.skip
def test_octal_tree_1():
    dims = md.mpi.MPI.Compute_dims(MPISIZE, 3)

    nlevels = 6

    if MPIRANK == 0 and DEBUG:
        print("DIMS", dims[::-1])

    cc = md.mpi.create_cartcomm(
        md.mpi.MPI.COMM_WORLD, dims[::-1], (1,1,1), True)

    tree = OctalTree(num_levels=nlevels, cart_comm=cc)
    if MPIRANK == 0:
        print(40*'-')
    for rx in range(MPISIZE):
        if rx == MPIRANK:
            print('RANK:', MPIRANK)
            for li, lx in enumerate(tree.levels):
                print(li, lx.local_grid_cube_size, lx.grid_cube_size,
                      lx.parent_local_size)
            print(40*'-')
        MPIBARRIER()

@pytest.mark.skip
def test_octal_data_tree_1():
    dims = md.mpi.MPI.Compute_dims(MPISIZE, 3)

    nlevels = 4

    if MPIRANK == 0 and DEBUG:
        print("DIMS", dims[::-1])

    cc = md.mpi.create_cartcomm(
        md.mpi.MPI.COMM_WORLD, dims[::-1], (1,1,1), True)

    tree = OctalTree(num_levels=nlevels, cart_comm=cc)

    datatree = OctalDataTree(tree=tree, ncomp=1, mode='plain')

    if MPIRANK == 0:
        print(40*'-')
    for rx in range(MPISIZE):
        if rx == MPIRANK:
            print('RANK:', MPIRANK)
            for li, lx in enumerate(tree.levels):
                print(li)
                print(lx.local_grid_cube_size, '\n', datatree.data[li].shape)
            print(40*'-')
            sys.stdout.flush()
        MPIBARRIER()

    if MPIRANK == 0:
        print(80*'=')
        sys.stdout.flush()

    datatreehalo = OctalDataTree(tree=tree, ncomp=1, mode='halo',
                                 dtype=ctypes.c_int)

    if MPIRANK == 0:
        print(40*'-')
    for rx in range(MPISIZE):
        if rx == MPIRANK:
            print('RANK:', MPIRANK)
            for li, lx in enumerate(tree.levels):
                print(li, lx.grid_cube_size, '\n', datatreehalo.data[li].shape)
            print(40*'-')
            sys.stdout.flush()
        MPIBARRIER()


    test_level = 3
    arr = datatreehalo[test_level][2:-2:, 2:-2:, 2:-2:].view()
    harr = datatreehalo[test_level].view()

    #rng = np.random.RandomState(seed=3857293)
    #arr[:] = rng.uniform(MPIRANK, MPIRANK+1, size=arr.shape)

    #arr[:] = np.random.uniform(MPIRANK, MPIRANK+1, size=arr.shape)
    arr[:] = MPIRANK + 1

    if MPIRANK == 0:
        print(40*'-')
    for rx in range(MPISIZE):
        if rx == MPIRANK:
            print('RANK:', MPIRANK, arr.shape)
            print(harr[:,:,:,0])
            print(40*'-')
            sys.stdout.flush()
        MPIBARRIER()

    datatreehalo.halo_exchange_level(test_level)

    if MPIRANK == 0:
        print(40*'-')
    for rx in range(MPISIZE):
        if rx == MPIRANK:
            print('RANK:', MPIRANK)
            print(harr[:,:,:,0])
            print(40*'-')
            sys.stdout.flush()
        MPIBARRIER()

@pytest.mark.skip
def test_octal_data_tree_2():
    dims = md.mpi.MPI.Compute_dims(MPISIZE, 3)

    nlevels = 4

    if MPIRANK == 0 and DEBUG:
        print("DIMS", dims[::-1])

    cc = md.mpi.create_cartcomm(
        md.mpi.MPI.COMM_WORLD, dims[::-1], (1,1,1), True)

    tree = OctalTree(num_levels=nlevels, cart_comm=cc)

    datatree = OctalDataTree(tree=tree, ncomp=1, mode='parent')

    if MPIRANK == 0:
        print(40*'-')
    for rx in range(MPISIZE):
        if rx == MPIRANK:
            print('RANK:', MPIRANK)
            for li, lx in enumerate(tree.levels):
                print(li)
                #print(lx.local_grid_cube_size, '\n', datatree.data[li].shape)
            print("nbytes", datatree.nbytes)
            print(40*'-')
            sys.stdout.flush()
        MPIBARRIER()


@pytest.mark.skip
def test_octal_data_tree_3():
    dims = md.mpi.MPI.Compute_dims(MPISIZE, 3)

    nlevels = 4

    if MPIRANK == 0 and DEBUG:
        print("DIMS", dims[::-1])

    cc = md.mpi.create_cartcomm(
        md.mpi.MPI.COMM_WORLD, dims[::-1], (1,1,1), True)

    tree = OctalTree(num_levels=nlevels, cart_comm=cc)

    if MPIRANK == 0:
        print(40*'-')
    for rx in range(MPISIZE):
        if rx == MPIRANK:
            print('RANK:', MPIRANK)
            print(tree.nbytes)
            print(40*'-')
            sys.stdout.flush()
        MPIBARRIER()

@pytest.mark.skip
def test_octal_data_tree_4():
    dims = md.mpi.MPI.Compute_dims(MPISIZE, 3)

    nlevels = 4
    ncomp = 1


    if MPIRANK == 0 and DEBUG:
        print("DIMS", dims[::-1])

    cc = md.mpi.create_cartcomm(
        md.mpi.MPI.COMM_WORLD, dims[::-1], (1,1,1), True)

    tree = OctalTree(num_levels=nlevels, cart_comm=cc)
    dataparent = OctalDataTree(tree=tree, ncomp=ncomp, mode='parent',
                               dtype=ctypes.c_int)
    datahalo = OctalDataTree(tree=tree, ncomp=ncomp, mode='halo',
                             dtype=ctypes.c_int)

    src_level = 2
    dataparent[src_level].ravel()[:] = MPIRANK+1
    print(dataparent[src_level][:,:,:,0])
    send_parent_to_halo(src_level, dataparent, datahalo)

    if MPIRANK == 0:
        print(80*'=')
        #print(datahalo[1][2:-2:, 2:-2:, 2:-2:, 0])
        print(datahalo[src_level - 1][:, :, : , 0])
    MPIBARRIER()



def test_octal_data_tree_5():
    dims = md.mpi.MPI.Compute_dims(MPISIZE, 3)

    nlevels = 6
    ncomp = 10

    cc = md.mpi.create_cartcomm(
        md.mpi.MPI.COMM_WORLD, dims[::-1], (1,1,1), True)

    tree = OctalTree(num_levels=nlevels, cart_comm=cc)

    dataparent = OctalDataTree(tree=tree, ncomp=ncomp, mode='parent',
                               dtype=ctypes.c_int)
    datahalo = OctalDataTree(tree=tree, ncomp=ncomp, mode='halo',
                             dtype=ctypes.c_int)

    if tree[nlevels-1].local_grid_cube_size is not None:
        datahalo[nlevels-1][2:-2:, 2:-2:, 2:-2, :] = np.arange(1, ncomp+1)
        #print(datahalo[nlevels-1][:,:,:,1])

    tsum = np.zeros(ncomp, dtype=ctypes.c_int)

    for ix in range(nlevels-1, 0, -1):
        lsize = tree[ix].parent_local_size

        if lsize is not None:
            for kz in range(lsize[0]):
                for ky in range(lsize[1]):
                    for kx in range(lsize[2]):
                        X = 2*kx + 2
                        Y = 2*ky + 2
                        Z = 2*kz + 2
                        tsum[:] = 0
                        tsum += datahalo[ix][Z,   Y,   X, :]
                        tsum += datahalo[ix][Z,   Y,   X+1, :]
                        tsum += datahalo[ix][Z,   Y+1, X, :]
                        tsum += datahalo[ix][Z,   Y+1, X+1, :]
                        tsum += datahalo[ix][Z+1, Y,   X, :]
                        tsum += datahalo[ix][Z+1, Y,   X+1, :]
                        tsum += datahalo[ix][Z+1, Y+1, X, :]
                        tsum += datahalo[ix][Z+1, Y+1, X+1, :]
                        dataparent[ix][kz, ky, kx, :] += tsum[:]

        send_parent_to_halo(ix, dataparent, datahalo)

    if MPIRANK == 0:
        #print("ANS", datahalo[0][2,2,2,:])
        for ix in range(ncomp):
            assert datahalo[0][2,2,2,ix] == 8**(nlevels-1) * (ix+1)



def test_entry_data_1():
    dims = md.mpi.MPI.Compute_dims(MPISIZE, 3)

    nlevels = 3
    ncomp = 1
    dtype = ctypes.c_int

    cc = md.mpi.create_cartcomm(
        md.mpi.MPI.COMM_WORLD, dims[::-1], (1,1,1), True)

    tree = OctalTree(num_levels=nlevels, cart_comm=cc)
    datahalo = OctalDataTree(tree=tree, ncomp=ncomp, mode='halo',
                             dtype=dtype)
    entrydata = EntryData(tree, ncomp, dtype)

    if MPIRANK == 0:
        print('\n', 40*'-')
    for rx in range(MPISIZE):
        if rx == MPIRANK:
            print(MPIRANK, entrydata.local_size, entrydata.local_offset)
            sys.stdout.flush()
        MPIBARRIER()


    entrydata[:] = MPIRANK + 1
    entrydata.push_onto(datahalo)


    if MPIRANK == 0:
        print(40*'-')
    for rx in range(MPISIZE):
        if rx == MPIRANK:
            if datahalo.num_data[-1] > 0:
                print(MPIRANK, entrydata[:,:,:,0], datahalo[-1][:,:,:,0])
                sys.stdout.flush()
        MPIBARRIER()









