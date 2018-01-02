
static inline INT64 compute_cell(
    const REAL * RESTRICT cube_inverse_len,
    const REAL px,
    const REAL py,
    const REAL pz,
    const REAL * RESTRICT boundary,
    const UINT64 * RESTRICT cube_offset,
    const UINT64 * RESTRICT cube_dim,
    const UINT64 * RESTRICT cube_side_counts,   
    INT32 * global_cell
){
    const REAL pxs = px + 0.5 * boundary[0];
    const REAL pys = py + 0.5 * boundary[1];
    const REAL pzs = pz + 0.5 * boundary[2];

    const UINT64 cx = ((UINT64) (pxs*cube_inverse_len[0])) - cube_offset[2];
    const UINT64 cy = ((UINT64) (pys*cube_inverse_len[1])) - cube_offset[1];
    const UINT64 cz = ((UINT64) (pzs*cube_inverse_len[2])) - cube_offset[0];
    //printf("px %f pxs %f boudary %f \n", px, pxs, boundary[0]);
    //printf("py %f pys %f boudary %f \n", py, pys, boundary[0]);
    //printf("pz %f pzs %f boudarz %f \n", pz, pzs, boundary[0]);
    if (cx >= cube_dim[2] || cy >= cube_dim[1] || cz >= cube_dim[0] ){
        return (INT64) -1;}
    
    const UINT64 gcx = ((UINT64) (pxs*cube_inverse_len[0]));
    const UINT64 gcy = ((UINT64) (pys*cube_inverse_len[1]));
    const UINT64 gcz = ((UINT64) (pzs*cube_inverse_len[2]));
    

    *global_cell = ((INT32) (  gcx + cube_side_counts[2] * (gcy + cube_side_counts[1] * gcz )  ));

    //printf("GLOBAL %f %f %f %d %d %d | %d\n", px, py, pz, gcx, gcy, gcz, *global_cell);
    return cx + cube_dim[2] * (cy + cube_dim[1] * cz);
}

static inline INT64 compute_cell_spherical(
    const REAL * RESTRICT cube_inverse_len,
    const REAL * RESTRICT cube_half_len,
    const REAL px,
    const REAL py,
    const REAL pz,
    const REAL * RESTRICT boundary,
    const UINT64 * RESTRICT cube_offset,
    const UINT64 * RESTRICT cube_dim,
    REAL * RESTRICT radius,
    REAL * RESTRICT ctheta,
    REAL * RESTRICT cphi,
    REAL * RESTRICT sphi,
    REAL * RESTRICT msphi
){
    const REAL pxs = px + 0.5 * boundary[0];
    const REAL pys = py + 0.5 * boundary[1];
    const REAL pzs = pz + 0.5 * boundary[2];

    const UINT64 cxt = pxs*cube_inverse_len[0];
    const UINT64 cyt = pys*cube_inverse_len[1];
    const UINT64 czt = pzs*cube_inverse_len[2];

    const UINT64 cx = cxt - cube_offset[2];
    const UINT64 cy = cyt - cube_offset[1];
    const UINT64 cz = czt - cube_offset[0];

    if (cx >= cube_dim[2] || cy >= cube_dim[1] || cz >= cube_dim[0] ){
        return (INT64) -1;}
    const int cell_idx = cx + cube_dim[2] * (cy + cube_dim[1] * cz);
    // now compute the vector between particle and cell center in spherical coords
    // cell center
    const REAL ccx = (cxt * 2 + 1) * cube_half_len[0] - 0.5 * boundary[0]; 
    const REAL ccy = (cyt * 2 + 1) * cube_half_len[1] - 0.5 * boundary[1]; 
    const REAL ccz = (czt * 2 + 1) * cube_half_len[2] - 0.5 * boundary[2]; 
    //printf("cube_inverse_lens %f %f %f\n", cube_inverse_len[0], cube_inverse_len[1], cube_inverse_len[2]);

    //printf("cube_half_len %f %f %f %f\n", cube_half_len[0], cube_half_len[1], cube_half_len[2], (cyt * 2 + 1) + cube_half_len[1]);
    // compute Cartesian displacement vector

    const REAL dx = px - ccx;
    const REAL dy = py - ccy;
    const REAL dz = pz - ccz;
    
    //printf("dx %f px %f mid %f\n", dx, px, ccx);
    //printf("dy %f py %f mid %f\n", dy, py, ccy);
    //printf("dz %f pz %f mid %f\n", dz, pz, ccz);
    

    // convert to spherical
    const REAL dx2 = dx*dx;
    const REAL dx2_p_dy2 = dx2 + dy*dy;
    const REAL d2 = dx2_p_dy2 + dz*dz;
    *radius = sqrt(d2);
    
    const REAL theta = atan2(sqrt(dx2_p_dy2), dz);
    *ctheta = cos(theta);
    
    const REAL phi = atan2(dy, dx);

    *cphi = cos(phi);
    *sphi = sin(phi); 
    *msphi = -1.0 * (*sphi);
    return cell_idx;
}

static inline void next_pos_exp(
    const REAL cphi,
    const REAL sphi,
    const REAL rpe,
    const REAL ipe,
    REAL * RESTRICT nrpe,
    REAL * RESTRICT nipe
){
    *nrpe = rpe*cphi - ipe*sphi;
    *nipe = rpe*sphi + ipe*cphi;
}

static inline void next_neg_exp(
    const REAL cphi,
    const REAL msphi,
    const REAL rne,
    const REAL ine,
    REAL * RESTRICT nrne,
    REAL * RESTRICT nine
){
    *nrne = rne*cphi  - ine*msphi;
    *nine = rne*msphi + ine*cphi;
}

static inline REAL m1_m(int m){
    return 1.0 - 2.0*((REAL)(m & 1));
}


extern "C"
INT32 particle_contribution(
    const INT64 nlevel,
    const UINT64 npart,
    const INT32 thread_max,
    const REAL * RESTRICT position,             // xyz
    const REAL * RESTRICT charge,
    INT32 * RESTRICT fmm_cell,
    const REAL * RESTRICT boundary,             // xl. xu, yl, yu, zl, zu
    const UINT64 * RESTRICT cube_offset,        // zyx (slowest to fastest)
    const UINT64 * RESTRICT cube_dim,           // as above
    const UINT64 * RESTRICT cube_side_counts,   // as above
    REAL * RESTRICT cube_data,                  // lexicographic
    INT32 * RESTRICT thread_assign
){
    INT32 err = 0;
    omp_set_num_threads(thread_max);
    //printf("%f | %f | %f\n", boundary[0], boundary[1], boundary[2]);


    const REAL cube_ilen[3] = {
        cube_side_counts[2]/boundary[0],
        cube_side_counts[1]/boundary[1],
        cube_side_counts[0]/boundary[2]
    };
    
    const REAL cube_half_side_len[3] = {
        0.5*boundary[0]/cube_side_counts[2],
        0.5*boundary[1]/cube_side_counts[1],
        0.5*boundary[2]/cube_side_counts[0]
    };

    // loop over particle and assign them to threads based on cell
    #pragma omp parallel for default(none) shared(thread_assign, position, \
    boundary, cube_offset, cube_dim, err, cube_ilen, charge, fmm_cell, cube_side_counts)
    for(UINT64 ix=0 ; ix<npart ; ix++){

        INT32 global_cell = -1;
        const INT64 ix_cell = compute_cell(cube_ilen, position[ix*3], position[ix*3+1], 
                position[ix*3+2], boundary, cube_offset, cube_dim, cube_side_counts, &global_cell);

        if (ix_cell < 0) {
            #pragma omp critical
            {err = -1;}
            #pragma omp flush (err)
        } else {
            const INT64 thread_owner = ix_cell % thread_max;
            INT64 thread_layer;
            #pragma omp critical
            {thread_layer = ++thread_assign[thread_owner];}
            thread_assign[thread_max + npart*thread_owner + thread_layer - 1]\
                = ix;

            // assign this particle a cell for short range part
            fmm_cell[ix] = global_cell;
            //printf("ix = %d global_cell = %d\n", ix, global_cell);
        }
    }
    if (err < 0) { return err; }
 
    // check all particles were assigned to a thread
    UINT64 check_sum = 0;
    for(INT32 ix=0 ; ix<thread_max ; ix++){
        check_sum += thread_assign[ix]; 
        //printf("tx %d val %d\n", ix, thread_assign[ix]);
    }
    if (check_sum != npart) {printf("npart %d assigned %d\n", npart, check_sum); return -2;}
    
    // Above we assigned particles to threads in a way that avoids needing atomics here.
    // Computing the cell is duplicate work, but the computation is cheap and the positions
    // needed to be read anyway to compute the moments.

    // using omp parallel for with schedule(static, 1) is robust against the omp
    // implementation deciding to launch less threads here than thread_max (which it
    // is entitled to do).
    
    REAL exp_space[thread_max][nlevel*4 + 2];
    // pre compute factorial and double factorial
    const UINT64 nfact = (2*nlevel > 4) ? 2*nlevel : 4;
    REAL factorial_vec[nfact];
    REAL double_factorial_vec[nfact];

    factorial_vec[0] = 1.0;
    factorial_vec[1] = 1.0;
    factorial_vec[2] = 2.0;
    double_factorial_vec[0] = 1.0;
    double_factorial_vec[1] = 1.0;
    double_factorial_vec[2] = 2.0;

    for( INT64 lx=3 ; lx<nfact ; lx++ ){
        factorial_vec[lx] = lx * factorial_vec[lx-1];
        double_factorial_vec[lx] = lx * double_factorial_vec[lx-2];
    }
    
    REAL P_SPACE_VEC[thread_max][nlevel*nlevel*2];


    UINT32 count = 0;
    #pragma omp parallel for default(none) shared(thread_assign, position, boundary, \
        cube_offset, cube_dim, err, cube_data, exp_space, factorial_vec, double_factorial_vec, P_SPACE_VEC, \
        cube_half_side_len, cube_ilen, charge) \
        schedule(static,1) \
        reduction(+: count)
    for(INT32 tx=0 ; tx<thread_max ; tx++){
        const int tid = omp_get_thread_num();
        const UINT64 ncomp = nlevel*nlevel*2;
        REAL * P_SPACE = P_SPACE_VEC[tid];
        for(INT64 px=0 ; px<thread_assign[tx] ; px++){
            INT64 ix = thread_assign[thread_max + npart*tx + px];
            REAL radius, ctheta, cphi, sphi, msphi;
            const INT64 ix_cell = compute_cell_spherical(
                cube_ilen, cube_half_side_len, position[ix*3], position[ix*3+1], 
                position[ix*3+2], boundary, cube_offset, cube_dim,
                &radius, &ctheta, &cphi, &sphi, &msphi
            );

            //printf("%d \t radius: %f cos(theta): %f cos(phi): %f sin(phi): %f -1*sin(phi): %f\n", 
            //ix, radius, ctheta, cphi, sphi, msphi);
            
            if (tx != ix_cell % thread_max) {           
                #pragma omp critical
                {err = -3;}
            }

            //compute spherical harmonic moments

            // start with the complex exponential (will not vectorise)
            REAL * RESTRICT exp_vec = exp_space[tid]; 
            REAL * RESTRICT cube_start = &cube_data[ix_cell*ncomp];
            REAL * RESTRICT cube_start_im = &cube_data[ix_cell*ncomp + nlevel*nlevel];


            exp_vec[EXP_RE_IND(nlevel, 0)] = 1.0;
            exp_vec[EXP_IM_IND(nlevel, 0)] = 0.0;
            for (INT32 lx=1 ; lx<=((INT32)nlevel) ; lx++){
                next_pos_exp(
                    cphi, sphi,
                    exp_vec[EXP_RE_IND(nlevel, lx-1)],
                    exp_vec[EXP_IM_IND(nlevel, lx-1)],
                    &exp_vec[EXP_RE_IND(nlevel, lx)],
                    &exp_vec[EXP_IM_IND(nlevel, lx)]);
                next_neg_exp(
                    cphi, msphi,
                    exp_vec[EXP_RE_IND(nlevel, -1*(lx-1))],
                    exp_vec[EXP_IM_IND(nlevel, -1*(lx-1))],
                    &exp_vec[EXP_RE_IND(nlevel, -1*lx)],
                    &exp_vec[EXP_IM_IND(nlevel, -1*lx)]);
            }


/*
            for (int lx=-1*((int)nlevel)+1 ; lx<((int)nlevel) ; lx++){
                printf("%d, %f %f\n", lx, exp_vec[EXP_RE_IND(nlevel, lx)], exp_vec[EXP_IM_IND(nlevel, lx)]);
            }
*/            


            const REAL sqrt_1m2lx = sqrt(1.0 - ctheta*ctheta);
 //           printf("sqrt(1 - 2l) = %f, cos(theta) = %f\n", sqrt_1m2lx, ctheta);


            // P_0^0 = 1;
            P_SPACE[P_SPACE_IND(nlevel, 0, 0)] = 1.0;
            
            for( int lx=0 ; lx<((int)nlevel) ; lx++){

                //compute the (lx+1)th P values using the lx-th values
                if (lx<(nlevel-1) ){ 
                    P_SPACE[P_SPACE_IND(nlevel, lx+1, lx+1)] = (-1.0 - 2.0*lx) * sqrt_1m2lx * \ 
                        P_SPACE[P_SPACE_IND(nlevel, lx, lx)];

                    P_SPACE[P_SPACE_IND(nlevel, lx+1, lx)] = ctheta * (2*lx + 1) * \
                        P_SPACE[P_SPACE_IND(nlevel, lx, lx)];

                    for( int mx=0 ; mx<lx ; mx++ ){
                        P_SPACE[P_SPACE_IND(nlevel, lx+1, mx)] = \
                            (ctheta * (2.0*lx+1.0) * P_SPACE[P_SPACE_IND(nlevel, lx, mx)] - \
                            (lx+mx)*P_SPACE[P_SPACE_IND(nlevel, lx-1, mx)]) / (lx - mx + 1);
                    }

                }
            }

            //for (int mx=0 ; mx<=lx ; mx++){
            //    printf("l %d, m %d P %.50f\n", lx, mx, P_SPACE[P_SPACE_IND(nlevel, lx, mx)]); 
            //}
            //printf("-----------------------------\n");
            
            REAL rhol = 1.0;
            //loop over l and m
            for( int lx=0 ; lx<((int)nlevel) ; lx++ ){
                rhol = (lx > 0) ? rhol*radius : 1.0;

                for( int mx=-1*lx ; mx<=lx ; mx++ ){
                    const UINT32 abs_mx = abs(mx);
                    const REAL coeff = sqrt(factorial_vec[lx - abs_mx]/factorial_vec[lx + abs_mx]) \
                                       * charge[ix] * rhol;

                    const REAL plm = P_SPACE[P_SPACE_IND(nlevel, lx, abs_mx)];

                    cube_start[CUBE_IND(lx, mx)] += coeff * plm * exp_vec[EXP_RE_IND(nlevel, -1*mx)];
                    cube_start_im[CUBE_IND(lx, mx)] += coeff * plm * exp_vec[EXP_IM_IND(nlevel, -1*mx)];

                    //if(lx == 1) {printf("%d %f\n", mx, plm);}

                    //printf("%d %d %d = %f %f\n",px, lx, mx, cube_start[CUBE_IND(lx, mx)], cube_start_im[CUBE_IND(lx, mx)]);

                }
            }

            count++;
        }
    }   

    // printf("npart %d count %d\n", npart, count);
    
    if (count != npart) {err = -4;}
    return err;
}









