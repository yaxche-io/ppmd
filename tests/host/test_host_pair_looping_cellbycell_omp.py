#!/usr/bin/python

import pytest
import ctypes
import numpy as np
import math


import ppmd as md
from ppmd.access import *

N = 1000
crN = 10 #cubert(N)
E = 8.

Eo2 = E/2.

tol = 10.**(-12)

MPIRANK = md.mpi.MPI.COMM_WORLD.Get_rank()
MPISIZE = md.mpi.MPI.COMM_WORLD.Get_size()


PositionDat = md.data.PositionDat
ParticleDat = md.data.ParticleDat
ScalarArray = md.data.ScalarArray
GlobalArray = md.data.GlobalArray
State = md.state.State
PairLoop = md.pairloop.CellByCellOMP
Kernel = md.kernel.Kernel


@pytest.fixture
def state():

    A = State()
    A.npart = N
    A.domain = md.domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = md.domain.BoundaryTypePeriodic()

    pt = PositionDat(ncomp=3)

    A.p = pt

    A.v = ParticleDat(ncomp=3)
    A.f = ParticleDat(ncomp=3)
    A.gid = ParticleDat(ncomp=1, dtype=ctypes.c_int)
    A.nc = ParticleDat(ncomp=1, dtype=ctypes.c_int)

    A.u = GlobalArray(ncomp=1)
    A.u.halo_aware = True

    return A


@pytest.fixture(scope="module", params=(0, MPISIZE-1))
def base_rank(request):
    return request.param


def test_host_pair_loop_NS_1(state):
    """
    Set a cutoff slightly smaller than the smallest distance in the grid
    """


    cell_width = float(E)/float(crN)
    pi = np.zeros([N,3], dtype=ctypes.c_double)

    pi = md.utility.lattice.cubic_lattice((crN, crN, crN), (E,E,E))

    state.p[:] = pi
    state.npart_local = N
    state.filter_on_domain_boundary()

    kernel_code = '''
    const double r0 = P.i[0] - P.j[0];
    const double r1 = P.i[1] - P.j[1];
    const double r2 = P.i[2] - P.j[2];
    if ((r0*r0 + r1*r1 + r2*r2) <= %(CUTOFF)s*%(CUTOFF)s){
        NC.i[0]+=1;
    }
    ''' % {'CUTOFF': str(cell_width-tol)}

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
    const double r0 = P.i[0] - P.j[0];
    const double r1 = P.i[1] - P.j[1];
    const double r2 = P.i[2] - P.j[2];
    if ((r0*r0 + r1*r1 + r2*r2) <= %(CUTOFF)s*%(CUTOFF)s){
        NC.i[0]+=1;
    }
    ''' % {'CUTOFF': str(cell_width+tol)}

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


@pytest.mark.skipif("MPISIZE>1")
def test_cell_by_cell_single():

    E = 8.0
    N = 1000

    A = State()
    A.npart = N
    A.domain = md.domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = md.domain.BoundaryTypePeriodic()
    
    A.P = PositionDat(ncomp=3)

    A.NN = ParticleDat(ncomp=1, dtype=ctypes.c_int)
    A.NM = ParticleDat(ncomp=1, dtype=ctypes.c_int)
    A.D1 = ParticleDat(ncomp=8, dtype=ctypes.c_double)
    A.GA = GlobalArray(ncomp=1, dtype=ctypes.c_int)
    A.SA = ScalarArray(ncomp=1, dtype=ctypes.c_int)

    cutoff = E/5.
    A.SA[:] = 2


    rng = np.random.RandomState(11111)
    pi = rng.uniform(low=-0.5*E, high=0.5*E, size=(N, 3))
    d1i = rng.uniform(size=(N, 8))

    with A.modify() as m:
        if MPIRANK == 0:
            m.add({
                A.P: pi,
                A.D1: d1i
            })


    k = Kernel(
        'kall',
        r'''
        const double rx = P.j[0] - P.i[0];
        const double ry = P.j[1] - P.i[1];
        const double rz = P.j[2] - P.i[2];
        const double r2 = rx*rx + ry*ry + rz*rz;
        if (r2 < ({RC}*{RC})){{
            NN.i[0]++;
            GA[0] += SA[0];
        }}

        '''.format(
            RC=cutoff
        ),
    )

    l1 = PairLoop(
        k, 
        {
            'P': A.P(READ),
            'NN': A.NN(INC_ZERO),
            'SA': A.SA(READ),
            'GA': A.GA(INC_ZERO)
        },
        cutoff
    )

    l2 = PairLoop(
        k, 
        {
            'P': A.P(READ),
            'NN': A.NM(INC_ZERO),
            'D1': A.D1(INC_ZERO),
            'SA': A.SA(READ),
            'GA': A.GA(INC_ZERO)
        },
        cutoff
    )


    l1.execute()

    order = rng.permutation(range(N))

    assert np.linalg.norm(A.NM[:N, 0]) < 10.**-16

    for px in range(N):
        local_id = order[px]

        l2.execute(local_id=local_id)

        assert np.linalg.norm(A.D1[local_id, :], np.inf) < 10.**-16
        assert A.NN[local_id, 0] == A.NM[local_id, 0]
        assert A.GA[0] == 2 * A.NM[local_id, 0]


    assert np.linalg.norm(A.D1[:N, :]) < 10.**-16














