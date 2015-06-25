#!/usr/bin/python

import domain
import potential
import state
import numpy as np
import math
import method
import data
import loop
import subprocess
import os

if __name__ == '__main__':

    MPI_HANDLE = data.MDMPI()

    #plot as computing + at end?
    plotting = False
    
    #log energy?
    logging = True
    
    #Enbale debug flags?
    debug = True   
    
    
    
    #particle properties
    N       = 10**3
    mass    = 39.948        #g/mol is this the correct mass?
    
    #potential properties
    epsilon = 0.9661
    sigma   = 3.405
    cutoff  = 7.5
    
    
    domain                  = domain.BaseDomainHalo(MPI_handle = MPI_HANDLE)
    potential               = potential.LennardJones(epsilon,sigma,cutoff)
    
    #initial_position_config = state.PosInitDLPOLYConfig('TEST7_CUSTOM/CONFIG')
    #initial_velocity_config = state.VelInitDLPOLYConfig('TEST7_CUSTOM/CONFIG')
    
    initial_position_config = state.PosInitDLPOLYConfig('../util/REVCON')
    initial_velocity_config = state.VelInitDLPOLYConfig('../util/REVCON')    
    
    intial_mass_config      = state.MassInitIdentical(mass)
    
    
    
    
    test_state = state.BaseMDStateHalo(domain = domain,
                                       potential = potential, 
                                       particle_pos_init = initial_position_config, 
                                       particle_vel_init = initial_velocity_config,
                                       particle_mass_init = intial_mass_config,
                                       N = N,
                                       DEBUG = debug,
                                       MPI_handle = MPI_HANDLE
                                       )
    
    
    
    
    
    
    
    
    #plotting handle
    if (plotting):
        plothandle = data.DrawParticles(interval = 25, MPI_handle = MPI_HANDLE)
    else:
        plothandle = None
    
    #energy handle
    if (logging):
        energyhandle = data.BasicEnergyStore(MPI_handle = MPI_HANDLE)
    else:
        energyhandle = None
    
    
    
    
    
    
    integrator = method.VelocityVerletAnderson(state = test_state, USE_C = True, plot_handle = plothandle, energy_handle = energyhandle, writexyz = False, DEBUG = debug, MPI_handle = MPI_HANDLE)
    
    
    #control file seems to compute 16000 iterations at dt =10^-3, 1000 to equbrilate then 15k for averaging?
    dt=10**-3
    T=5000*dt
    integrator.integrate(dt = dt, T = T, timer=True)
    
    print test_state.positions[0,::]
    print test_state.velocities[0,::]    
    print test_state.forces[0,::]  
    
    if (MPI_HANDLE.rank ==0):
        print "Total time in halo exchange:", domain.halos._time
        print "Time in forces_update:", test_state._time    
    
    
    
    
    
    
    
    
    
    
    if (logging):
        energyhandle.plot()
    
    
    a=input("PRESS ENTER TO CONTINUE.\n")
    
