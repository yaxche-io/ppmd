from __future__ import print_function, division, absolute_import

__author__ = "W.R.Saunders"
__copyright__ = "Copyright 2016, W.R.Saunders"

import itertools, ctypes
import numpy as np

class cube_owner_map(object):
    """
    Compute the global map from cube index (lexicographic) to owning MPI rank
    and map to MPI ranks with sub-domains of non-empty intersection with each
    cube.
    
    Assumes that in each dimension ranks are assigned equal shares of the 
    domain.
    
    :param cart_comm: MPI cartesian communicator.
    :param cube_side_count: Integer subdivision level of domain.
    """
    def __init__(self, cart_comm, cube_side_count):

        self.cart_comm = cart_comm
        """Cartesian communicator used"""
        topo = self.cart_comm.Get_topo()
        dims= topo[0] # dim order here is z, y, x

        self.cube_count = cube_side_count**len(dims)
        """Total number of cubes"""
        self.cube_side_count = cube_side_count
        """Side count of octal tree on domain"""

        owners, contribs = self.compute_grid_ownership(dims, cube_side_count)
        cube_to_mpi = self.compute_map_product_owners(cart_comm, owners)
        starts, con_ranks, send_ranks = self.compute_map_product_contribs(cart_comm,
            cube_to_mpi, contribs)

        self.cube_to_mpi = cube_to_mpi
        """Array from cube global index to owning mpi rank"""
        self.contrib_mpi = con_ranks
        """Array containing ranks contributing to a cube"""
        self.contrib_starts = starts
        """Cube i has contributing coeffients from ranks x_s_i to x_s_{i-1}
        where s is contrib_starts and x is contrib_mpi"""
        self.cube_to_send = send_ranks
        """Array if this mpi rank contributes to cube i then x_i is owning
        rank of cube i else x_i = -1"""


    @staticmethod
    def compute_grid_ownership(dims, cube_side_count):
        """
        For each dimension compute the owner and contributing ranks. Does
        not perform out product to compute the full map.
        :param dims: tuple of mpi dims.
        :param cube_side_count: int, number of cubes in each dimension
        :return: tuple: ranks of each cube owner, contributing ranks.
        """

        ndim = len(dims)
        oocsc = 1.0 / cube_side_count
        hoocsc = 0.5 / cube_side_count
        cube_mids = [ hoocsc + oocsc*ix for ix in range(cube_side_count) ]
        cube_lower_edge = lambda x: x - hoocsc
        cube_upper_edge = lambda x: x + hoocsc

        dim_owners = [[-1 for iy in range(cube_side_count)] for
                      ix in range(ndim)]

        dim_contribs = [[[] for iy in range(cube_side_count) ] for
                        ix in range(ndim)]

        for dx in range(ndim):
            lbound = lambda argx: float(argx)/dims[dx]
            ubound = lambda argx: float(argx+1)/dims[dx]
            for mx in range(dims[dx]):
                for cx, cmid in enumerate(cube_mids):
                    if (lbound(mx) <= cmid) and (cmid < ubound(mx)):
                        # this rank is the cube's unique owner
                        dim_owners[dx][cx] = mx

                    if (ubound(mx) > cube_lower_edge(cmid)) and \
                            (lbound(mx) < cube_upper_edge(cmid)):
                        # this rank's subdomain intersects the cube's lower
                        # bound
                        dim_contribs[dx][cx].append(mx)

                    elif (lbound(mx) < cube_upper_edge(cmid)) and \
                            (ubound(mx) > cube_lower_edge(cmid)):
                        # rank intersects cube's upper edge
                        dim_contribs[dx][cx].append(mx)

        # dim owner orders is z dim then y dim ...
        return dim_owners, dim_contribs


    @staticmethod
    def compute_map_product_owners(cart_comm, dim_owners):
        """
        Compute the full map from cube index to mpi rank owner.
        :param: MPI cart_comm to use for logical coord to rank conversion.
        :param dim_owners: ndims x cube_side_count tuple representing cube to 
        owner map per dimension, elements are ints.
        lists of contributors.
        :return: array, length number of cubes, cube global index to mpi rank
        owner.
        """
        # domain is a cube therefore we can inspect one dimension
        ncubes_per_side = len(dim_owners[0])
        ndim = len(dim_owners)
        ncubes = ncubes_per_side**ndim
        iterset = [range(ncubes_per_side) for i in range(ndim)]
        cube_to_mpi = np.zeros(ncubes, dtype=ctypes.c_uint64)

        tuple_to_lin_coeff = [
            ncubes_per_side**(ndim-dx-1) for dx in range(ndim)]

        # should convert an z,y,x tuple to lexicographic linear index
        cube_tuple_to_lin = lambda X: sum([i[0]*i[1] for i in zip(
            X,tuple_to_lin_coeff)])

        # loop over cube indexes
        for cube_tuple in itertools.product(*iterset):
            cx = cube_tuple_to_lin(cube_tuple)
            ompi = cart_comm.Get_cart_rank([
                dim_owners[i][cube_tuple[i]] for i in range(ndim)])
            cube_to_mpi[cx] = ompi

        return cube_to_mpi

    @staticmethod
    def compute_map_product_contribs(cart_comm, cube_to_mpi, dim_contribs):
        """
        Compute the full map from cube index to mpi rank owner, cube index to
        mpi ranks of contributors.
        :param: MPI cart_comm to use for logical coord to rank conversion.
        owner map per dimension, elements are ints.
        :param cube_to_mpi: ndims x cube_side_count tuple representing cube to 
        owner map per dimension, elements are ints.        
        :param dim_contribs: tuple ndims x cube_side_count tuple containing
        lists of contributors.
        :return: 
        """
        ncubes_per_side = len(dim_contribs[0])
        ndim = len(dim_contribs)
        my_rank = cart_comm.Get_rank()

        # duplicate function (makes testing easier)
        tuple_to_lin_coeff = [
            ncubes_per_side**(ndim-dx-1) for dx in range(ndim)]

        # should convert an z,y,x tuple to lexicographic linear index
        cube_tuple_to_lin = lambda X: sum([i[0]*i[1] for i in zip(
            X,tuple_to_lin_coeff)])

        # loop over the cubes, then loop over contributors and add to contrib
        # list if contributing mpi rank is not owning rank.

        curr_start = 0
        starts = np.zeros(ncubes_per_side**ndim + 1, dtype=ctypes.c_uint64)
        con_ranks = list()
        send_ranks = np.zeros(ncubes_per_side**ndim, dtype=ctypes.c_int64)
        send_ranks[:] = -1

        iterset = [range(ncubes_per_side) for i in range(ndim)]
        for ctx in itertools.product(*iterset):
            cx = cube_tuple_to_lin(ctx)
            owner = cube_to_mpi[cx]

            # loop over contributing ranks
            for con in itertools.product(
                    *[dim_contribs[i][j] for i, j in enumerate(ctx)]):
                con_rank = cart_comm.Get_cart_rank(con)

                # build list this rank sends to
                if con_rank != owner:
                    if con_rank == my_rank:
                        send_ranks[cx] = owner
                    elif my_rank == owner:
                        curr_start += 1
                        con_ranks.append(con_rank)

            starts[cx + 1] = curr_start

        starts = np.array(starts, dtype=ctypes.c_uint64)
        con_ranks = np.array(con_ranks, dtype=ctypes.c_uint64)

        return starts, con_ranks, send_ranks








