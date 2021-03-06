
#include <stdint.h>
#include <omp.h>
#include <stdio.h>
#include <math.h>
#include <iostream>

#define REAL double
#define INT64 int64_t
#define INT32 int32_t

using namespace std;


#define _LM_TO_IND(L, M) ((L)+(M))

#define EXP_RE_IND(L, M) (_LM_TO_IND((L), (M)))
#define EXP_IM_IND(L, M) ((2*(L))+1 + EXP_RE_IND((L),(M)))

#define CUBE_IND(L, M) ((L) * ( (L) + 1 ) + (M) )

// defined for non-negative M
#define P_IND(L, M) (((L)*((L) + 1)/2) + (M))

#define MIN(x, y) ((x < y) ? x : y)
#define MAX(x, y) ((x < y) ? y : x)

#define I_IND(nlevel, kx, mx) ((2*(nlevel)+1)*(nlevel+(kx)) + nlevel + (mx) )

#define ABS(x) ((x) > 0 ? (x) : -1*(x))

#define BLOCKSIZE 8

#define ENERGY_UNIT (%(SUB_ENERGY_UNIT)s)
#define FORCE_UNIT (%(SUB_FORCE_UNIT)s)

#define CUDACHECKERR if(err!= cudaSuccess){printf("CUDA ERR LINE: %%d\n", __LINE__-1);return err;}


const INT64 HMAP[26][3] = {
        {-1,1,-1},      // 0
        {-1,-1,-1},
        {-1,0,-1},
        {0,1,-1},
        {0,-1,-1},
        {0,0,-1},
        {1,0,-1},
        {1,1,-1},
        {1,-1,-1},      // 8

        {-1,1,0},       // 9
        {-1,0,0},
        {-1,-1,0},
        {0,-1,0},
        {0,1,0},        // 14
        {1,0,0},        // 15
        {1,1,0},
        {1,-1,0},       // 17

        {-1,0,1},       // 18
        {-1,1,1},
        {-1,-1,1},
        {0,0,1},
        {0,1,1},
        {0,-1,1},
        {1,0,1},
        {1,1,1},
        {1,-1,1}        // 26
};
__constant__ INT64 d_max_cell_count;
__constant__ INT64 d_offsets[26];
__constant__ INT64 d_nlocal;
__constant__ INT64 d_ll_cstart;



__constant__ INT64 d_plsx;
__constant__ INT64 d_plsy;

__constant__ INT64 d_pgsx;
__constant__ INT64 d_pgsy;

__constant__ INT64 d_local_offset2;
__constant__ INT64 d_local_offset1;
__constant__ INT64 d_local_offset0;






