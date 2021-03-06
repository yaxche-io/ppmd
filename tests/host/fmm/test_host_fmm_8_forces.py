from __future__ import print_function, division

__author__ = "W.R.Saunders"
__copyright__ = "Copyright 2016, W.R.Saunders"

import pytest, ctypes, math
from mpi4py import MPI
import numpy as np

#from ppmd_vis import plot_spheres

import itertools
def get_res_file_path(filename):
    return os.path.join(os.path.join(os.path.dirname(__file__), '../../res'), filename)


from ppmd import *
from ppmd.coulomb.fmm import *
from ppmd.coulomb.ewald_half import *
from scipy.special import sph_harm, lpmv
import time

from math import *

MPISIZE = MPI.COMM_WORLD.Get_size()
MPIRANK = MPI.COMM_WORLD.Get_rank()
MPIBARRIER = MPI.COMM_WORLD.Barrier
DEBUG = False
SHARED_MEMORY = 'omp'

def red(*input):
    try:
        from termcolor import colored
        return colored(*input, color='red')
    except Exception as e: return input
def green(*input):
    try:
        from termcolor import colored
        return colored(*input, color='green')
    except Exception as e: return input
def yellow(*input):
    try:
        from termcolor import colored
        return colored(*input, color='yellow')
    except Exception as e: return input

def red_tol(val, tol):
    if abs(val) > tol:
        return red(str(val))
    else:
        return green(str(val))


cube_offsets = (
    (-1,1,-1),
    (-1,-1,-1),
    (-1,0,-1),
    (0,1,-1),
    (0,-1,-1),
    (0,0,-1),
    (1,0,-1),
    (1,1,-1),
    (1,-1,-1),

    (-1,1,0),
    (-1,0,0),
    (-1,-1,0),
    (0,-1,0),
    (0,1,0),
    (1,0,0),
    (1,1,0),
    (1,-1,0),

    (-1,0,1),
    (-1,1,1),
    (-1,-1,1),
    (0,0,1),
    (0,1,1),
    (0,-1,1),
    (1,0,1),
    (1,1,1),
    (1,-1,1)
)

def tuple_it(*args, **kwargs):
    if len(kwargs) == 0:
        tx = args[0]
        return itertools.product(range(tx[0]), range(tx[1]), range(tx[2]))
    else:
        l = kwargs['low']
        h = kwargs['high']
        return itertools.product(range(l[0], h[0]),
                                 range(l[1], h[1]),
                                 range(l[2], h[2]))


def spherical(xyz):
    if type(xyz) is tuple or len(xyz.shape) == 1:
        sph = np.zeros(3)
        xy = xyz[0]**2 + xyz[1]**2
        # r
        sph[0] = np.sqrt(xy + xyz[2]**2)
        # polar angle
        sph[1] = np.arctan2(np.sqrt(xy), xyz[2])
        # longitude angle
        sph[2] = np.arctan2(xyz[1], xyz[0])

    else:
        sph = np.zeros(xyz.shape)
        xy = xyz[:,0]**2 + xyz[:,1]**2
        # r
        sph[:,0] = np.sqrt(xy + xyz[:,2]**2)
        # polar angle
        sph[:,1] = np.arctan2(np.sqrt(xy), xyz[:,2])
        # longitude angle
        sph[:,2] = np.arctan2(xyz[:,1], xyz[:,0])

    #print("spherical", xyz, sph)
    return sph


def Hfoo(nx, mx):
    return math.sqrt(
        float(math.factorial(nx - abs(mx)))/math.factorial(nx + abs(mx))
    )

def Pfoo(nx, mx, x):
    if abs(mx) > abs(nx):
        return 0.0
    elif nx < 0:
        return Pfoo(-1*nx -1, mx, x)
    else:
        return lpmv(mx, nx, x)

def Yfoo(nx, mx, theta, phi):
    coeff = Hfoo(nx, mx)
    legp = lpmv(abs(mx), nx, math.cos(theta))
    
    assert abs(legp.imag) < 10.**-16

    return coeff * legp * cmath.exp(1.j * mx * phi)







def compute_phi(llimit, moments, disp_sph):

    phi_sph_re = 0.
    phi_sph_im = 0.
    def re_lm(l,m): return (l**2) + l + m
    def im_lm(l,m): return (l**2) + l +  m + llimit**2

    for lx in range(llimit):
        mrange = list(range(lx, -1, -1)) + list(range(1, lx+1))
        mrange2 = list(range(-1*lx, 1)) + list(range(1, lx+1))
        scipy_p = lpmv(mrange, lx, np.cos(disp_sph[0,1]))

        #print('lx', lx, '-------------')

        for mxi, mx in enumerate(mrange2):
            #print('mx', mx)

            re_exp = np.cos(mx*disp_sph[0,2])
            im_exp = np.sin(mx*disp_sph[0,2])

            val = math.sqrt(math.factorial(
                lx - abs(mx))/math.factorial(lx + abs(mx)))
            val *= scipy_p[mxi]

            irad = 1. / (disp_sph[0,0] ** (lx+1.))

            scipy_real = re_exp * val * irad
            scipy_imag = im_exp * val * irad

            ppmd_mom_re = moments[re_lm(lx, mx)]
            ppmd_mom_im = moments[im_lm(lx, mx)]

            phi_sph_re += scipy_real*ppmd_mom_re - scipy_imag*ppmd_mom_im
            phi_sph_im += scipy_real*ppmd_mom_im + ppmd_mom_re*scipy_imag

    return phi_sph_re, phi_sph_im



def compute_phi_local(llimit, moments, disp_sph):

    phi_sph_re = 0.
    phi_sph_im = 0.
    def re_lm(l,m): return (l**2) + l + m
    def im_lm(l,m): return (l**2) + l +  m + llimit**2

    for lx in range(llimit):
        mrange = list(range(lx, -1, -1)) + list(range(1, lx+1))
        mrange2 = list(range(-1*lx, 1)) + list(range(1, lx+1))
        scipy_p = lpmv(mrange, lx, np.cos(disp_sph[0,1]))

        #print('lx', lx, '-------------')

        for mxi, mx in enumerate(mrange2):

            re_exp = np.cos(mx*disp_sph[0,2])
            im_exp = np.sin(mx*disp_sph[0,2])

            #print('mx', mx, im_exp)

            val = math.sqrt(math.factorial(
                lx - abs(mx))/math.factorial(lx + abs(mx)))
            val *= scipy_p[mxi]

            irad = disp_sph[0,0] ** (lx)

            scipy_real = re_exp * val * irad
            scipy_imag = im_exp * val * irad

            ppmd_mom_re = moments[re_lm(lx, mx)]
            ppmd_mom_im = moments[im_lm(lx, mx)]

            phi_sph_re += scipy_real*ppmd_mom_re - scipy_imag*ppmd_mom_im
            phi_sph_im += scipy_real*ppmd_mom_im + ppmd_mom_re*scipy_imag

    return phi_sph_re, phi_sph_im


def get_p_exp(fmm, disp_sph):
    def re_lm(l,m): return (l**2) + l + m
    exp_array = np.zeros(fmm.L*8 + 2, dtype=ctypes.c_double)
    p_array = np.zeros((fmm.L*2)**2, dtype=ctypes.c_double)
    for lx in range(fmm.L*2):
        mrange = list(range(lx, -1, -1)) + list(range(1, lx+1))
        mrange2 = list(range(-1*lx, 1)) + list(range(1, lx+1))
        scipy_p = lpmv(mrange, lx, np.cos(disp_sph[0,1]))

        for mxi, mx in enumerate(mrange2):
            coeff = math.sqrt(float(math.factorial(lx-abs(mx)))/
                math.factorial(lx+abs(mx)))
            p_array[re_lm(lx, mx)] = scipy_p[mxi].real*coeff

    for mxi, mx in enumerate(list(
            range(-2*fmm.L, 1)) + list(range(1, 2*fmm.L+1))
        ):

        exp_array[mxi] = np.cos(mx*disp_sph[0,2])
        exp_array[mxi + fmm.L*4 + 1] = np.sin(mx*disp_sph[0,2])

    return p_array, exp_array



@pytest.mark.skipif("MPISIZE>1")
#@pytest.mark.skipif("True")
def test_fmm_force_direct_1():

    R = 3
    eps = 10.**-6
    free_space = '27'

    N = 4
    E = 4.
    rc = E/4

    A = state.State()
    A.domain = domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = domain.BoundaryTypePeriodic()

    ASYNC = False
    DIRECT = True if MPISIZE == 1 else False

    DIRECT= True
    EWALD = True

    fmm = PyFMM(domain=A.domain, r=R, eps=eps, free_space=free_space)

    A.npart = N

    rng = np.random.RandomState(seed=1234)

    A.P = data.PositionDat(ncomp=3)
    A.F = data.ParticleDat(ncomp=3)
    A.FE = data.ParticleDat(ncomp=3)
    A.Q = data.ParticleDat(ncomp=1)

    A.crr = data.ScalarArray(ncomp=1)
    A.cri = data.ScalarArray(ncomp=1)
    A.crs = data.ScalarArray(ncomp=1)


    if N == 4:
        ra = 0.25 * E
        nra = -0.25 * E

        A.P[0,:] = ( 1.01,  1.01, 0.0)
        A.P[1,:] = (-1.01,  1.01, 0.0)
        A.P[2,:] = (-1.01, -1.01, 0.0)
        A.P[3,:] = ( 1.01, -1.01, 0.0)

        A.Q[0,0] = -1.
        A.Q[1,0] = 1.
        A.Q[2,0] = -1.
        A.Q[3,0] = 1.

    elif N == 1:
        A.P[0,:] = ( 0.25*E, 0.25*E, 0.25*E)
        A.P[0,:] = ( 10.**-6, 10.**-6, 10.**-6)

        #A.P[0,:] = (0, -0.25*E, 0)
        #A.P[1,:] = (0, 0.25*E, 0)
        #A.P[0,:] = (0, 0, -0.25*E)
        #A.P[1,:] = (0, 0, 0.25*E)

        #A.Q[:,0] = 1.

        A.Q[0,0] = 1.

    elif N == 2:
        #A.P[0,:] = ( 0.25*E, 0.25*E, 0.25*E)
        #A.P[1,:] = ( -0.25*E, -0.25*E, 0)

        #A.P[0,:] = (0, -0.25*E, 0)
        #A.P[1,:] = (0, 0.25*E, 0)
        #A.P[0,:] = (0, 0, -0.25*E)
        #A.P[1,:] = (0, 0, 0.25*E)

        #A.Q[:,0] = 1.
        ra = 0.25 * E
        nra = -0.25 * E

        eps = 0.00

        epsx = 0
        epsy = 0
        epsz = 0

        A.P[0,:] = ( 1.000, 0.001, 0.001)
        A.P[1,:] = (-1.001, 0.001, 0.001)

        #A.P[:2:,:] = rng.uniform(low=-0.4999*E, high=0.4999*E, size=(N,3))

        A.Q[0,0] = -1.
        A.Q[1,0] = 1.

    elif N == 8:
        for px in range(8):
            phi = (float(px)/8) * 2. * math.pi
            pxr = 0.25*E
            pxx = pxr * math.cos(phi)
            pxy = pxr * math.sin(phi)


            A.P[px, :] = (pxx, pxy, 0)
            A.Q[px, 0] = 1. - 2. * (px % 2)
            #A.Q[px, 0] = -1.

        #A.P[0,:] += eps

        eps = 0.00001
        #A.P[0:N:2,0] += eps
        #A.P[0,0] -= eps
        A.P[4,0] -= eps
        A.P[:, 2] -= 0.200
        A.P[:, 1] -= 0.200

        #A.Q[0,0] = 0.
        A.Q[1,0] = 0.
        A.Q[4,0] = 0.
        A.Q[3,0] = 0.
        A.Q[5,0] = 0.
        A.Q[6,0] = 0.
        A.Q[7,0] = 0.

    else:
        assert N % 2 == 0
        for px in range(N//2):
            pos = rng.uniform(low=-0.4999*E, high=0.4999*E, size=(1,3))
            cha = rng.uniform(low=-1., high=1.)

            A.P[px, :] = pos
            A.Q[px, 0] = cha

            A.P[-1*(px+1), :] = -1.0*pos
            A.Q[-1*(px+1), 0] = cha

        bias = np.sum(A.Q[:])
        A.Q[:,0] -= bias/N

        dipole = np.zeros(3)
        for px in range(N):
            dipole[:] += A.P[px,:]*A.Q[px,0]

        bias = np.sum(A.Q[:])

        print("DIPOLE:\t", dipole, "TOTAL CHARGE:\t", bias)

    A.scatter_data_from(0)

    t0 = time.time()
    #phi_py = fmm._test_call(A.P, A.Q, execute_async=ASYNC)
    phi_py = fmm(A.P, A.Q, forces=A.F, execute_async=ASYNC)
    t1 = time.time()



    direct_forces = np.zeros((N, 3))

    if DIRECT:
        #print("WARNING 0-th PARTICLE ONLY")
        phi_direct = 0.0

        # compute phi from image and surrounding 26 cells

        for ix in range(N):

            phi_part = 0.0
            for jx in range(ix+1, N):
                rij = np.linalg.norm(A.P[jx,:] - A.P[ix,:])
                phi_direct += A.Q[ix, 0] * A.Q[jx, 0] /rij
                phi_part += A.Q[ix, 0] * A.Q[jx, 0] /rij

                direct_forces[ix,:] -= A.Q[ix, 0] * A.Q[jx, 0] * \
                                       (A.P[jx,:] - A.P[ix,:]) / (rij**3.)
                direct_forces[jx,:] += A.Q[ix, 0] * A.Q[jx, 0] * \
                                       (A.P[jx,:] - A.P[ix,:]) / (rij**3.)
            if free_space == '27':
                for ofx in cube_offsets:
                    cube_mid = np.array(ofx)*E
                    for jx in range(N):
                        rij = np.linalg.norm(A.P[jx,:] + cube_mid - A.P[ix, :])
                        phi_direct += 0.5*A.Q[ix, 0] * A.Q[jx, 0] /rij
                        phi_part += 0.5*A.Q[ix, 0] * A.Q[jx, 0] /rij

                        direct_forces[ix,:] -= A.Q[ix, 0] * A.Q[jx, 0] * \
                                           (A.P[jx,:] - A.P[ix,:] + cube_mid) \
                                               / (rij**3.)


    local_err = abs(phi_py - phi_direct)
    if local_err > eps: serr = red(local_err)
    else: serr = green(local_err)

    if MPIRANK == 0 and DEBUG:
        print("\n")
        #print(60*"-")
        #opt.print_profile()
        #print(60*"-")
        print("TIME FMM:\t", t1 - t0)
        print("ENERGY DIRECT:\t{:.20f}".format(phi_direct))
        print("ENERGY FMM:\t", phi_py)
        print("ERR:\t\t", serr)

    for px in range(N):

        err_re_c = red_tol(np.linalg.norm(direct_forces[px,:] - A.F[px,:],
                                          ord=np.inf), 10.**-6)

        print("PX:", px)
        print("\t\tFORCE DIR :",direct_forces[px,:])
        print("\t\tFORCE FMMC:",A.F[px,:], err_re_c)

    fmm.free()


#@pytest.mark.skipif("MPISIZE>1")
#@pytest.mark.skipif("True")
def test_fmm_force_ewald_1():

    R = 3
    eps = 10.**-8
    free_space = False

    N = 32
    E = 4.

    #N = 10000
    #E = 100.

    rc = E/8

    A = state.State()
    A.domain = domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = domain.BoundaryTypePeriodic()

    ASYNC = False

    CUDA=False

    fmm = PyFMM(domain=A.domain, r=R, l=22, free_space=free_space,
                cuda=CUDA)

    A.npart = N

    rng = np.random.RandomState(seed=1234)
    rng = np.random.RandomState(seed=95235)

    A.P = data.PositionDat(ncomp=3)
    A.F = data.ParticleDat(ncomp=3)
    A.FE = data.ParticleDat(ncomp=3)
    A.Q = data.ParticleDat(ncomp=1)

    A.crr = data.ScalarArray(ncomp=1)
    A.cri = data.ScalarArray(ncomp=1)
    A.crs = data.ScalarArray(ncomp=1)


    if N == 4:
        ra = 0.25 * E
        nra = -0.25 * E

        A.P[0,:] = ( 0.21,  0.21, 0.00)
        A.P[1,:] = (-0.21,  0.21, 0.00)
        A.P[2,:] = (-0.21, -0.21, 0.00)
        A.P[3,:] = ( 0.21, -0.21, 0.00)

        #A.P[0,:] = ( 0.00,  0.21, 0.21)
        #A.P[1,:] = ( 0.00,  0.21,-0.21)
        #A.P[2,:] = ( 0.00, -0.21,-0.21)
        #A.P[3,:] = ( 0.00, -0.21, 0.21)

        #A.P[0,:] = ( 1.01,  1.01, 0.00)
        #A.P[1,:] = (-1.01,  1.01, 0.00)
        #A.P[2,:] = (-1.01, -1.01, 0.00)
        #A.P[3,:] = ( 1.01, -1.01, 0.00)

        A.Q[0,0] = -1.
        A.Q[1,0] = 1.
        A.Q[2,0] = -1.
        A.Q[3,0] = 1.

    elif N == 1:
        A.P[0,:] = ( 0.25*E, 0.25*E, 0.25*E)
        A.P[0,:] = ( 10.**-6, 10.**-6, 10.**-6)

        #A.P[0,:] = (0, -0.25*E, 0)
        #A.P[1,:] = (0, 0.25*E, 0)
        #A.P[0,:] = (0, 0, -0.25*E)
        #A.P[1,:] = (0, 0, 0.25*E)

        #A.Q[:,0] = 1.

        A.Q[0,0] = 1.

    elif N == 2:
        #A.P[0,:] = ( 0.25*E, 0.25*E, 0.25*E)
        #A.P[1,:] = ( -0.25*E, -0.25*E, 0)

        #A.P[0,:] = (0, -0.25*E, 0)
        #A.P[1,:] = (0, 0.25*E, 0)
        #A.P[0,:] = (0, 0, -0.25*E)
        #A.P[1,:] = (0, 0, 0.25*E)

        #A.Q[:,0] = 1.
        ra = 0.25 * E
        nra = -0.25 * E

        epsx = 0
        epsy = 0
        epsz = 0

        A.P[0,:] = ( 0.001, 0.001,  1.001)
        A.P[1,:] = ( 0.001, 0.001, -1.001)

        #A.P[:2:,:] = rng.uniform(low=-0.4999*E, high=0.4999*E, size=(N,3))

        A.Q[0,0] = -1.
        A.Q[1,0] = 1.

    elif N == 8:
        for px in range(8):
            phi = (float(px)/8) * 2. * math.pi
            pxr = 0.25*E
            pxx = pxr * math.cos(phi)
            pxy = pxr * math.sin(phi)


            A.P[px, :] = (pxx, pxy, 0)
            A.Q[px, 0] = 1. - 2. * (px % 2)
            #A.Q[px, 0] = -1.

        #A.P[0,:] += eps

        #A.P[0:N:2,0] += eps
        #A.P[0,0] -= eps
        A.P[4,0] -= eps
        A.P[:, 2] -= 0.200
        A.P[:, 1] -= 0.200

        #A.Q[0,0] = 0.
        A.Q[1,0] = 0.
        A.Q[4,0] = 0.
        A.Q[3,0] = 0.
        A.Q[5,0] = 0.
        A.Q[6,0] = 0.
        A.Q[7,0] = 0.

    else:
        assert N % 2 == 0
        for px in range(N//2):
            pos = rng.uniform(low=-0.4999*E, high=0.4999*E, size=(1,3))
            cha = rng.uniform(low=-1., high=1.)

            A.P[px, :] = pos
            A.Q[px, 0] = cha

            A.P[-1*(px+1), :] = -1.0*pos
            A.Q[-1*(px+1), 0] = cha

        bias = np.sum(A.Q[:])
        A.Q[:,0] -= bias/N


    dipole = np.zeros(3)
    for px in range(N):
        dipole[:] += A.P[px,:]*A.Q[px,0]
    
    bias = np.sum(A.Q[:])

    Q = np.sum(np.abs(A.Q[:N:,0]))

    A.scatter_data_from(0)

    t0 = time.time()
    phi_py = fmm(A.P, A.Q, forces=A.F, execute_async=ASYNC)
    t1 = time.time()


    ewald = EwaldOrthoganalHalf(
        domain=A.domain,
        real_cutoff=rc,
        eps=eps,
        shared_memory=SHARED_MEMORY
    )

    t2 = time.time()
    ewald.evaluate_contributions(positions=A.P, charges=A.Q)
    A.cri[0] = 0.0
    ewald.extract_forces_energy_reciprocal(A.P, A.Q, A.FE, A.cri)
    A.crr[0] = 0.0
    ewald.extract_forces_energy_real(A.P, A.Q, A.FE, A.crr)
    A.crs[0] = 0.0
    ewald.evaluate_self_interactions(A.Q, A.crs)

    t3 = time.time()

    phi_ewald = A.cri[0] + A.crr[0] + A.crs[0]

    local_err = abs(phi_py - phi_ewald)/Q
    if local_err > eps: serr = red(local_err)
    else: serr = green(local_err)

    for px in range(A.npart_local):

        assert np.linalg.norm(A.FE[px,:] - A.F[px,:], ord=np.inf) < 10.**-6




    if MPIRANK == 0 and DEBUG:
        print("\n")
        #print(60*"-")
        #opt.print_profile()
        #print(60*"-")
        print("TIME EWALD:\t", t3 - t2)
        print("TIME FMM:\t", t1 - t0)
        print("ENERGY EWALD:\t{:.20f}".format(phi_ewald))
        print("ENERGY FMM:\t", phi_py)
        print("ERR:\t\t", serr)

    # run the same again
    A.F[:] = 0.0
    t0 = time.time()
    phi_py = fmm(A.P, A.Q, forces=A.F, execute_async=ASYNC)
    t1 = time.time()

    local_err = abs(phi_py - phi_ewald)/Q
    if local_err > eps: serr = red(local_err)
    else: serr = green(local_err)

    A.gather_data_on(0)
    if MPIRANK == 0:
        for px in range(N):

            err_re_c = red_tol(np.linalg.norm(A.FE[px,:] - A.F[px,:],
                                              ord=np.inf), 10.**-6)

            assert np.linalg.norm(A.FE[px,:] - A.F[px,:], ord=np.inf) < 10.**-6

    if MPIRANK == 0 and DEBUG:
        print("TIME FMM:\t", t1 - t0)
        print("ENERGY FMM:\t", phi_py)
        print("ERR:\t\t", serr)

    fmm.free()


@pytest.mark.skipif("True")
def test_fmm_force_ewald_2():

    R = 3
    eps = 10.**-6
    free_space = True

    N = 2
    E = 4.
    rc = E/8

    A = state.State()
    A.domain = domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = domain.BoundaryTypePeriodic()

    ASYNC = False
    DIRECT = True if MPISIZE == 1 else False

    DIRECT= True
    EWALD = True

    fmm = PyFMM(domain=A.domain, r=R, eps=eps, free_space=free_space)

    A.npart = N

    rng = np.random.RandomState(seed=1234)

    A.P = data.PositionDat(ncomp=3)
    A.F = data.ParticleDat(ncomp=3)
    A.FE = data.ParticleDat(ncomp=3)
    A.Q = data.ParticleDat(ncomp=1)

    A.crr = data.ScalarArray(ncomp=1)
    A.cri = data.ScalarArray(ncomp=1)
    A.crs = data.ScalarArray(ncomp=1)


    if N == 4:
        ra = 0.25 * E
        nra = -0.25 * E

        A.P[0,:] = ( 0.21,  0.21, 0.00)
        A.P[1,:] = (-0.21,  0.21, 0.00)
        A.P[2,:] = (-0.21, -0.21, 0.00)
        A.P[3,:] = ( 0.21, -0.21, 0.00)

        #A.P[0,:] = ( 0.00,  0.21, 0.21)
        #A.P[1,:] = ( 0.00,  0.21,-0.21)
        #A.P[2,:] = ( 0.00, -0.21,-0.21)
        #A.P[3,:] = ( 0.00, -0.21, 0.21)

        #A.P[0,:] = ( 1.01,  1.01, 0.00)
        #A.P[1,:] = (-1.01,  1.01, 0.00)
        #A.P[2,:] = (-1.01, -1.01, 0.00)
        #A.P[3,:] = ( 1.01, -1.01, 0.00)

        A.Q[0,0] = -1.
        A.Q[1,0] = 1.
        A.Q[2,0] = -1.
        A.Q[3,0] = 1.

    elif N == 1:
        A.P[0,:] = ( 0.25*E, 0.25*E, 0.25*E)
        A.P[0,:] = ( 10.**-6, 10.**-6, 10.**-6)

        #A.P[0,:] = (0, -0.25*E, 0)
        #A.P[1,:] = (0, 0.25*E, 0)
        #A.P[0,:] = (0, 0, -0.25*E)
        #A.P[1,:] = (0, 0, 0.25*E)

        #A.Q[:,0] = 1.

        A.Q[0,0] = 1.

    elif N == 2:
        #A.P[0,:] = ( 0.25*E, 0.25*E, 0.25*E)
        #A.P[1,:] = ( -0.25*E, -0.25*E, 0)

        #A.P[0,:] = (0, -0.25*E, 0)
        #A.P[1,:] = (0, 0.25*E, 0)
        #A.P[0,:] = (0, 0, -0.25*E)
        #A.P[1,:] = (0, 0, 0.25*E)

        #A.Q[:,0] = 1.
        ra = 0.25 * E
        nra = -0.25 * E

        eps = 0.00

        epsx = 0
        epsy = 0
        epsz = 0

        A.P[0,:] = ( 1.999999, 0., 0.)
        A.P[1,:] = ( 0., 0., 0.)

        #A.P[:2:,:] = rng.uniform(low=-0.4999*E, high=0.4999*E, size=(N,3))

        A.Q[0,0] = -1.
        A.Q[1,0] = 1.

    elif N == 8:
        for px in range(8):
            phi = (float(px)/8) * 2. * math.pi
            pxr = 0.25*E
            pxx = pxr * math.cos(phi)
            pxy = pxr * math.sin(phi)


            A.P[px, :] = (pxx, pxy, 0)
            A.Q[px, 0] = 1. - 2. * (px % 2)
            #A.Q[px, 0] = -1.

        #A.P[0,:] += eps

        eps = 0.00001
        #A.P[0:N:2,0] += eps
        #A.P[0,0] -= eps
        A.P[4,0] -= eps
        A.P[:, 2] -= 0.200
        A.P[:, 1] -= 0.200

        #A.Q[0,0] = 0.
        A.Q[1,0] = 0.
        A.Q[4,0] = 0.
        A.Q[3,0] = 0.
        A.Q[5,0] = 0.
        A.Q[6,0] = 0.
        A.Q[7,0] = 0.

    else:
        assert N % 2 == 0
        for px in range(N//2):
            pos = rng.uniform(low=-0.4999*E, high=0.4999*E, size=(1,3))
            cha = rng.uniform(low=-1., high=1.)

            A.P[px, :] = pos
            A.Q[px, 0] = cha

            A.P[-1*(px+1), :] = -1.0*pos
            A.Q[-1*(px+1), 0] = cha

        bias = np.sum(A.Q[:])
        A.Q[:,0] -= bias/N


    dipole = np.zeros(3)
    for px in range(N):
        dipole[:] += A.P[px,:]*A.Q[px,0]

    bias = np.sum(A.Q[:])

    print("DIPOLE:\t", dipole, "TOTAL CHARGE:\t", bias)

    A.scatter_data_from(0)

    print("boundary", A.domain.boundary)

    t0 = time.time()
    phi_py = fmm(A.P, A.Q, forces=A.F, execute_async=ASYNC)
    t1 = time.time()


    if MPIRANK == 0 and DEBUG:
        print("\n")
        #print(60*"-")
        #opt.print_profile()
        #print(60*"-")
        print("TIME FMM:\t", t1 - t0)
        print("ENERGY FMM:\t", phi_py)

    A.gather_data_on(0)
    if MPIRANK == 0:
        for px in range(N):

            print("PX:", px)
            print("\t\tFORCE FMM:",A.F[px,:])


    fmm.free()


@pytest.mark.skipif("True")
def test_fmm_force_direct_3():

    R = 3
    L = 12
    free_space = True

    N = 2
    E = 4.
    rc = E/4

    A = state.State()
    A.domain = domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = domain.BoundaryTypePeriodic()

    ASYNC = False
    DIRECT = True if MPISIZE == 1 else False

    DIRECT= True
    EWALD = True

    fmm = PyFMM(domain=A.domain, r=R, eps=None, l=L, free_space=free_space)

    A.npart = N

    rng = np.random.RandomState(seed=1234)

    A.P = data.PositionDat(ncomp=3)
    A.F = data.ParticleDat(ncomp=3)
    A.FE = data.ParticleDat(ncomp=3)
    A.Q = data.ParticleDat(ncomp=1)

    A.crr = data.ScalarArray(ncomp=1)
    A.cri = data.ScalarArray(ncomp=1)
    A.crs = data.ScalarArray(ncomp=1)


    if N == 2:

        eps = 0.00

        epsx = 0
        epsy = 0
        epsz = 0

        A.P[0,:] = (-0.0001, 0.0001, 1.0001)
        A.P[1,:] = (-0.0001, 0.0001,-0.0001)


        A.Q[0,0] = 1.
        A.Q[1,0] = 1.


    A.scatter_data_from(0)

    t0 = time.time()
    #phi_py = fmm._test_call(A.P, A.Q, execute_async=ASYNC)
    phi_py = fmm(A.P, A.Q, forces=A.F, execute_async=ASYNC)
    t1 = time.time()



    direct_forces = np.zeros((N, 3))

    if DIRECT:
        #print("WARNING 0-th PARTICLE ONLY")
        phi_direct = 0.0

        # compute phi from image and surrounding 26 cells

        for ix in range(N):

            phi_part = 0.0
            for jx in range(ix+1, N):
                rij = np.linalg.norm(A.P[jx,:] - A.P[ix,:])
                phi_direct += A.Q[ix, 0] * A.Q[jx, 0] /rij
                phi_part += A.Q[ix, 0] * A.Q[jx, 0] /rij

                direct_forces[ix,:] -= A.Q[ix, 0] * A.Q[jx, 0] * \
                                       (A.P[jx,:] - A.P[ix,:]) / (rij**3.)
                direct_forces[jx,:] += A.Q[ix, 0] * A.Q[jx, 0] * \
                                       (A.P[jx,:] - A.P[ix,:]) / (rij**3.)
            if free_space == '27':
                for ofx in cube_offsets:
                    cube_mid = np.array(ofx)*E
                    for jx in range(N):
                        rij = np.linalg.norm(A.P[jx,:] + cube_mid - A.P[ix, :])
                        phi_direct += 0.5*A.Q[ix, 0] * A.Q[jx, 0] /rij
                        phi_part += 0.5*A.Q[ix, 0] * A.Q[jx, 0] /rij

                        direct_forces[ix,:] -= A.Q[ix, 0] * A.Q[jx, 0] * \
                                           (A.P[jx,:] - A.P[ix,:] + cube_mid) \
                                               / (rij**3.)


    local_err = abs(phi_py - phi_direct)
    if local_err > eps: serr = red(local_err)
    else: serr = green(local_err)

    if MPIRANK == 0 and DEBUG:
        print("\n")
        #print(60*"-")
        #opt.print_profile()
        #print(60*"-")
        print("TIME FMM:\t", t1 - t0)
        print("ENERGY DIRECT:\t{:.20f}".format(phi_direct))
        print("ENERGY FMM:\t", phi_py)
        print("ERR:\t\t", serr)
    
    

    for px in range(N):
        cell = A._fmm_cell[px,0]
        stride = fmm.tree_plain[0].shape[-1]
        ss = fmm.tree_plain[R-1].shape[0:3:]

        cx = cell % ss[2]
        cy = ((cell - cx)//ss[2]) % ss[1]
        cz = (((cell - cx)//ss[2]) - cy)//ss[1]

        mom = fmm.tree_plain[fmm.R-1][cz, cy, cx, :]
        mid = (0.5*E/2.**(R-1))*np.ones(3) + (E/2.**(R-1))*np.array((cx, cy, cz)) - 0.5*E*np.ones(3)
        
        disp_cart = A.P[px,:] - mid
        disp = spherical(disp_cart)

        print(cell, "|", cx, cy, cz, "|", mid)


        fpy = force_from_multipole(mom, fmm, disp.reshape(1,3), A.Q[px,0])


        err_re_c = red_tol(np.linalg.norm(direct_forces[px,:] - A.F[px,:],
                                          ord=np.inf), 10.**-6)
        err_re_p = red_tol(np.linalg.norm(direct_forces[px,:] - fpy,
                                          ord=np.inf), 10.**-6)        


        print("PX:", px)
        print("\t\tFORCE DIR :",direct_forces[px,:])
        print("\t\tFORCE FMMC:",A.F[px,:], err_re_c)
        print("\t\tFORCE py  :",fpy, err_re_p)

    fmm.free()

def force_from_multipole(py_mom, fmm, disp, charge):

    Fv = np.zeros(3)
    radius = disp[0,0]
    theta = disp[0,1]
    phi = disp[0,2]

    rstheta = 1.0 / sin(theta)
    rhat = np.array((cos(phi)*sin(theta),
                    sin(phi)*sin(theta),
                    cos(theta)))

    thetahat = np.array(
        (cos(phi)*cos(theta),
         sin(phi)*cos(theta),
         -1.0*sin(theta))
    )
    

    print(radius, cos(theta), sin(theta), cos(phi), sin(phi))

    phihat = np.array((-1*sin(phi), cos(phi), 0.0))

    radius_coeff2 = 0.
    theta_coeff2 = 0.
    phi_coeff2 = 0.

    for jx in range(0, fmm.L):
        for kx in range(-1*jx, jx+1):

            rpower = radius**(jx-1.)

            Ljk = py_mom[fmm.re_lm(jx,kx)] + 1.j*py_mom[fmm.im_lm(jx,kx)]
            
            #print(Ljk)
            radius_coeff = float(jx) * rpower * \
                               Yfoo(jx, kx, theta, phi)

            # theta
            theta_coeff = float(jx - abs(kx) + 1) * \
                            Pfoo(jx+1, abs(kx), cos(theta))
            theta_coeff -= float(jx + 1) * cos(theta) * \
                            Pfoo(jx, abs(kx), cos(theta))
            theta_coeff *= rpower
            theta_coeff *= Hfoo(jx, kx) * cmath.exp(1.j * float(kx) * phi) * rstheta

            # phi
            phi_coeff = Yfoo(jx, kx, theta, phi) * (1.j * float(kx))
            phi_coeff *= rpower * rstheta
            
            radius_coeff2 += radius_coeff*Ljk
            theta_coeff2 += theta_coeff  *Ljk
            phi_coeff2 += phi_coeff      *Ljk
    

    radius_coeff2 *= charge
    theta_coeff2 *= charge
    phi_coeff2 *= charge
    radius_coeff2 =radius_coeff2.real
    theta_coeff2  =theta_coeff2.real
    phi_coeff2    =phi_coeff2.real


    print("radius", radius_coeff2.real)
    print("theta", theta_coeff2.real)
    print("phi", phi_coeff2.real)
    print("charge", charge)

    Fv[:] -= radius_coeff2 * rhat  + theta_coeff2 * thetahat + phi_coeff2 * phihat

    return Fv


