"""
Methods for Coulombic forces and energies.
"""

__author__ = "W.R.Saunders"
__copyright__ = "Copyright 2016, W.R.Saunders"
__license__ = "GPL"

from math import sqrt, log, ceil, pi, exp, cos, sin
import numpy as np
import ctypes
import  build
import runtime

class CoulombicEnergy(object):

    def __init__(self, domain, eps=10.**-6, real_cutoff=10.):
        self.domain = domain
        self.eps = float(eps)
        self.real_cutoff = float(real_cutoff)

        tau = sqrt(abs(log(eps * self.real_cutoff)))
        alpha = sqrt(abs(log(eps*real_cutoff*tau)))*(1.0/real_cutoff)
        tau1 = sqrt(abs(log(eps*self.real_cutoff*(2.*tau*alpha)**2)))
        

        # these parts are specific to the orthongonal box
        extent = self.domain.extent
        lx = (extent[0], 0., 0.)
        ly = (0., extent[1], 0.)
        lz = (0., 0., extent[2])
        ivolume = 1./np.dot(lx, np.cross(ly, lz))
        
        gx = np.cross(ly,lz)*ivolume
        gy = np.cross(lz,lx)*ivolume
        gz = np.cross(lx,ly)*ivolume

        nmax_x = ceil(0.25 + np.linalg.norm(gx, ord=2)*alpha*tau1/pi)
        nmax_y = ceil(0.25 + np.linalg.norm(gy, ord=2)*alpha*tau1/pi)
        nmax_z = ceil(0.25 + np.linalg.norm(gz, ord=2)*alpha*tau1/pi)
        

        print 'These nmax values seem too low'
        print eps, tau, tau1, alpha
        print 0.25 + np.linalg.norm(gx, ord=2)*alpha*tau1/pi
        print 0.25 + np.linalg.norm(gx, ord=2)*alpha*tau/pi
        print gx, gy, gz
        print 'nmax:', nmax_x, nmax_y, nmax_z


        print 'Taking tau1 to give nmax*20 until fixed....'
        nmax_x = int(ceil(tau1))*1
        nmax_y = int(ceil(tau1))*1
        nmax_z = int(ceil(tau1))*1

        print 'nmax:', nmax_x, nmax_y, nmax_z
        
        # find shortest nmax_i * gi
        gxl = np.linalg.norm(gx)
        gyl = np.linalg.norm(gy)
        gzl = np.linalg.norm(gz)
        max_len = min(
            gxl*float(nmax_x),
            gyl*float(nmax_y),
            gzl*float(nmax_z)
        )

        print "recip vector lengths", gxl, gyl, gzl

        nmax_x = int(ceil(max_len/gxl))
        nmax_y = int(ceil(max_len/gyl))
        nmax_z = int(ceil(max_len/gzl))

        print 'min reciprocal vector len:', max_len
        nmax_t = max(nmax_x, nmax_y, nmax_z)
        print "nmax_t", nmax_t

        # define persistent vars
        self._vars = {}
        self._vars['alpha']           = ctypes.c_double(alpha)
        self._vars['max_recip']       = ctypes.c_double(max_len)
        self._vars['nmax_vec']        = np.array((nmax_x, nmax_y, nmax_z), dtype=ctypes.c_int)
        self._vars['recip_vec']       = np.zeros((3,3), dtype=ctypes.c_double)
        self._vars['recip_vec'][0, :] = gx
        self._vars['recip_vec'][1, :] = gy
        self._vars['recip_vec'][2, :] = gz
        # Again specific to orthogonal domains
        self._vars['recip_consts'] = np.zeros(3, dtype=ctypes.c_double)
        self._vars['recip_consts'][0] = exp((-1./(4.*alpha)) * (gx[0]**2.) )
        self._vars['recip_consts'][1] = exp((-1./(4.*alpha)) * (gy[1]**2.) )
        self._vars['recip_consts'][2] = exp((-1./(4.*alpha)) * (gz[2]**2.) )
        
        # pass stride in tmp space vector
        self._vars['recip_axis_len'] = ctypes.c_int(nmax_t)
        # tmp space vector
        self._vars['recip_axis'] = np.zeros((2,2*nmax_t+1,3), dtype=ctypes.c_double)
        # recpirocal space
        self._vars['recip_space'] = np.zeros((2, 2*nmax_x+1, 2*nmax_y+1, 2*nmax_z+1), dtype=ctypes.c_double)



        with open(str(runtime.LIB_DIR) + '/CoulombicEnergyOrthSource.h','r') as fh:
            header = fh.read()

        with open(str(runtime.LIB_DIR) + '/CoulombicEnergyOrthSource.cpp','r') as fh:
            source = fh.read()

        self._lib = build.simple_lib_creator(header, source, 'CoulombicEnergyOrth')


    @staticmethod
    def _COMP_EXP_PACKED(x, gh):
        gh[0] = cos(x)
        gh[1] = sin(x)

    @staticmethod
    def _COMP_AB_PACKED(a,x,gh):
        gh[0] = a[0]*x[0] - a[1]*x[1]
        gh[1] = a[0]*x[1] + a[1]*x[0]

    @staticmethod
    def _COMP_ABC_PACKED(a,x,k,gh):

        axmby = a[0]*x[0] - a[1]*x[1]
        xbpay = a[0]*x[1] + a[1]*x[0]

        gh[0] = axmby*k[0] - xbpay*k[1]
        gh[1] = axmby*k[1] + xbpay*k[0]


    def evaluate_python(self, positions):
        # python version for sanity

        np.set_printoptions(linewidth=180)

        N_LOCAL = positions.npart_local

        recip_axis = self._vars['recip_axis']
        recip_vec = self._vars['recip_vec']
        recip_axis_len = self._vars['recip_axis_len'].value
        nmax_vec = self._vars['nmax_vec']
        recip_space = self._vars['recip_space']

        print "recip_axis_len", recip_axis_len

        recip_space[:] = 0.0

        for lx in range(N_LOCAL):
            print 60*'-'
            print positions[lx, :]

            for dx in range(3):

                gi = recip_vec[dx,dx]
                ri = positions[lx, dx]*gi

                # unit at middle as exp(0) = 1+0i
                recip_axis[:, recip_axis_len, dx] = (1.,0.)


                # first element along each axis
                self._COMP_EXP_PACKED(
                    ri,
                    recip_axis[:, recip_axis_len+1, dx]
                )


                base_el = recip_axis[:, recip_axis_len+1, dx]
                recip_axis[0, recip_axis_len-1, dx] = base_el[0]
                recip_axis[1, recip_axis_len-1, dx] = -1. * base_el[1]



                # +ve part
                for ex in range(2+recip_axis_len, nmax_vec[dx]+recip_axis_len+1):
                    self._COMP_AB_PACKED(
                        base_el,
                        recip_axis[:,ex-1,dx],
                        recip_axis[:,ex,dx]
                    )

                # rest of axis
                for ex in range(recip_axis_len-1):
                    recip_axis[0,recip_axis_len-2-ex,dx] = recip_axis[0,recip_axis_len+2+ex,dx]
                    recip_axis[1,recip_axis_len-2-ex,dx] = -1. * recip_axis[1,recip_axis_len+2+ex,dx]

                print "\t", ri,2*"\n","re", recip_axis[0,:,dx], "\nim", recip_axis[1,:,dx]

            # now calculate the contributions to all of recip space
            tmp = np.zeros(2, dtype=ctypes.c_double)
            for rz in xrange(2*nmax_vec[2]+1):
                for ry in xrange(2*nmax_vec[1]+1):
                    for rx in xrange(2*nmax_vec[0]+1):
                        tmp[:] = 0.0
                        self._COMP_ABC_PACKED(
                            recip_axis[:,rx,0],
                            recip_axis[:,ry,1],
                            recip_axis[:,rz,2],
                            tmp[:]
                        )
                        recip_space[:,rx,ry,rz] += tmp[:]




        print 60*"="
        print recip_space[:]








































