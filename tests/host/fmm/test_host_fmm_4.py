from __future__ import print_function, division

__author__ = "W.R.Saunders"
__copyright__ = "Copyright 2016, W.R.Saunders"

import pytest, ctypes, math
from mpi4py import MPI
import numpy as np

#from ppmd_vis import plot_spheres

import itertools


from ppmd import *
from ppmd.coulomb.fmm import *
from scipy.special import sph_harm, lpmv
import time


MPISIZE = MPI.COMM_WORLD.Get_size()
MPIRANK = MPI.COMM_WORLD.Get_rank()
MPIBARRIER = MPI.COMM_WORLD.Barrier
DEBUG = False

def red(input):
    try:
        from termcolor import colored
        return colored(input, 'red')
    except Exception as e: return input
def green(input):
    try:
        from termcolor import colored
        return colored(input, 'green')
    except Exception as e: return input
def yellow(input):
    try:
        from termcolor import colored
        return colored(input, 'yellow')
    except Exception as e: return input


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
    if type(xyz) is tuple:
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

    return sph

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
def test_fmm_init_4_1():

    offset = (20., 0., 0.)

    R = 3
    Ns = 2**(R-1)
    E = 10.

    A = state.State()
    A.domain = domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = domain.BoundaryTypePeriodic()

    eps = 10.**-2

    N = Ns**3
    fmm = PyFMM(domain=A.domain, r=R, eps=eps, free_space=True)

    #N = 3
    A.npart = N

    rng = np.random.RandomState(seed=1234)

    A.P = data.PositionDat(ncomp=3)
    A.Q = data.ParticleDat(ncomp=1)
    #A.P[:] = utility.lattice.cubic_lattice((Ns, Ns, Ns),
    #                                       (E, E, E))
    A.P[:] = rng.uniform(low=-0.499*E, high=0.499*E, size=(N,3))
    A.Q[:] = rng.uniform(low=-1.0, high=1.0, size=(N,1))

    #A.Q[::,0] = 1.
    #A.P[0, :] = (-3.75, -3.75, -3.75)
    #A.P[1, :] = (3.75, -3.75, 3.75)
    #A.P[2, :] = (3.75, 3.75, 3.75)

    # for last/first cube
    cube_width = E/fmm.tree[R-1].ncubes_side_global
    #A.P[0, :] = (-0.5*(E - cube_width), -0.5*(E - cube_width),
    #             -0.5*(E - cube_width))
    #A.P[1, :] = (0.5*(E - cube_width), 0.5*(E - cube_width),
    #             0.5*(E - cube_width))

    A.Q[:] = 1.0

    #bias = np.sum(A.Q[:])/N
    #A.Q[:] -= bias

    A.scatter_data_from(0)


    fmm._check_aux_dat(A.P)
    fmm._compute_cube_contrib(A.P, A.Q, A._fmm_cell)
    for level in range(fmm.R - 1, 0, -1):

        fmm._translate_m_to_m(level)
        fmm._halo_exchange(level)
        fmm._translate_m_to_l(level)
        fmm._fine_to_coarse(level)

        ls = fmm.tree[level].local_grid_cube_size
        cube_width = E/fmm.tree[level].ncubes_side_global


        for tx in tuple_it(ls):
        #for tx in [(0,0,1),]:
            txa = np.array(tx)
            txh = txa + 2

            mask = [tx[dx] % 2 for dx in range(3)]
            lin_mask = mask[2] + 2*mask[1] + 4*mask[0]

            #print("lin_mask", green(lin_mask))

            low = [-2 - mask[dx] for dx in range(3)]
            high = [4 - mask[dx] for dx in range(3)]

            ll = np.zeros_like(fmm.tree_halo[level][0, 0, 0, :])
            of_count = 0
            ofc_count = 0

            #print(low, high)

            for ofxi, ofx in enumerate(tuple_it(low=low, high=high)):
                radius = ofx[0]*ofx[0] + ofx[1]*ofx[1] + ofx[2]*ofx[2]
                if radius > 3:

                    lin_tx = txh[2] + (ls[2]+4)*(txh[1] + (ls[1]+4)*txh[0])
                    lin_off = ofx[2] + (ls[2]+4)*(ofx[1] + (ls[1]+4)*ofx[0])

                    of_count += 1

                    radius = radius ** 0.5
                    of = txh + ofx
                    lin_of = of[2] + (ls[2]+4)*(of[1] + (ls[1]+4)*of[0])

                    assert lin_tx + lin_off == lin_of, "{} + {} == {}".format(
                        lin_tx, lin_off, lin_of)

                    #print("of", of)
                    mm = fmm.tree_halo[level][of[0], of[1], of[2], :]

                    #if abs(mm[0]) > 0.0001:
                    #    print("mm[0]", ofx, green(mm[0]))

                    disp = cube_width * np.array(ofx)
                    disp_sph = spherical(np.array(((disp[2], disp[1], disp[0]),)))

                    p_array, exp_array = get_p_exp(fmm, disp_sph)

                    #if ofx[2] == 3 and ofx[1] == 3 and ofx[0] == 3:
                    #    print("disp radius", disp_sph[0])
                    #    print("p array", p_array[:], len(p_array))
                    #    print("exp array", exp_array[:], len(exp_array))


                    if abs(disp_sph[0,0] - radius*cube_width) > 10.**-10:
                        print(disp_sph[0,0], radius*cube_width)

                    moment = 1
                    llold = ll[moment]
                    fmm._translate_mtl_lib['mtl_test_wrapper'](
                        ctypes.c_int64(fmm.L),
                        ctypes.c_double(disp_sph[0, 0]),
                        extern_numpy_ptr(mm),
                        extern_numpy_ptr(exp_array),
                        extern_numpy_ptr(p_array),
                        extern_numpy_ptr(fmm._a),
                        extern_numpy_ptr(fmm._ar),
                        extern_numpy_ptr(fmm._ipower_mtl),
                        extern_numpy_ptr(ll)
                    )

                    #if abs(ll[moment] - llold) > 10.**-6: llg = green(ll[moment])
                    #else: llg = ll[moment]
                    #print(level, "\t",lin_off,"\t",ofx,"\t",llg,"\t",llold, "\t",
                    #      disp_sph[0])

                else: ofc_count += 1#; print("CLOSE", ofx)

            assert ofc_count == 27
            assert of_count == 189


            eps2 = 10.**-10
            for ax in range(2*fmm.L**2):
                err = abs(ll[ax] - fmm.tree_plain[level][tx[0], tx[1], tx[2],ax])
                if err > eps2:
                #if True:
                    print(tx, ax, "err", red(err), ll[ax],
                          fmm.tree_plain[level][tx[0], tx[1], tx[2],ax])
                assert err < eps2

            #print("P", ll)
            #print("C", fmm.tree_plain[level][tx[2], tx[1], tx[0],:])

    fmm.free()


@pytest.mark.skipif("MPISIZE>1")
def test_fmm_init_4_2():

    R = 3
    Ns = 2**(R-1)
    E = 10.

    SKIP_MTL = False

    A = state.State()
    A.domain = domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = domain.BoundaryTypePeriodic()

    eps = 10.**-2
    eps2 = 10.**-3

    N = Ns**3
    fmm = PyFMM(domain=A.domain, r=R, eps=eps, free_space=True)

    N = 2
    A.npart = N


    rng = np.random.RandomState(seed=1234)

    A.P = data.PositionDat(ncomp=3)
    A.Q = data.ParticleDat(ncomp=1)
    #A.P[:] = utility.lattice.cubic_lattice((Ns, Ns, Ns),
    #                                       (E, E, E))
    A.P[:] = rng.uniform(low=-0.499*E, high=0.499*E, size=(N,3))
    A.Q[:] = rng.uniform(low=-1.0, high=1.0, size=(N,1))

    #A.Q[::,0] = 1.
    #A.P[0, :] = (-3.75, -3.75, -3.75)
    #A.P[1, :] = (3.75, -3.75, 3.75)
    #A.P[2, :] = (3.75, 3.75, 3.75)

    # for last/first cube
    cube_width = E/fmm.tree[R-1].ncubes_side_global
    #A.P[0, :] = (-0.5*(E - cube_width), -0.5*(E - cube_width),
    #             -0.5*(E - cube_width))
    #A.P[1, :] = (0.5*(E - cube_width), 0.5*(E - cube_width),
    #             0.5*(E - cube_width))

    A.Q[:] = 1.0

    #bias = np.sum(A.Q[:])/N
    #A.Q[:] -= bias

    A.scatter_data_from(0)


    ### FAR PHI START ####
    far_away = np.array((1.5*E, 1.5*E, 1.5*E))
    src = """
    const double d0 = P.i[0] - POINT[0];
    const double d1 = P.i[1] - POINT[1];
    const double d2 = P.i[2] - POINT[2];
    phi[0] += Q.i[0] / sqrt(d0*d0 + d1*d1 + d2*d2);
    """
    far_phi_kernel = kernel.Kernel('point_phi', src,
                               headers=(kernel.Header('math.h'),))
    far_phi_ga = data.GlobalArray(ncomp=1, dtype=ctypes.c_double)
    far_point_sa = data.ScalarArray(ncomp=3, dtype=ctypes.c_double)
    far_point_sa[:] = far_away
    far_phi_loop = loop.ParticleLoopOMP(kernel=far_phi_kernel,
                                        dat_dict={
        'P': A.P(access.READ),
        'Q': A.Q(access.READ),
        'POINT': far_point_sa(access.READ),
        'phi': far_phi_ga(access.INC_ZERO)
    })
    far_phi_loop.execute()
    far_phi = far_phi_ga[0]
    ### FAR PHI END ###


    ### LOCAL PHI START ###
    # compute potential energy to point across all charges directly
    P2 = data.PositionDat(npart=N, ncomp=3)
    Q2 = data.ParticleDat(npart=N, ncomp=1)
    P2[:,:] = A.P[:N:,:]
    Q2[:,:] = A.Q[:N:,:]
    local_phi_ga = data.ScalarArray(ncomp=1, dtype=ctypes.c_double)
    src = """
    const double d0 = P.j[0] - P.i[0];
    const double d1 = P.j[1] - P.i[1];
    const double d2 = P.j[2] - P.i[2];
    phi[0] += 0.5 * Q.i[0] * Q.j[0] / sqrt(d0*d0 + d1*d1 + d2*d2);
    """
    local_phi_kernel = kernel.Kernel('all_to_all_phi', src,
                               headers=(kernel.Header('math.h'),))


    local_phi_loop = pairloop.AllToAllNS(kernel=local_phi_kernel,
                       dat_dict={'P': P2(access.READ),
                                 'Q': Q2(access.READ),
                                 'phi': local_phi_ga(access.INC_ZERO)})
    local_phi_loop.execute()
    local_phi_direct = local_phi_ga[0]
    ### LOCAL PHI END ###


    fmm._check_aux_dat(A.P)
    fmm._compute_cube_contrib(A.P, A.Q, A._fmm_cell)
    for level in range(fmm.R - 1, 0, -1):
        fmm._halo_exchange(level)
        fmm._translate_m_to_l(level)
        fmm._translate_m_to_m(level)
        fmm._fine_to_coarse(level)

        ls = fmm.tree[level].local_grid_cube_size
        lo = fmm.tree[level].local_grid_offset

        cube_width = E/fmm.tree[level].ncubes_side_global
        first_cube = -0.5*E + 0.5*cube_width

        parent_cube_width = 2. * E /fmm.tree[level].ncubes_side_global
        parent_first_cube = -0.5*E + 0.5*parent_cube_width

        #### MM EVAL START PARENT ####
        phi_sph_re = 0.0
        phi_sph_im = 0.0
        for momx in tuple_it((ls[0]//2, ls[1]//2, ls[2]//2)):

            center = np.array(
                (parent_first_cube + (lo[2]//2 + momx[2])*parent_cube_width,
                 parent_first_cube + (lo[1]//2 + momx[1])*parent_cube_width,
                 parent_first_cube + (lo[0]//2 + momx[0])*parent_cube_width))

            disp = far_away - center
            moments = fmm.tree_parent[level][
                      momx[0], momx[1], momx[2], :]
            disp_sph = spherical(np.reshape(disp, (1, 3)))

            phi_sph_re1, phi_sph_im1 = compute_phi(fmm.L, moments,
                                                   disp_sph)
            phi_sph_re += phi_sph_re1
            phi_sph_im += phi_sph_im1

        err = abs(phi_sph_re - far_phi)
        assert err < eps2
        if DEBUG:
            if err > eps2: serr = red(err)
            else: serr = green(err)
            print("LEVEL", level, "MM (PARENT) EVAL ERR:", serr, green(far_phi), phi_sph_re)
        #### MM EVAL END PARENT ####

        #### MM EVAL START CHILD ####
        phi_sph_re = 0.0
        phi_sph_im = 0.0
        for momx in tuple_it((ls[0], ls[1], ls[2])):

            center = np.array(
                (first_cube + (lo[2] + momx[2])*cube_width,
                 first_cube + (lo[1] + momx[1])*cube_width,
                 first_cube + (lo[0] + momx[0])*cube_width))

            disp = far_away - center
            moments = fmm.tree_halo[level][
                      2+momx[0], 2+momx[1], 2+momx[2], :]
            disp_sph = spherical(np.reshape(disp, (1, 3)))

            phi_sph_re1, phi_sph_im1 = compute_phi(fmm.L, moments,
                                                   disp_sph)
            phi_sph_re += phi_sph_re1
            phi_sph_im += phi_sph_im1

        err = abs(phi_sph_re - far_phi)

        assert err < eps2
        if DEBUG:
            if err > eps2: serr = red(err)
            else: serr = green(err)
            print("LEVEL", level, "MM (CHILD) EVAL ERR:", serr, green(far_phi), phi_sph_re)
        #### MM EVAL END CHILD ####

        ##### MTL LOOP START ####
        if not SKIP_MTL:
            for tx in tuple_it(ls):
            #for tx in [(0,0,1),]:
                txa = np.array(tx)
                txh = txa + 2

                mask = [tx[dx] % 2 for dx in range(3)]
                lin_mask = mask[2] + 2*mask[1] + 4*mask[0]

                low = [-2 - mask[dx] for dx in range(3)]
                high = [4 - mask[dx] for dx in range(3)]

                ll = np.zeros_like(fmm.tree_halo[level][0, 0, 0, :])
                of_count = 0
                ofc_count = 0

                for ofxi, ofx in enumerate(tuple_it(low=low, high=high)):
                    radius = ofx[0]*ofx[0] + ofx[1]*ofx[1] + ofx[2]*ofx[2]
                    if radius > 3:

                        lin_tx = txh[2] + (ls[2]+4)*(txh[1] + (ls[1]+4)*txh[0])
                        lin_off = ofx[2] + (ls[2]+4)*(ofx[1] + (ls[1]+4)*ofx[0])

                        of_count += 1

                        radius = radius ** 0.5
                        of = txh + ofx
                        lin_of = of[2] + (ls[2]+4)*(of[1] + (ls[1]+4)*of[0])

                        assert lin_tx + lin_off == lin_of, "{} + {} == {}".format(
                            lin_tx, lin_off, lin_of)

                        #print("of", of)
                        mm = fmm.tree_halo[level][of[0], of[1], of[2], :]

                        #if abs(mm[0]) > 0.0001:
                        #    print("mm[0]", ofx, green(mm[0]))

                        disp = cube_width * np.array(ofx)
                        disp_sph = spherical(np.array(((disp[2], disp[1], disp[0]),)))

                        p_array, exp_array = get_p_exp(fmm, disp_sph)

                        moment = 1
                        llold = ll[moment]
                        fmm._translate_mtl_lib['mtl_test_wrapper'](
                            ctypes.c_int64(fmm.L),
                            ctypes.c_double(disp_sph[0, 0]),
                            extern_numpy_ptr(mm),
                            extern_numpy_ptr(exp_array),
                            extern_numpy_ptr(p_array),
                            extern_numpy_ptr(fmm._a),
                            extern_numpy_ptr(fmm._ar),
                            extern_numpy_ptr(fmm._ipower_mtl),
                            extern_numpy_ptr(ll)
                        )

                        #if abs(ll[moment] - llold) > 10.**-6: llg = green(ll[moment])
                        #else: llg = ll[moment]
                        #print(lin_off,"\t",ofx,"\t",llg,"\t",llold, "\t",
                        #      disp_sph[0])

                    else: ofc_count += 1#; print("CLOSE", ofx)

                assert ofc_count == 27
                assert of_count == 189

                for ax in range(2*fmm.L**2):
                    err = abs(ll[ax] - fmm.tree_plain[level][tx[0], tx[1], tx[2],ax])
                    if err > eps2:
                        print(tx, ax, "err", red(err), ll[ax],
                              fmm.tree_plain[level][tx[0], tx[1], tx[2],ax])

                    assert err < eps

    fmm.free()



def test_fmm_init_4_3():

    R = 4
    Ns = 2**(R-1)
    Ns = 20
    E = 3.*Ns

    SKIP_DIRECT = False
    ASYNC = False

    A = state.State()
    A.domain = domain.BaseDomainHalo(extent=(E,E,E))
    A.domain.boundary_condition = domain.BoundaryTypePeriodic()

    eps = 10.**-2
    eps2 = 10.**-3

    N = Ns**3
    fmm = PyFMM(domain=A.domain, r=R, eps=eps, free_space=True)

    #N = 2
    A.npart = N

    rng = np.random.RandomState(seed=1234)

    A.P = data.PositionDat(ncomp=3)
    A.Q = data.ParticleDat(ncomp=1)
    A.P[:] = utility.lattice.cubic_lattice((Ns, Ns, Ns),
                                           (E, E, E))
    #A.P[:] = rng.uniform(low=-0.499*E, high=0.499*E, size=(N,3))
    A.Q[:] = rng.uniform(low=-1.0, high=1.0, size=(N,1))

    A.Q[::,0] = .1
    #A.P[0, :] = (-3.75, -3.75, -3.75)
    #A.P[1, :] = (3.75, -3.75, 3.75)
    #A.P[2, :] = (3.75, 3.75, 3.75)

    # for last/first cube
    cube_width = E/fmm.tree[R-1].ncubes_side_global
    #A.P[0, :] = (-0.5*(E - cube_width), -0.5*(E - cube_width),
    #             -0.5*(E - cube_width))
    #A.P[1, :] = (0.5*(E - cube_width), 0.5*(E - cube_width),
    #             0.5*(E - cube_width))

    #bias = np.sum(A.Q[:])/N
    #A.Q[:] -= bias

    if MPIRANK == 0 and DEBUG:
        print("N", N, "L", fmm.L, "R", fmm.R)

    if not SKIP_DIRECT:
        ### LOCAL PHI START ###
        # compute potential energy to point across all charges directly
        P2 = data.PositionDat(npart=N, ncomp=3)
        Q2 = data.ParticleDat(npart=N, ncomp=1)
        if MPIRANK == 0:
            P2[:,:] = A.P[:N:,:]
            Q2[:,:] = A.Q[:N:,:]
        else:
            P2[:,:] = 0
            Q2[:,:] = 0

        local_phi_ga = data.ScalarArray(ncomp=1, dtype=ctypes.c_double)
        src = """
        const double d0 = P.j[0] - P.i[0];
        const double d1 = P.j[1] - P.i[1];
        const double d2 = P.j[2] - P.i[2];
        phi[0] += 0.5 * Q.i[0] * Q.j[0] / sqrt(d0*d0 + d1*d1 + d2*d2);
        """
        local_phi_kernel = kernel.Kernel('all_to_all_phi', src,
                                   headers=(kernel.Header('math.h'),))

        # TODO THIS IS NOT COLLECTIVE!
        local_phi_loop = pairloop.AllToAllNS(kernel=local_phi_kernel,
                           dat_dict={'P': P2(access.READ),
                                     'Q': Q2(access.READ),
                                     'phi': local_phi_ga(access.INC_ZERO)})

        if MPIRANK == 0:
            call_n = N
        else:
            call_n = 0

        local_phi_loop.execute(n=call_n)
        local_phi_direct = local_phi_ga[0]
        if DEBUG:
            print("local_phi {:.30f}".format(float(local_phi_direct)))
    else:
        local_phi_direct = 0.0

    local_phi_direct =  mpi.all_reduce(np.array([local_phi_direct]))[0]

    A.scatter_data_from(0)


    t0 = time.time()
    phi_py = fmm(A.P, A.Q, execute_async=ASYNC)
    t1 = time.time()

    local_err = abs(phi_py - local_phi_direct)

    assert local_err < eps

    if local_err > eps: serr = red(local_err)
    else: serr = yellow(local_err)

    if MPIRANK == 0 and DEBUG:
        print(60*"-")
        opt.print_profile()
        print(60*"-")
        print("TIME:", t1 - t0)
        print("LOCAL PHI ERR:", serr, phi_py, green(local_phi_direct))


    fmm.free()













