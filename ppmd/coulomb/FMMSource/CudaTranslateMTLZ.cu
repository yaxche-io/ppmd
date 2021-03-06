

__constant__ INT64 d_nlevel;
__constant__ REAL d_radius;
__constant__ INT64 d_ncells;
__constant__ INT64 d_re_ncomp;

__constant__ INT64 d_plain_dim0;
__constant__ INT64 d_plain_dim1;
__constant__ INT64 d_plain_dim2;

__constant__ INT64 d_phi_stride;
__constant__ INT64 d_theta_stride;

__constant__ INT64 d_ASTRIDE1;
__constant__ INT64 d_ASTRIDE2;


static inline __device__ void cplx_mul_add(
    const REAL a,
    const REAL b,
    const REAL x,
    const REAL y,
    REAL * RESTRICT g,
    REAL * RESTRICT h
){
   // ( a + bi) * (x + yi) = (ax - by) + (xb + ay)i
    *g += a * x - b * y;
    *h += x * b + a * y;
}


static __global__ void mtl_kernel2(
    const INT64 num_indices,
    const INT64 nblocks,
    const REAL * RESTRICT d_multipole_moments,
    const REAL * RESTRICT d_phi_data,
    const REAL * RESTRICT d_theta_data,
    const REAL * RESTRICT d_alm,
    const REAL * RESTRICT d_almr,
    const INT64 * RESTRICT d_int_list,
    const INT64 * RESTRICT d_int_tlookup,
    const INT64 * RESTRICT d_int_plookup,
    const double * RESTRICT d_int_radius,
    const INT64 * RESTRICT d_jlookup,
    const INT64 * RESTRICT d_klookup,
    const REAL * RESTRICT d_ipower_mtl,
    REAL * RESTRICT d_local_moments
){
    const INT64 plainx = blockIdx.x/nblocks;
    const INT64 plainy = blockIdx.y;
    const INT64 plainz = blockIdx.z;



    const INT64 index_id = (blockIdx.x % nblocks)*blockDim.x + threadIdx.x;
    const bool valid_id = (index_id < num_indices);

    if (valid_id){
        const INT64 jx = d_jlookup[index_id];
        const INT64 kx = d_klookup[index_id];

        const INT64 octal_ind = (plainx % 2) + \
            2*( (plainy % 2) + 2*(plainz % 2) );

        REAL contrib_re = 0.0;
        REAL contrib_im = 0.0; 

        for (INT64 conx=octal_ind*189 ; conx<(octal_ind+1)*189 ; conx++){
            
            const REAL iradius = 1./(d_int_radius[conx] * d_radius);

            const INT64 jcell = (d_int_list[conx] + \
                ((plainx + 2) + (d_plain_dim2+4)* \
                ( (plainy + 2) + (d_plain_dim1+4) * (plainz + 2) )) \
                )*2*d_nlevel*d_nlevel;
            
            
            REAL m1tn_ajk = d_alm[jx*d_ASTRIDE1 + d_ASTRIDE2 + kx] * pow(iradius, jx+1);
            // use Y values
            for( INT64 nx=0 ; nx<d_nlevel ; nx++ ){

                for( INT64 mx=-1*nx ; mx<=nx ; mx++ ){
                    
                    // a_n_m
                    REAL coeff = d_alm[nx*d_ASTRIDE1 + d_ASTRIDE2 + mx] * \
                    // i*(k,m)
                    (((ABS(kx-mx) - ABS(kx) - ABS(mx)) % 4) == 0 ? 1.0 : -1.0) * \
                    // (-1)**(n) * A_j_k
                    m1tn_ajk;

                    const REAL o_re = coeff * d_multipole_moments[jcell + CUBE_IND(nx, mx)];
                    const REAL o_im = coeff * d_multipole_moments[jcell + CUBE_IND(nx, mx) + d_nlevel*d_nlevel];

                    const REAL ppart = d_theta_data[d_theta_stride * d_int_tlookup[conx] + \
                        CUBE_IND(jx+nx, mx-kx)];
                    
                    const REAL y_re = ppart * d_phi_data[d_phi_stride * d_int_plookup[conx] + \
                        EXP_RE_IND(2*d_nlevel, mx-kx)];

                    const REAL y_im = ppart * d_phi_data[d_phi_stride * d_int_plookup[conx] + \
                        EXP_IM_IND(2*d_nlevel, mx-kx)];


                    contrib_re += (o_re * y_re) - (o_im * y_im);
                    contrib_im += (y_re * o_im) + (o_re * y_im);
                    
                }

                
                m1tn_ajk *= -1.0 * iradius;
            }
        }

        const INT64 local_base = 2*num_indices*(plainx + \
        d_plain_dim2*(plainy + d_plain_dim1*plainz));   
        d_local_moments[local_base + CUBE_IND(jx, kx)] = contrib_re;
        d_local_moments[local_base + CUBE_IND(jx, kx) + d_nlevel*d_nlevel] = contrib_im;
    }


}




extern "C"
int translate_mtl(
    const INT64 * RESTRICT dim_child,      // slowest to fastest
    const REAL * RESTRICT d_multipole_moments,
    REAL * RESTRICT d_local_moments,
    const REAL * RESTRICT d_phi_data,
    const REAL * RESTRICT d_theta_data,
    const REAL * RESTRICT d_alm,
    const REAL * RESTRICT d_almr,
    const REAL radius,
    const INT64 nlevel,
    const INT64 * RESTRICT d_int_list,
    const INT64 * RESTRICT d_int_tlookup,
    const INT64 * RESTRICT d_int_plookup,
    const double * RESTRICT d_int_radius,
    const INT64 * RESTRICT d_jlookup,
    const INT64 * RESTRICT d_klookup,
    const REAL * RESTRICT d_ipower_mtl,
    const INT64 thread_block_size,
    const INT64 device_number
){


    int err = 0;
    //this is z, y, x
    const INT64 ncells = dim_child[0] * dim_child[1] * dim_child[2];

    //const INT64 ncomp = nlevel*nlevel*2;
    const INT64 re_ncomp = nlevel*nlevel;
    const INT64 ncomp2 = nlevel*nlevel*8;
    //const INT64 im_offset = nlevel*nlevel;
    //const INT64 im_offset2 = 4*nlevel*nlevel;


    const INT64 phi_stride = 8*nlevel + 2;
    const INT64 theta_stride = 4 * nlevel * nlevel;
    
    const INT64 ASTRIDE1 = 4*nlevel + 1;
    const INT64 ASTRIDE2 = 2*nlevel;

    
    const INT64 num_indices = nlevel * nlevel;

    const INT64 nblocks = ((num_indices%thread_block_size) == 0) ? \
        num_indices/thread_block_size : \
        num_indices/thread_block_size + 1;
    
    dim3 grid_block(nblocks*dim_child[2], dim_child[1], dim_child[0]);
    dim3 thread_block(thread_block_size, 1, 1);
    
    //err = cudaSetDevice(device_number);
    if (err != cudaSuccess){return err;}

    int device_id = -1;
    err = cudaGetDevice(&device_id);
    if (err != cudaSuccess){return err;}

    cudaDeviceProp device_prop;
    err = cudaGetDeviceProperties(&device_prop, device_id);
    if (err != cudaSuccess){return err;}

    if (device_prop.maxThreadsPerBlock<thread_block_size) { 
        printf("bad threadblock size: %d, device max: %d\n", thread_block_size, device_prop.maxThreadsPerBlock); 
        return cudaErrorUnknown; 
    }
 
    err = cudaMemcpyToSymbol(d_nlevel, &nlevel, sizeof(INT64));
    if (err != cudaSuccess) {return err;}
    
    err = cudaMemcpyToSymbol(d_radius, &radius, sizeof(REAL));
    if (err != cudaSuccess) {return err;}

    err = cudaMemcpyToSymbol(d_ncells, &ncells, sizeof(INT64));
    if (err != cudaSuccess) {return err;}

    err = cudaMemcpyToSymbol(d_re_ncomp, &re_ncomp, sizeof(INT64));
    if (err != cudaSuccess) {return err;}

    err = cudaMemcpyToSymbol(d_plain_dim0, &dim_child[0], sizeof(INT64));
    if (err != cudaSuccess) {return err;}
    err = cudaMemcpyToSymbol(d_plain_dim1, &dim_child[1], sizeof(INT64));
    if (err != cudaSuccess) {return err;}
    err = cudaMemcpyToSymbol(d_plain_dim2, &dim_child[2], sizeof(INT64));
    if (err != cudaSuccess) {return err;}
    
    err = cudaMemcpyToSymbol(d_phi_stride, &phi_stride, sizeof(INT64));
    if (err != cudaSuccess) {return err;}
    err = cudaMemcpyToSymbol(d_theta_stride, &theta_stride, sizeof(INT64));
    if (err != cudaSuccess) {return err;}

    err = cudaMemcpyToSymbol(d_ASTRIDE1, &ASTRIDE1, sizeof(INT64));
    if (err != cudaSuccess) {return err;}

    err = cudaMemcpyToSymbol(d_ASTRIDE2, &ASTRIDE2, sizeof(INT64));
    if (err != cudaSuccess) {return err;}

    
    mtl_kernel2<<<grid_block, thread_block>>>(
        num_indices,
        nblocks,
        d_multipole_moments,
        d_phi_data,
        d_theta_data,
        d_alm,
        d_almr,
        d_int_list,
        d_int_tlookup,
        d_int_plookup,
        d_int_radius,
        d_jlookup,
        d_klookup,
        d_ipower_mtl,        
        d_local_moments
    );
    

    err = cudaDeviceSynchronize();
    if (err != cudaSuccess) {return err;}

    return err;
}


// -----------------------------------------------------------------------------------

static __global__ void kernel_rotate_forward(
    const INT64 num_indices,
    const INT64 nblocks,
	const INT64	conxi,
    const REAL * RESTRICT d_multipole_moments,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_re_mat_forw,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_im_mat_forw,
    const INT64 * RESTRICT d_int_list,
    const INT64 * RESTRICT d_int_tlookup,
    const INT64 * RESTRICT d_jlookup,
    const INT64 * RESTRICT d_klookup,
    REAL * RESTRICT d_rot_mom
){
    const INT64 plainx = blockIdx.x/nblocks;
    const INT64 plainy = blockIdx.y;
    const INT64 plainz = blockIdx.z;


    const INT64 index_id = (blockIdx.x % nblocks)*blockDim.x + threadIdx.x;
    const bool valid_id = (index_id < num_indices);

    if (valid_id){
        const INT64 jx = d_jlookup[index_id];
        const INT64 kx = d_klookup[index_id];

        const INT64 octal_ind = (plainx % 2) + \
            2*( (plainy % 2) + 2*(plainz % 2) );

        const INT64 conx=octal_ind*189 + conxi;

        const INT64 local_base = 2*num_indices*(plainx + \
        d_plain_dim2*(plainy + d_plain_dim1*plainz));

		const INT64 jcell = (d_int_list[conx] + \
			((plainx + 2) + (d_plain_dim2+4)* \
			( (plainy + 2) + (d_plain_dim1+4) * (plainz + 2) )) \
			)*2*d_nlevel*d_nlevel;
        
		// get the source vector
		const REAL * RESTRICT re_x = &d_multipole_moments[jcell + CUBE_IND(jx, -1*jx)];
		const REAL * RESTRICT im_x = &d_multipole_moments[jcell + CUBE_IND(jx, -1*jx) + d_nlevel*d_nlevel];

		// get the matrix coefficients to rotate forward
		const REAL * RESTRICT re_m = d_re_mat_forw[d_int_tlookup[conx]][jx];
		const REAL * RESTRICT im_m = d_im_mat_forw[d_int_tlookup[conx]][jx];
		

		// size of matrix
		const INT64 p = 2*jx+1;
		const INT64 rx = kx + jx;
		REAL re_c = 0.0;
		REAL im_c = 0.0;

		for(INT64 cx=0; cx<p ; cx++){
			cplx_mul_add(   re_m[p*cx+rx],  im_m[p*cx+rx],
							re_x[cx],       im_x[cx],
							&re_c,          &im_c);

		}
		
	    d_rot_mom[local_base + CUBE_IND(jx, kx)] = re_c;
        d_rot_mom[local_base + CUBE_IND(jx, kx) + d_nlevel*d_nlevel] = im_c;



    }

}



static inline REAL mtp(const INT64 n){
    return ((n % 2) == 0) ? 1.0 : -1.0;
}


static __global__ void kernel_shift_z(
    const INT64 num_indices,
    const INT64 nblocks,
    const INT64 conxi,
    const REAL * RESTRICT d_multipole_moments,
    const INT64 * RESTRICT d_jlookup,
    const INT64 * RESTRICT d_klookup,
    const double * RESTRICT d_int_radius,
    const REAL * RESTRICT d_alm,
    const REAL * RESTRICT d_almr,
    REAL * RESTRICT d_out_mom
){
    const INT64 plainx = blockIdx.x/nblocks;
    const INT64 plainy = blockIdx.y;
    const INT64 plainz = blockIdx.z;


    const INT64 index_id = (blockIdx.x % nblocks)*blockDim.x + threadIdx.x;
    const bool valid_id = (index_id < num_indices);

    if (valid_id){
        const INT64 jx = d_jlookup[index_id];
        const INT64 kx = d_klookup[index_id];
        const INT64 abs_kx = ABS(kx);

        const INT64 octal_ind = (plainx % 2) + \
            2*( (plainy % 2) + 2*(plainz % 2) );
        const INT64 conx=octal_ind*189 + conxi;


        const INT64 local_base = 2*num_indices*(plainx + \
        d_plain_dim2*(plainy + d_plain_dim1*plainz));
        
        REAL re_c = 0.0;
        REAL im_c = 0.0;
        const REAL iradius = 1./(d_int_radius[conx] * d_radius);

        REAL next_iradius = pow(iradius, jx+abs_kx+1);

        for(INT64 nx=abs_kx ; nx<d_nlevel ; nx++){
            
            const REAL coeff =  d_almr[nx+jx] * \
                                next_iradius * \
                                d_alm[jx*d_ASTRIDE1 + d_ASTRIDE2 + kx] * \
                                d_alm[nx*d_ASTRIDE1 + d_ASTRIDE2 + kx];

            const INT64 oind = CUBE_IND(nx, kx) + local_base;
            const REAL o_re = d_multipole_moments[oind];
            const REAL o_im = d_multipole_moments[oind + d_nlevel*d_nlevel];

            re_c += o_re * coeff;
            im_c += o_im * coeff;

            next_iradius *= -1.0 * iradius;
        }

        d_out_mom[local_base + CUBE_IND(jx, kx)] = re_c;
        d_out_mom[local_base + CUBE_IND(jx, kx) + d_nlevel*d_nlevel] = im_c;


    }

}



static __global__ void kernel_rotate_back(
    const INT64 num_indices,
    const INT64 nblocks,
	const INT64	conxi,
    const REAL * RESTRICT d_multipole_moments,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_re_mat_back,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_im_mat_back,
    const INT64 * RESTRICT d_int_list,
    const INT64 * RESTRICT d_int_tlookup,
    const INT64 * RESTRICT d_jlookup,
    const INT64 * RESTRICT d_klookup,
    REAL * RESTRICT d_rot_mom
){
    const INT64 plainx = blockIdx.x/nblocks;
    const INT64 plainy = blockIdx.y;
    const INT64 plainz = blockIdx.z;


    const INT64 index_id = (blockIdx.x % nblocks)*blockDim.x + threadIdx.x;
    const bool valid_id = (index_id < num_indices);

    if (valid_id){
        const INT64 jx = d_jlookup[index_id];
        const INT64 kx = d_klookup[index_id];

        const INT64 octal_ind = (plainx % 2) + \
            2*( (plainy % 2) + 2*(plainz % 2) );

        const INT64 conx=octal_ind*189 + conxi;

        const INT64 local_base = 2*num_indices*(plainx + \
        d_plain_dim2*(plainy + d_plain_dim1*plainz));
        
		// get the source vector
		const REAL * RESTRICT re_x = &d_multipole_moments[local_base + CUBE_IND(jx, -1*jx)];
		const REAL * RESTRICT im_x = &d_multipole_moments[local_base + CUBE_IND(jx, -1*jx) + d_nlevel*d_nlevel];

		// get the matrix coefficients to rotate forward
		const REAL * RESTRICT re_m = d_re_mat_back[d_int_tlookup[conx]][jx];
		const REAL * RESTRICT im_m = d_im_mat_back[d_int_tlookup[conx]][jx];
		

		// size of matrix
		const INT64 p = 2*jx+1;
		const INT64 rx = kx + jx;
		REAL re_c = 0.0;
		REAL im_c = 0.0;



		for(INT64 cx=0; cx<p ; cx++){
			cplx_mul_add(   re_m[p*cx+rx],  im_m[p*cx+rx],
							re_x[cx],       im_x[cx],
							&re_c,          &im_c);

		}

        d_rot_mom[local_base + CUBE_IND(jx, kx)] += re_c;
        d_rot_mom[local_base + CUBE_IND(jx, kx) + d_nlevel*d_nlevel] += im_c;


    }

}






static __global__ void kernel_all_fused(
    // rotate forward
    const INT64 num_indices,
    const INT64 nblocks,
    const REAL * RESTRICT d_multipole_moments,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_re_mat_forw,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_im_mat_forw,
    const INT64 * RESTRICT d_int_list,
    const INT64 * RESTRICT d_int_tlookup,
    const INT64 * RESTRICT d_jlookup,
    const INT64 * RESTRICT d_klookup,
    //rotate backward
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_re_mat_back,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_im_mat_back,
    // translate
    const double * RESTRICT d_int_radius,
    const REAL * RESTRICT d_alm,
    const REAL * RESTRICT d_almr,
    REAL * RESTRICT d_out_mom
)
{
    extern __shared__ REAL d_tmp1[];
    extern __shared__ REAL d_tmp2[];
    

    const INT64 plainx = blockIdx.x/nblocks;
    const INT64 plainy = blockIdx.y;
    const INT64 plainz = blockIdx.z;

    const INT64 index_id = (blockIdx.x % nblocks)*blockDim.x + threadIdx.x;
    const bool valid_id = (index_id < num_indices);

    if (valid_id){
        const INT64 jx = d_jlookup[index_id];
        const INT64 kx = d_klookup[index_id];

        const INT64 octal_ind = (plainx % 2) + \
            2*( (plainy % 2) + 2*(plainz % 2) );

        for(int conxi=0; conxi<189; conxi++){
            // rotate forward

            const INT64 conx=octal_ind*189 + conxi;

            const INT64 local_base = 2*num_indices*(plainx + \
            d_plain_dim2*(plainy + d_plain_dim1*plainz));

            const INT64 jcell = (d_int_list[conx] + \
                ((plainx + 2) + (d_plain_dim2+4)* \
                ( (plainy + 2) + (d_plain_dim1+4) * (plainz + 2) )) \
                )*2*d_nlevel*d_nlevel;
            
            // get the source vector
            const REAL * RESTRICT re_x = &d_multipole_moments[jcell + CUBE_IND(jx, -1*jx)];
            const REAL * RESTRICT im_x = &d_multipole_moments[jcell + CUBE_IND(jx, -1*jx) + d_nlevel*d_nlevel];

            // get the matrix coefficients to rotate forward
            const REAL * RESTRICT re_m = d_re_mat_forw[d_int_tlookup[conx]][jx];
            const REAL * RESTRICT im_m = d_im_mat_forw[d_int_tlookup[conx]][jx];
            

            // size of matrix
            const INT64 p = 2*jx+1;
            const INT64 rx = kx + jx;
            REAL re_c = 0.0;
            REAL im_c = 0.0;

            for(INT64 cx=0; cx<p ; cx++){
                cplx_mul_add(   re_m[p*cx+rx],  im_m[p*cx+rx],
                                re_x[cx],       im_x[cx],
                                &re_c,          &im_c);

            }
            
            d_tmp1[CUBE_IND(jx, kx)] = re_c;
            d_tmp1[CUBE_IND(jx, kx) + d_nlevel*d_nlevel] = im_c;
            
            __syncthreads();
            // z translate
            const INT64 abs_kx = ABS(kx);
            
            re_c = 0.0;
            im_c = 0.0;
            const REAL iradius = 1./(d_int_radius[conx] * d_radius);

            REAL next_iradius = pow(iradius, jx+abs_kx+1);

            for(INT64 nx=abs_kx ; nx<d_nlevel ; nx++){
                
                const REAL coeff =  d_almr[nx+jx] * \
                                    next_iradius * \
                                    d_alm[jx*d_ASTRIDE1 + d_ASTRIDE2 + kx] * \
                                    d_alm[nx*d_ASTRIDE1 + d_ASTRIDE2 + kx];

                const INT64 oind = CUBE_IND(nx, kx);
                const REAL o_re = d_tmp1[oind];
                const REAL o_im = d_tmp1[oind + d_nlevel*d_nlevel];

                re_c += o_re * coeff;
                im_c += o_im * coeff;

                next_iradius *= -1.0 * iradius;
            }

            d_tmp2[CUBE_IND(jx, kx)] = re_c;
            d_tmp2[CUBE_IND(jx, kx) + d_nlevel*d_nlevel] = im_c;
            
            __syncthreads();
            // rotate backwards

            // get the source vector
            const REAL * RESTRICT re_xb = &d_tmp2[CUBE_IND(jx, -1*jx)];
            const REAL * RESTRICT im_xb = &d_tmp2[CUBE_IND(jx, -1*jx) + d_nlevel*d_nlevel];

            // get the matrix coefficients to rotate forward
            const REAL * RESTRICT re_mb = d_re_mat_back[d_int_tlookup[conx]][jx];
            const REAL * RESTRICT im_mb = d_im_mat_back[d_int_tlookup[conx]][jx];

            // size of matrix
            re_c = 0.0;
            im_c = 0.0;

            for(INT64 cx=0; cx<p ; cx++){
                cplx_mul_add(   re_mb[p*cx+rx],  im_mb[p*cx+rx],
                                re_xb[cx],       im_xb[cx],
                                &re_c,          &im_c);

            }

            d_out_mom[local_base + CUBE_IND(jx, kx)] += re_c;
            d_out_mom[local_base + CUBE_IND(jx, kx) + d_nlevel*d_nlevel] += im_c;

            __syncthreads();
        }

    }

    return;
}















extern "C"
int translate_mtl_z(
    const INT64 * RESTRICT dim_child,      // slowest to fastest
    const REAL * RESTRICT d_multipole_moments,
    REAL * RESTRICT d_local_moments,
	REAL * RESTRICT d_tmp_plain0,
	REAL * RESTRICT d_tmp_plain1,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_re_mat_forw,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_im_mat_forw,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_re_mat_back,
    const REAL * RESTRICT const * RESTRICT const * RESTRICT d_im_mat_back,
    const REAL * RESTRICT d_alm,
    const REAL * RESTRICT d_almr,
    const REAL radius,
    const INT64 nlevel,
    const INT64 * RESTRICT d_int_list,
    const INT64 * RESTRICT d_int_tlookup,
    const double * RESTRICT d_int_radius,
    const INT64 * RESTRICT d_jlookup,
    const INT64 * RESTRICT d_klookup,
    const REAL * RESTRICT d_ipower_mtl,
    const INT64 thread_block_size,
    const INT64 device_number
){


    int err = 0;
    //this is z, y, x
    const INT64 ncells = dim_child[0] * dim_child[1] * dim_child[2];

    //const INT64 ncomp = nlevel*nlevel*2;
    const INT64 re_ncomp = nlevel*nlevel;
    const INT64 ncomp2 = nlevel*nlevel*8;


    const INT64 phi_stride = 8*nlevel + 2;
    const INT64 theta_stride = 4 * nlevel * nlevel;
    
    const INT64 ASTRIDE1 = 4*nlevel + 1;
    const INT64 ASTRIDE2 = 2*nlevel;

    
    const INT64 num_indices = nlevel * nlevel;

    const INT64 nblocks = ((num_indices%thread_block_size) == 0) ? \
        num_indices/thread_block_size : \
        num_indices/thread_block_size + 1;
    
    dim3 grid_block(nblocks*dim_child[2], dim_child[1], dim_child[0]);
    dim3 thread_block(thread_block_size, 1, 1);
    
    if (num_indices > thread_block_size){
        printf("all terms must be handled by one thread block\n");
        return -1;
    }

    //err = cudaSetDevice(device_number);
    if (err != cudaSuccess){return err;}

    int device_id = -1;
    err = cudaGetDevice(&device_id);
    if (err != cudaSuccess){return err;}

    cudaDeviceProp device_prop;
    err = cudaGetDeviceProperties(&device_prop, device_id);
    if (err != cudaSuccess){return err;}

    if (device_prop.maxThreadsPerBlock<thread_block_size) { 
        printf("bad threadblock size: %d, device max: %d\n", thread_block_size, device_prop.maxThreadsPerBlock); 
        return cudaErrorUnknown; 
    }
    
    err = cudaMemcpyToSymbol(d_nlevel, &nlevel, sizeof(INT64));
    if (err != cudaSuccess) {return err;}
    
    err = cudaMemcpyToSymbol(d_radius, &radius, sizeof(REAL));
    if (err != cudaSuccess) {return err;}

    err = cudaMemcpyToSymbol(d_ncells, &ncells, sizeof(INT64));
    if (err != cudaSuccess) {return err;}

    err = cudaMemcpyToSymbol(d_re_ncomp, &re_ncomp, sizeof(INT64));
    if (err != cudaSuccess) {return err;}

    err = cudaMemcpyToSymbol(d_plain_dim0, &dim_child[0], sizeof(INT64));
    if (err != cudaSuccess) {return err;}
    err = cudaMemcpyToSymbol(d_plain_dim1, &dim_child[1], sizeof(INT64));
    if (err != cudaSuccess) {return err;}
    err = cudaMemcpyToSymbol(d_plain_dim2, &dim_child[2], sizeof(INT64));
    if (err != cudaSuccess) {return err;}
    
    err = cudaMemcpyToSymbol(d_phi_stride, &phi_stride, sizeof(INT64));
    if (err != cudaSuccess) {return err;}
    err = cudaMemcpyToSymbol(d_theta_stride, &theta_stride, sizeof(INT64));
    if (err != cudaSuccess) {return err;}

    err = cudaMemcpyToSymbol(d_ASTRIDE1, &ASTRIDE1, sizeof(INT64));
    if (err != cudaSuccess) {return err;}

    err = cudaMemcpyToSymbol(d_ASTRIDE2, &ASTRIDE2, sizeof(INT64));
    if (err != cudaSuccess) {return err;}

    kernel_all_fused<<<grid_block, thread_block, 2*sizeof(REAL)*2*num_indices>>>(
        num_indices,
        nblocks,
        d_multipole_moments,
        d_re_mat_forw,
        d_im_mat_forw,
        d_int_list,
        d_int_tlookup,
        d_jlookup,
        d_klookup,
        d_re_mat_back,
        d_im_mat_back,
        d_int_radius,
        d_alm,
        d_almr,
        d_local_moments
    );

    err = cudaDeviceSynchronize();

    for( INT64 cxi=0 ; cxi<189 ; cxi++){
        
        continue;

        kernel_rotate_forward<<<grid_block, thread_block>>>(
        num_indices,
        nblocks,
        cxi,
        d_multipole_moments,
        d_re_mat_forw,
        d_im_mat_forw,
        d_int_list,
        d_int_tlookup,
        d_jlookup,
        d_klookup,
        d_tmp_plain0
        );

        err = cudaDeviceSynchronize();
        if (err != cudaSuccess) {return err;}

        kernel_shift_z<<<grid_block, thread_block>>>(
            num_indices,
            nblocks,
            cxi,
            d_tmp_plain0,
            d_jlookup,
            d_klookup,
            d_int_radius,
            d_alm,
            d_almr,
            d_tmp_plain1
        );

        err = cudaDeviceSynchronize();
        if (err != cudaSuccess) {return err;}


        kernel_rotate_back<<<grid_block, thread_block>>>(
        num_indices,
        nblocks,
        cxi,
        d_tmp_plain1,
        d_re_mat_back,
        d_im_mat_back,
        d_int_list,
        d_int_tlookup,
        d_jlookup,
        d_klookup,
        d_local_moments
        );

        err = cudaDeviceSynchronize();
        if (err != cudaSuccess) {return err;}
    }






    return err;
}




