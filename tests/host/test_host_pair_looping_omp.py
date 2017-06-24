#!/usr/bin/python

import pytest
import ctypes
import numpy as np
import math


import ppmd as md

N = 1000
crN = 10 #cubert(N)
E = 8.

Eo2 = E/2.

tol = 10.**(-14)

rank = md.mpi.MPI.COMM_WORLD.Get_rank()
nproc = md.mpi.MPI.COMM_WORLD.Get_size()


PositionDat = md.data.PositionDat
ParticleDat = md.data.ParticleDat
ScalarArray = md.data.ScalarArray
GlobalArray = md.data.GlobalArray
State = md.state.State
PairLoop = md.pairloop.PairLoopNeighbourListNSOMP

@pytest.fixture
def state():
    A = State()
    A.npart = N
    A.domain = md.domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = md.domain.BoundaryTypePeriodic()

    A.p = PositionDat(ncomp=3)
    A.v = ParticleDat(ncomp=3)
    A.f = ParticleDat(ncomp=3)
    A.gid = ParticleDat(ncomp=1, dtype=ctypes.c_int)
    A.nc = ParticleDat(ncomp=1, dtype=ctypes.c_int)

    A.u = GlobalArray(ncomp=1)
    A.u.halo_aware = True

    return A

@pytest.fixture
def s_nd():
    """
    State with no domain, hence will not spatially decompose
    """
    A = State()
    A.npart = N
    A.p = PositionDat(ncomp=3)
    A.v = ParticleDat(ncomp=3)
    A.f = ParticleDat(ncomp=3)
    A.gid = ParticleDat(ncomp=1, dtype=ctypes.c_int)
    A.nc = ParticleDat(ncomp=1, dtype=ctypes.c_int)

    A.u = GlobalArray(ncomp=1)
    A.u.halo_aware = True

    return A

@pytest.fixture(scope="module", params=list({0, nproc-1}))
def base_rank(request):
    return request.param


def test_host_pair_loop_NS_1(state):
    """
    Set a cutoff slightly smaller than the smallest distance in the grid
    """
    cell_width = float(E)/float(crN)
    pi = np.zeros([N,3], dtype=ctypes.c_double)
    px = 0

    # This is upsetting....
    for ix in range(crN):
        for iy in range(crN):
            for iz in range(crN):
                pi[px,:] = (E/crN)*np.array([ix, iy, iz]) - 0.5*(E-E/crN)*np.ones(3)
                px += 1

    state.p[:] = pi
    state.npart_local = N
    state.filter_on_domain_boundary()


    kernel_code = '''
    NC(0,0)+=1;
    '''

    kernel = md.kernel.Kernel('test_host_pair_loop_1',code=kernel_code)
    kernel_map = {'P': state.p(md.access.R),
                  'NC': state.nc(md.access.W)}

    loop = PairLoop(kernel=kernel,
                                             dat_dict=kernel_map,
                                             shell_cutoff=cell_width-tol)

    state.nc.zero()

    loop.execute()
    for ix in range(state.npart_local):
        assert state.nc[ix] == 0



def test_host_pair_loop_NS_2(state):
    """
    Set a cutoff slightly larger than the smallest distance in the grid
    """
    cell_width = float(E)/float(crN)
    pi = np.zeros([N,3], dtype=ctypes.c_double)
    px = 0

    # This is upsetting....
    for ix in range(crN):
        for iy in range(crN):
            for iz in range(crN):
                pi[px,:] = (E/crN)*np.array([ix, iy, iz]) - 0.5*(E-E/crN)*np.ones(3)
                px += 1

    state.p[:] = pi
    state.npart_local = N
    state.filter_on_domain_boundary()


    kernel_code = '''
    NC(0,0)+=1;
    '''

    kernel = md.kernel.Kernel('test_host_pair_loop_1',code=kernel_code)
    kernel_map = {'P': state.p(md.access.R),
                  'NC': state.nc(md.access.W)}

    loop = PairLoop(kernel=kernel,
                                             dat_dict=kernel_map,
                                             shell_cutoff=cell_width+tol)

    state.nc.zero()

    loop.execute()
    for ix in range(state.npart_local):
        assert state.nc[ix] == 6


def test_host_pair_loop_NS_3(state):
    """
    Set a cutoff slightly smaller than the next nearest neighbour distance in
    the grid
    """
    cell_width = float(E)/float(crN)
    pi = np.zeros([N,3], dtype=ctypes.c_double)
    px = 0

    # This is upsetting....
    for ix in range(crN):
        for iy in range(crN):
            for iz in range(crN):
                pi[px,:] = (E/crN)*np.array([ix, iy, iz]) - 0.5*(E-E/crN)*np.ones(3)
                px += 1

    state.p[:] = pi
    state.npart_local = N
    state.filter_on_domain_boundary()


    kernel_code = '''
    NC(0,0)+=1;
    '''

    kernel = md.kernel.Kernel('test_host_pair_loop_1',code=kernel_code)
    kernel_map = {'P': state.p(md.access.R),
                  'NC': state.nc(md.access.W)}

    loop = PairLoop(kernel=kernel,
                                             dat_dict=kernel_map,
                                             shell_cutoff=math.sqrt(2.)*cell_width-tol)

    state.nc.zero()

    loop.execute()
    for ix in range(state.npart_local):
        assert state.nc[ix] == 6


def test_host_pair_loop_NS_4(state):
    """
    Set a cutoff slightly larger than the next nearest neighbour distance in
    the grid
    """
    cell_width = float(E)/float(crN)
    pi = np.zeros([N,3], dtype=ctypes.c_double)
    px = 0

    # This is upsetting....
    for ix in range(crN):
        for iy in range(crN):
            for iz in range(crN):
                pi[px,:] = (E/crN)*np.array([ix, iy, iz]) - 0.5*(E-E/crN)*np.ones(3)
                px += 1

    state.p[:] = pi
    state.npart_local = N
    state.filter_on_domain_boundary()


    kernel_code = '''
    NC(0,0)+=1;
    '''

    kernel = md.kernel.Kernel('test_host_pair_loop_1',code=kernel_code)
    kernel_map = {'P': state.p(md.access.R),
                  'NC': state.nc(md.access.W)}

    loop = PairLoop(kernel=kernel,
                                             dat_dict=kernel_map,
                                             shell_cutoff=math.sqrt(2.)*cell_width+tol)

    state.nc.zero()

    loop.execute()
    for ix in range(state.npart_local):
        assert state.nc[ix] == 18




def test_host_pair_loop_NS_5(state):
    """
    Set a cutoff slightly smaller than the 3rd nearest neighbour distance in
    the grid
    """
    cell_width = float(E)/float(crN)
    pi = np.zeros([N,3], dtype=ctypes.c_double)
    px = 0

    # This is upsetting....
    for ix in range(crN):
        for iy in range(crN):
            for iz in range(crN):
                pi[px,:] = (E/crN)*np.array([ix, iy, iz]) - 0.5*(E-E/crN)*np.ones(3)
                px += 1

    state.p[:] = pi
    state.npart_local = N
    state.filter_on_domain_boundary()


    kernel_code = '''
    NC(0,0)+=1;
    '''

    kernel = md.kernel.Kernel('test_host_pair_loop_1',code=kernel_code)
    kernel_map = {'P': state.p(md.access.R),
                  'NC': state.nc(md.access.W)}

    loop = PairLoop(kernel=kernel,
                                             dat_dict=kernel_map,
                                             shell_cutoff=math.sqrt(3.)*cell_width-tol)

    state.nc.zero()

    loop.execute()
    for ix in range(state.npart_local):
        assert state.nc[ix] == 18



def test_host_pair_loop_NS_6(state):
    """
    Set a cutoff slightly larger than the 3rd nearest neighbour distance in
    the grid
    """
    cell_width = float(E)/float(crN)
    pi = np.zeros([N,3], dtype=ctypes.c_double)
    px = 0

    # This is upsetting....
    for ix in range(crN):
        for iy in range(crN):
            for iz in range(crN):
                pi[px,:] = (E/crN)*np.array([ix, iy, iz]) - 0.5*(E-E/crN)*np.ones(3)
                px += 1

    state.p[:] = pi
    state.npart_local = N
    state.filter_on_domain_boundary()


    kernel_code = '''
    NC.i[0]+=1;
    '''

    kernel = md.kernel.Kernel('test_host_pair_loop_NS_1',code=kernel_code)
    kernel_map = {'P': state.p(md.access.R),
                  'NC': state.nc(md.access.W)}

    loop = PairLoop(kernel=kernel,
                                               dat_dict=kernel_map,
                                               shell_cutoff=math.sqrt(3.)*cell_width+tol)

    state.nc.zero()

    loop.execute()
    for ix in range(state.npart_local):
        assert state.nc[ix] == 26



def test_host_pair_loop_NS_FCC2():
    """
    Set a cutoff slightly larger than the 3rd nearest neighbour distance in
    the grid
    """
    A = State()

    crN2 = 10

    A.npart = (crN2**3)*4

    A.domain = md.domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = md.domain.BoundaryTypePeriodic()

    A.P = PositionDat(ncomp=3)
    A.nc = ParticleDat(ncomp=1, dtype=ctypes.c_int)


    cell_width = float(E)/float(crN2)

    A.P = PositionDat(ncomp=3)
    A.P[:] = md.utility.lattice.fcc((crN2, crN2, crN2), (E, E, E))

    A.npart_local = (crN2**3)*4
    A.filter_on_domain_boundary()


    kernel_code = '''
    NC.i[0]+=1;
    '''

    kernel = md.kernel.Kernel('test_host_pair_loop_NS_1',code=kernel_code)
    kernel_map = {'P': A.P(md.access.R),
                  'NC': A.nc(md.access.INC0)}

    loop = PairLoop(kernel=kernel,
                                               dat_dict=kernel_map,
                                               shell_cutoff=cell_width-tol)

    A.nc.zero()

    loop.execute()
    for ix in range(A.npart_local):
        assert A.nc[ix] == 12


def test_host_pair_loop_NS_FCC():
    """
    Set a cutoff slightly larger than the 3rd nearest neighbour distance in
    the grid
    """
    A = State()

    crN2 = 10

    A.npart = (crN2**3)*4

    A.domain = md.domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = md.domain.BoundaryTypePeriodic()

    A.P = PositionDat(ncomp=3)
    A.nc = ParticleDat(ncomp=1, dtype=ctypes.c_int)


    cell_width = (0.5*float(E))/float(crN2)

    A.P = PositionDat(ncomp=3)
    A.P[:] = md.utility.lattice.fcc((crN2, crN2, crN2), (E, E, E))

    A.npart_local = (crN2**3)*4
    A.filter_on_domain_boundary()


    kernel_code = '''
    NC.i[0]+=1;
    '''

    kernel = md.kernel.Kernel('test_host_pair_loop_NS_1',code=kernel_code)
    kernel_map = {'P': A.P(md.access.R),
                  'NC': A.nc(md.access.INC0)}

    loop = PairLoop(kernel=kernel,
                                               dat_dict=kernel_map,
                                               shell_cutoff=math.sqrt(2.)*cell_width+tol)

    A.nc.zero()

    loop.execute()
    for ix in range(A.npart_local):
        assert A.nc[ix] == 12


def test_host_pair_loop_NS_FCC_2():
    """
    Set a cutoff slightly larger than the 3rd nearest neighbour distance in
    the grid
    """
    A = State()

    crN2 = 10

    A.npart = (crN2**3)*4

    A.domain = md.domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = md.domain.BoundaryTypePeriodic()

    A.P = PositionDat(ncomp=3)
    A.nc = ParticleDat(ncomp=1, dtype=ctypes.c_int)
    A.nn = GlobalArray(ncomp=1, dtype=ctypes.c_int)
    A.nn2 = GlobalArray(ncomp=2, dtype=ctypes.c_int)
    A.nset = GlobalArray(ncomp=1, dtype=ctypes.c_int)
    A.nset.set(4)

    cell_width = (0.5*float(E))/float(crN2)

    A.P = PositionDat(ncomp=3)
    A.P[:] = md.utility.lattice.fcc((crN2, crN2, crN2), (E, E, E))

    A.npart_local = (crN2**3)*4
    NTOTAL = (crN2**3)*4
    A.filter_on_domain_boundary()

    kernel_code = '''
    NC.i[0]+=1;
    NN[0]++;
    NN2[0]+=NSET[0];
    NN2[1]+=2;
    '''

    kernel = md.kernel.Kernel('test_host_pair_loop_NS_1',code=kernel_code)
    kernel_map = {'P': A.P(md.access.R),
                  'NC': A.nc(md.access.INC_ZERO),
                  'NN': A.nn(md.access.INC_ZERO),
                  'NSET': A.nset(md.access.READ),
                  'NN2': A.nn2(md.access.INC_ZERO)}

    loop = PairLoop(
        kernel=kernel,
        dat_dict=kernel_map,
        shell_cutoff=math.sqrt(2.)*cell_width+tol
    )

    loop.execute()
    for ix in range(A.npart_local):
        assert A.nc[ix] == 12

    assert A.nn[0] == 12*NTOTAL
    assert A.nn2[0] == 12*NTOTAL*4
    assert A.nn2[1] == 12*NTOTAL*2

    loop2 = PairLoop(
        kernel=kernel,
        dat_dict=kernel_map,
        shell_cutoff=math.sqrt(2.)*cell_width-tol
    )
    loop3 = PairLoop(
        kernel=kernel,
        dat_dict=kernel_map,
        shell_cutoff=2*cell_width+tol
    )

    loop2.execute()
    for ix in range(A.npart_local):
        assert A.nc[ix] == 0


    loop3.execute()
    for ix in range(A.npart_local):
        assert A.nc[ix] == 18, '{}'.format(ix)

    loop.execute()
    for ix in range(A.npart_local):
        assert A.nc[ix] == 12, '{}'.format(ix)

    loop3.execute()
    for ix in range(A.npart_local):
        assert A.nc[ix] == 18, '{}'.format(ix)





