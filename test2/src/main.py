#!/usr/bin/python

import domain
import potential
import state

if __name__ == '__main__':
    
    
    print "test MD"
    
    N=1000
    rho = 1
    
    print rho
    
    test_domain = domain.BaseDomain()
    test_potential = potential.LennardJonesShifted()
    
    test_init_lattice = state.LatticeInitNRho(N, rho)
    
    test_state = state.BaseMDState(test_domain, test_potential, test_init_lattice, N)
    
    
    
    
    
    #test_state.frame_plot()
    
    
    
    
    
    
    
    
