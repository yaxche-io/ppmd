#!/usr/bin/python

import ctypes
import numpy as np


import ppmd as md

N = 1000

rank = md.mpi.MPI.COMM_WORLD.Get_rank()
barrier = md.mpi.MPI.COMM_WORLD.Barrier


PositionDat = md.data.PositionDat
ParticleDat = md.data.ParticleDat
ScalarArray = md.data.ScalarArray


def test_host_all_to_all_NS():

    md.runtime.BUILD_PER_PROC = True
    if rank == 0:
        A = ParticleDat(
            npart=1000,
            ncomp=1,
            dtype=ctypes.c_int64
        )
        B = ParticleDat(
            npart=1000,
            ncomp=1,
            dtype=ctypes.c_int64
        )


        A[:,0] = np.arange(N)
        B[:] = 0

        k = md.kernel.Kernel(
            'AllToAll_1',
            '''
            B.i[0] += A.j[0];
            '''
        )

        p1 = md.pairloop.AllToAllNS(
            kernel=k,
            dat_dict={
                'A': A(md.access.R),
                'B': B(md.access.W)
                }
        )

        p1.execute()


        # check output
        sum = np.sum(np.arange(N))
        C = sum - np.arange(N)

        for i in range(N):
            assert B[i] == C[i]

    barrier()
    md.runtime.BUILD_PER_PROC = False
    barrier()

def test_host_all_to_all():

    md.runtime.BUILD_PER_PROC = True
    if rank == 0:
        A = ParticleDat(
            npart=1000,
            ncomp=1,
            dtype=ctypes.c_int64
        )
        B = ParticleDat(
            npart=1000,
            ncomp=1,
            dtype=ctypes.c_int64
        )

        A[:,0] = np.arange(N)
        B[:] = 0

        k = md.kernel.Kernel(
            'AllToAll_1',
            '''
            B.i[0] += A.j[0];
            B.j[0] += A.i[0];
            '''
        )


        p1 = md.pairloop.AllToAll(
            kernel=k,
            dat_dict={
                'A': A(md.access.R),
                'B': B(md.access.W)
                }
        )

        p1.execute()


        # check output
        sum = np.sum(np.arange(N))
        C = sum - np.arange(N)

        for i in range(N):
            assert B[i] == C[i]


    barrier()
    md.runtime.BUILD_PER_PROC = False
    barrier()
