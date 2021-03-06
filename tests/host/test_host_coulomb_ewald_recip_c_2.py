__author__ = "W.R.Saunders"
__copyright__ = "Copyright 2016, W.R.Saunders"

import ctypes
import numpy as np

import pytest

from math import pi

import ppmd
import ppmd.coulomb.ewald

import os
def get_res_file_path(filename):
    return os.path.join(os.path.join(os.path.dirname(__file__), '../res'), filename)


mpi_rank = ppmd.mpi.MPI.COMM_WORLD.Get_rank()
mpi_ncomp = ppmd.mpi.MPI.COMM_WORLD.Get_size()
ParticleDat = ppmd.data.ParticleDat
PositionDat = ppmd.data.PositionDat
ScalarArray = ppmd.data.ScalarArray
State = ppmd.state.BaseMDState

def assert_tol(val, tol, msg="tolerance not met"):
    assert abs(val) < 10.**(-1*tol), msg

def test_ewald_energy_python_co2_2_1():
    """
    Test that the python implementation of ewald calculates the correct 
    real space contribution and self interaction contribution.
    """

    eta = 0.26506
    alpha = eta**2.
    rc = 12.

    e = 24.47507
    meo2 = -0.5 * e

    data = np.load(get_res_file_path('coulomb/CO2.npy'))

    N = data.shape[0]
    A = State()
    A.npart = N
    A.domain = ppmd.domain.BaseDomainHalo(extent=(e,e,e))
    A.domain.boundary_condition = ppmd.domain.BoundaryTypePeriodic()

    c = ppmd.coulomb.ewald.EwaldOrthoganal(domain=A.domain, real_cutoff=rc, alpha=alpha)
    assert c.alpha == alpha, "unexpected alpha"
    assert c.real_cutoff == rc, "unexpected rc"


    A.positions = PositionDat(ncomp=3)
    A.forces = ParticleDat(ncomp=3)
    A.charges = ParticleDat(ncomp=1)

    energy = ScalarArray(ncomp=1, dtype=ctypes.c_double)

    if mpi_rank == 0:
        A.positions[:] = data[:,0:3:]
        A.charges[:, 0] = data[:,3]
    A.scatter_data_from(0)

    c.evaluate_contributions(positions=A.positions, charges=A.charges)

    c.extract_forces_energy_reciprocal(A.positions, A.charges, A.forces, energy)

    assert abs(energy[0]*c.internal_to_ev() - 0.917463161E1) < 10.**-3

    A.gather_data_on(0)
    if mpi_rank == 0:
        assert abs( np.sum(A.charges[:, 0]) ) < 10.**-12, "total charge not zero"


def test_ewald_energy_python_co2_2_2():
    eta = 0.26506
    alpha = eta**2.
    rc = 12.

    e = 24.47507

    data = np.load(get_res_file_path('coulomb/CO2.npy'))

    N = data.shape[0]
    A = State()
    A.npart = N
    A.domain = ppmd.domain.BaseDomainHalo(extent=(e,e,e))
    A.domain.boundary_condition = ppmd.domain.BoundaryTypePeriodic()

    c = ppmd.coulomb.ewald.EwaldOrthoganal(domain=A.domain, real_cutoff=rc, alpha=alpha, shared_memory='mpi')
    assert c.alpha == alpha, "unexpected alpha"
    assert c.real_cutoff == rc, "unexpected rc"


    A.positions = PositionDat(ncomp=3)
    A.forces = ParticleDat(ncomp=3)
    A.charges = ParticleDat(ncomp=1)

    energy = ScalarArray(ncomp=1, dtype=ctypes.c_double)

    if mpi_rank == 0:
        A.positions[:] = data[:,0:3:]
        A.charges[:, 0] = data[:,3]
    A.scatter_data_from(0)

    c.evaluate_contributions(positions=A.positions, charges=A.charges)

    c.extract_forces_energy_reciprocal(A.positions, A.charges, A.forces, energy)

    assert abs(energy[0]*c.internal_to_ev() - 0.917463161E1) < 10.**-3, "{}, {}".format(energy[0]*c.internal_to_ev(), energy[0])



def test_ewald_energy_python_co2_2_3():
    """
    Test non cube domains reciprocal space
    """

    SHARED_MEMORY = False

    eta = 0.26506
    alpha = eta**2.
    rc = 12.
    e0 = 30.
    e1 = 40.
    e2 = 50.

    data = np.load(get_res_file_path('coulomb/CO2cuboid.npy'))

    N = data.shape[0]
    A = State()
    A.npart = N
    A.domain = ppmd.domain.BaseDomainHalo(extent=(e0,e1,e2))
    A.domain.boundary_condition = ppmd.domain.BoundaryTypePeriodic()

    c = ppmd.coulomb.ewald.EwaldOrthoganal(
        domain=A.domain,
        real_cutoff=12.,
        alpha=alpha,
        recip_cutoff=0.2667*pi*2.0,
        recip_nmax=(8,11,14),
        shared_memory=SHARED_MEMORY
    )

    assert c.alpha == alpha, "unexpected alpha"
    assert c.real_cutoff == rc, "unexpected rc"


    A.positions = PositionDat(ncomp=3)
    A.forces = ParticleDat(ncomp=3)
    A.charges = ParticleDat(ncomp=1)

    energy = ScalarArray(ncomp=1, dtype=ctypes.c_double)

    if mpi_rank == 0:
        A.positions[:] = data[:,0:3:]
        A.charges[:, 0] = data[:,3]
    A.scatter_data_from(0)

    c.evaluate_contributions(positions=A.positions, charges=A.charges)

    c.extract_forces_energy_reciprocal(A.positions, A.charges, A.forces, energy)

    rs = c._test_python_structure_factor()

    assert abs(rs*c.internal_to_ev() - 0.3063162184E+02) < 10.**-3, "structure factor"
    assert abs(energy[0]*c.internal_to_ev() - 0.3063162184E+02) < 10.**-3, "particle loop"

    energy_real = ScalarArray(ncomp=1, dtype=ctypes.c_double)
    energy_self = ScalarArray(ncomp=1, dtype=ctypes.c_double)


    c.extract_forces_energy_real(A.positions, A.charges, A.forces, energy_real)

    c.evaluate_self_interactions(A.charges, energy_self)

    assert abs(energy_real[0]*c.internal_to_ev() + energy_self[0]*c.internal_to_ev() + 0.6750050309E+04) < 10.**-2, "bad real space part"

def test_ewald_energy_python_co2_2_3_omp():
    """
    Test non cube domains reciprocal space
    """

    SHARED_MEMORY = 'omp'

    eta = 0.26506
    alpha = eta**2.
    rc = 12.
    e0 = 30.
    e1 = 40.
    e2 = 50.

    data = np.load(get_res_file_path('coulomb/CO2cuboid.npy'))

    N = data.shape[0]
    A = State()
    A.npart = N
    A.domain = ppmd.domain.BaseDomainHalo(extent=(e0,e1,e2))
    A.domain.boundary_condition = ppmd.domain.BoundaryTypePeriodic()

    c = ppmd.coulomb.ewald.EwaldOrthoganal(
        domain=A.domain,
        real_cutoff=12.,
        alpha=alpha,
        recip_cutoff=0.2667*pi*2.0,
        recip_nmax=(8,11,14),
        shared_memory=SHARED_MEMORY
    )

    assert c.alpha == alpha, "unexpected alpha"
    assert c.real_cutoff == rc, "unexpected rc"


    A.positions = PositionDat(ncomp=3)
    A.forces = ParticleDat(ncomp=3)
    A.charges = ParticleDat(ncomp=1)

    energy = ScalarArray(ncomp=1, dtype=ctypes.c_double)

    if mpi_rank == 0:
        A.positions[:] = data[:,0:3:]
        A.charges[:, 0] = data[:,3]
    A.scatter_data_from(0)

    c.evaluate_contributions(positions=A.positions, charges=A.charges)

    assert abs(np.linalg.norm(c._vars['recip_space_kernel'][:]) - 3298.0244365) < 10.**-8, "d"

    rs = c._test_python_structure_factor()
    c.extract_forces_energy_reciprocal(A.positions, A.charges, A.forces, energy)


    assert abs(rs*c.internal_to_ev() - 0.3063162184E+02) < 10.**-3, "structure factor"
    assert abs(energy[0]*c.internal_to_ev() - 0.3063162184E+02) < 10.**-3, "particle loop"

    energy_real = ScalarArray(ncomp=1, dtype=ctypes.c_double)
    energy_self = ScalarArray(ncomp=1, dtype=ctypes.c_double)


    c.extract_forces_energy_real(A.positions, A.charges, A.forces, energy_real)

    c.evaluate_self_interactions(A.charges, energy_self)

    assert abs(energy_real[0]*c.internal_to_ev() + energy_self[0]*c.internal_to_ev() + 0.6750050309E+04) < 10.**-2, "bad real space part"





def test_ewald_energy_python_co2_2_3_mpi():
    """
    Test non cube domains reciprocal space
    """

    SHARED_MEMORY = 'mpi'

    eta = 0.26506
    alpha = eta**2.
    rc = 12.
    e0 = 30.
    e1 = 40.
    e2 = 50.

    data = np.load(get_res_file_path('coulomb/CO2cuboid.npy'))

    N = data.shape[0]
    A = State()
    A.npart = N
    A.domain = ppmd.domain.BaseDomainHalo(extent=(e0,e1,e2))
    A.domain.boundary_condition = ppmd.domain.BoundaryTypePeriodic()

    c = ppmd.coulomb.ewald.EwaldOrthoganal(
        domain=A.domain,
        real_cutoff=12.,
        alpha=alpha,
        recip_cutoff=0.2667*pi*2.0,
        recip_nmax=(8,11,14),
        shared_memory=SHARED_MEMORY
    )

    assert c.alpha == alpha, "unexpected alpha"
    assert c.real_cutoff == rc, "unexpected rc"


    A.positions = PositionDat(ncomp=3)
    A.forces = ParticleDat(ncomp=3)
    A.charges = ParticleDat(ncomp=1)

    energy = ScalarArray(ncomp=1, dtype=ctypes.c_double)

    if mpi_rank == 0:
        A.positions[:] = data[:,0:3:]
        A.charges[:, 0] = data[:,3]
    A.scatter_data_from(0)

    c.evaluate_contributions(positions=A.positions, charges=A.charges)

    rs = c._test_python_structure_factor()
    c.extract_forces_energy_reciprocal(A.positions, A.charges, A.forces, energy)


    assert abs(rs*c.internal_to_ev() - 0.3063162184E+02) < 10.**-3, "structure factor"
    assert abs(energy[0]*c.internal_to_ev() - 0.3063162184E+02) < 10.**-3, "particle loop"

    energy_real = ScalarArray(ncomp=1, dtype=ctypes.c_double)
    energy_self = ScalarArray(ncomp=1, dtype=ctypes.c_double)


    c.extract_forces_energy_real(A.positions, A.charges, A.forces, energy_real)

    c.evaluate_self_interactions(A.charges, energy_self)

    assert abs(energy_real[0]*c.internal_to_ev() + energy_self[0]*c.internal_to_ev() + 0.6750050309E+04) < 10.**-2, "bad real space part"




