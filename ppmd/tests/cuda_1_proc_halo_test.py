import numpy as np
import ctypes

from ppmd import *
from ppmd.cuda import *



# n=25 reasonable size
n = 10
N = n**3
# n=860
rho = 1.
mu = 1.0
nsig = 5.0

# Initialise basic domain
test_domain = domain.BaseDomainHalo()

# Initialise LJ potential
test_potential = potential.LennardJones(sigma=1.0,epsilon=1.0)

test_pos_init = simulation.PosInitLatticeNRhoRand(N,rho,0.,None)

test_vel_init = simulation.VelInitNormDist(mu,nsig)

test_mass_init = simulation.MassInitIdentical(1.)


sim1 = simulation.BaseMDSimulation(domain_in=test_domain,
                                   potential_in=test_potential,
                                   particle_pos_init=test_pos_init,
                                   particle_vel_init=test_vel_init,
                                   particle_mass_init=test_mass_init,
                                   n=N
                                   )

COM = cuda_cell.CellOccupancyMatrix()

# Create a particle dat with the positions in from the sim1.state
sim1.state.d_positions = cuda_data.ParticleDat(initial_value=sim1.state.positions.dat, name='positions')


COM.setup(sim1.state.as_func('n'), sim1.state.d_positions, sim1.state.domain)

COM.sort()
cuda_halo.HALOS = cuda_halo.CartesianHalo(COM)


sim1.state.d_positions.halo_exchange()







