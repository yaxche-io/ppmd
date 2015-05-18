import numpy as np
import math
import ctypes
import data
from mpi4py import MPI
import random
import kernel
import build
import particle
import time

################################################################################################################
# HALO DEFINITIONS
################################################################################################################
'''
class cell_basis_calc(object):
    def __init__(self, extent):
        self._extent = extent
    
    def calc(self,c_in, cell_array):
        """
        Convert cell linear index to vector.
        
        :arg int c_in: Input index.
        """    
        Cz = self._extent[2]*float(c_in)/(cell_array[0]*cell_array[1]*cell_array[2])
        Cx = self._extent[0]*float(c_in % cell_array[0])/cell_array[0]
        Cy = self._extent[1]*float(int((c_in - Cz*(cell_array[0]*cell_array[1]))/(cell_array[0])))/cell_array[1]
        return np.array([Cx,Cy,Cz], dtype=ctypes.c_double)
'''    
class HaloCartesianSingleProcess(object):
    """
    Class to contain and control cartesian halo transfers.
    
    """
    def __init__(self, MPICOMM = None, rank = 0, nproc = 1, cell_array = None, extent = None):
        self._DEBUG = True
        timer=True
        if (timer==True):
            start = time.time() 
                
        assert cell_array != None, "Error: No cell array passed."
        assert extent != None, "Error: No extent passed."
        
        self._rank = rank
        self._nproc = nproc
        self._MPI = MPICOMM
        
        self._ca = cell_array
        self._extent = extent
        
        self._halos=[]
        
        _BASE_SIZES = [1, self._ca[0]-2, 1, self._ca[1]-2, (self._ca[0]-2)*(self._ca[1]-2), self._ca[1]-2,1,self._ca[0]-2,1]
        
        _MID_SIZES = [self._ca[2]-2, (self._ca[0]-2)*(self._ca[2]-2), self._ca[2]-2, (self._ca[1]-2)*(self._ca[2]-2), (self._ca[1]-2)*(self._ca[2]-2), self._ca[2]-2, (self._ca[0]-2)*(self._ca[2]-2), self._ca[2]-2]
        
        self._SIZES = _BASE_SIZES + _MID_SIZES + _BASE_SIZES
        
        dest=0
        src=0
        
        self._halo_setup_prepare()
        
        for ix in range(26):
            self._halos.append(Halo(self._MPI, self._rank,dest,src,ix,self._SIZES[ix], ncol = 3))
        
        self._create_packing_pointer_array()
        
        
        self._time = 0.   
        if (timer==True):
            end = time.time()
            print "halo setup time = ", end-start, "s"      
        
    def exchange(self,cell_contents_count, cell_list, data):
        timer=True
        if (timer==True):
            start = time.time()          
   
    
        '''Get new storage sizes''' 
        self._exchange_size_calc(cell_contents_count)
         
         
        
        '''Reset halo starting points'''
        data.halo_start_reset()
        
        
        
        _static_args = {
                        'PPA':self._packing_pointers.ctypes_data,
                        'cell_start':ctypes.c_int(cell_list[cell_list.end]),
                        'ncomp':ctypes.c_int(data.ncomp)
                        }
        
        _args = {
                 'Q':cell_list,
                 'CCA_I':self._cell_contents_array_index,
                 'CIA':self._cell_indices_array,
                 'CSA':self._cell_shifts_array,
                 'data_buffer':data
                 }        
        
        
        
        self._packing_lib.execute(static_args = _static_args, dat_dict = _args)
        
        #perform halo exchange
        for i,h in enumerate(self._halos):
            h.exchange(self._exchange_sizes[i], self._cell_contents_array[self._cell_contents_array_index[i]:self._cell_contents_array_index[i+1]:], self._cell_contents_recv[self._cell_contents_array_index[i]:self._cell_contents_array_index[i+1]:],cell_list, data)
        
        
        
        
        

        #print self._local_cell_indices_array
        #sort local cells after exchange
        self._cell_sort_loop.execute({'Q':cell_list,'LCI':self._local_cell_indices_array,'CRC':self._cell_contents_recv},{'CC':ctypes.c_int(self._cell_contents_recv.ncomp),'shift':ctypes.c_int(data.npart),'end':ctypes.c_int(cell_list[cell_list.end])})
        
                                   
        
        
        if (timer==True):
            end = time.time()
            self._time+=end - start      
            
                        
    
        
    def _create_packing_pointer_array(self):
        self._packing_pointers = data.PointerArray(length=26,dtype=ctypes.c_double)
        for ix in range(26):
            self._packing_pointers[ix] = self._halos[ix].send_buffer.ctypes_data
        
        
        
        _packing_code = '''
        
        for(int ix = 0; ix<26; ix++ ){
            const int start = CCA_I[ix];
            const int end = CCA_I[ix+1];
            int index = 0;
            
            for(int iy = start; iy < end; iy++){
                
                int c_i = CIA[iy];
                int iz = Q[cell_start+c_i];
                
                while(iz > -1){
                    for(int cx = 0; cx<ncomp;cx++){
                        PPA[ix][LINIDX_2D(ncomp,index,cx)] = data_buffer[LINIDX_2D(ncomp,iz,cx)] + CSA[LINIDX_2D(ncomp,ix,cx)];
                    }
                    index++;
                    iz = Q[iz];
                
                
                }
            }
        }
        
        '''
        
        _static_args = {
                        'PPA':'doublepointerpointer', #self._packing_pointers.ctypes_data
                        'cell_start':ctypes.c_int,   #ctypes.c_int(cell_list[cell_list.end])
                        'ncomp':ctypes.c_int    #ctypes.c_int(data.ncomp)
                        }
        
        _args = {
                 'Q':data.NullIntScalarArray,   #cell_list.ctypes_data
                 'CCA_I':self._cell_contents_array_index,
                 'CIA':self._cell_indices_array,
                 'CSA':self._cell_shifts_array,
                 'data_buffer':data.NullDoubleScalarArray, #data
                 }
        
        
        
        
        _headers = ['stdio.h']
        _kernel = kernel.Kernel('HaloPackingCode', _packing_code, None, _headers, None, _static_args)
        self._packing_lib = build.SharedLib(_kernel,_args,DEBUG = self._DEBUG)         
        
        
        
        
        
        
        
    def _exchange_size_calc(self,cell_contents_count):
        '''
        for i,x in enumerate(self._cell_indices):
            self._exchange_sizes[i]=sum([y[1] for y in enumerate(cell_contents_count) if y[0] in x])
        '''
        
        _args = {
                 'CCC':cell_contents_count, 
                 'ES':self._exchange_sizes,
                 'CI':self._cell_indices_array,
                 'CIL':self._cell_indices_len,
                 'CCA':self._cell_contents_array,
                 'CCA_I':self._cell_contents_array_index
                 }        
        
        
        self._exchange_sizes_lib.execute(dat_dict = _args)
        
        
        
    def _halo_setup_prepare(self):
        
       
        
        self._exchange_sizes=data.ScalarArray(range(26),dtype=ctypes.c_int)

        
        #CELL INDICES TO PACK ===========================================================================================
                
        _E = self._ca[0]*self._ca[1]*(self._ca[2]-1) - self._ca[0] - 1
        _TS = _E - self._ca[0]*(self._ca[1] - 2) + 2
        
        _BE = self._ca[0]*(2*self._ca[1] - 1) - 1
        _BS = self._ca[0]*(self._ca[1] + 1) + 1
        
        _tmp4=[]
        for ix in range(self._ca[1]-2):
            _tmp4 += range(_TS + ix*self._ca[0], _TS + (ix+1)*self._ca[0] - 2, 1)
        
        _tmp10=[]
        for ix in range(self._ca[2]-2):
            _tmp10 += range( _BE-self._ca[0]+2 + ix*self._ca[0]*self._ca[1], _BE + ix*self._ca[0]*self._ca[1],1)
        
        _tmp12=[]
        for ix in range(self._ca[2]-2):
            _tmp12 += range( _BS+self._ca[0]-3 + ix*self._ca[0]*self._ca[1], _BE + ix*self._ca[0]*self._ca[1], self._ca[0])
        
        _tmp13=[]
        for ix in range(self._ca[2]-2):
            _tmp13 += range( _BS + ix*self._ca[0]*self._ca[1], _BE + ix*self._ca[0]*self._ca[1], self._ca[0])        
        
        _tmp15=[]
        for ix in range(self._ca[2]-2):
            _tmp15 += range( _BS + ix*self._ca[0]*self._ca[1], _BS+self._ca[0]-2 + ix*self._ca[0]*self._ca[1], 1)

        _tmp21=[]
        for ix in range(self._ca[1]-2):
            _tmp21 += range(_BS + ix*self._ca[0], _BS + (ix+1)*self._ca[0] - 2, 1)          
        
        
        
        self._cell_indices=[
                            [_E-1],
                            range(_E-self._ca[0]+2,_E,1),
                            [_E-self._ca[0]+2],
                            range(_TS+self._ca[0]-3, _E, self._ca[0]), 
                            _tmp4, 
                            range(_TS,_E,self._ca[0]), 
                            [_TS+self._ca[0]-3], 
                            range(_TS,_TS+self._ca[0]-2,1),
                            [_TS],
                            
                            range(_BE - 1,_E,self._ca[0]*self._ca[1]),
                            _tmp10,
                            range(_BE-self._ca[0]+2,_E,self._ca[0]*self._ca[1]),
                            _tmp12,
                            _tmp13,
                            range(_BS+self._ca[0]-3,_E,self._ca[0]*self._ca[1]),
                            _tmp15,
                            range(_BS,_E,self._ca[0]*self._ca[1]),
                              
                            [_BE-1],
                            range(_BE-self._ca[0]+2,_BE,1),
                            [_BE-self._ca[0]+2],
                            range(_BS+self._ca[0]-3, _BE, self._ca[0]), 
                            _tmp21,
                            range(_BS,_BE,self._ca[0]), 
                            [_BS+self._ca[0]-3], 
                            range(_BS,_BS+self._ca[0]-2,1),
                            [_BS]
                            ]
          
        #=====================================================================================================================
        #LOCAL CELL INDICES TO SORT INTO
        
        _LE = self._ca[0]*self._ca[1]*self._ca[2]
        _LTS = _LE - self._ca[0]*self._ca[1]
        
        _LBE = self._ca[0]*self._ca[1]
        _LBS = 0
        
        _Ltmp4=[]
        for ix in range(self._ca[1]-2):
            _Ltmp4 += range(_LBS + 1 + (ix+1)*self._ca[0], _LBS + (ix+2)*self._ca[0] - 1, 1)
        
        _Ltmp10=[]
        for ix in range(self._ca[2]-2):
            _Ltmp10 += range( _LBS + 1 + (ix+1)*self._ca[0]*self._ca[1], _LBS + (ix+1)*self._ca[0]*self._ca[1] + self._ca[0] - 1,1)        
        
        _Ltmp12=[]
        for ix in range(self._ca[2]-2):
            _Ltmp12 += range( _LBS + self._ca[0] + (ix+1)*self._ca[0]*self._ca[1], _LBS + self._ca[0]*(self._ca[1]-1) + (ix+1)*self._ca[0]*self._ca[1], self._ca[0])        
        
        _Ltmp13=[]
        for ix in range(self._ca[2]-2):
            _Ltmp13 += range( _LBS + 2*self._ca[0] - 1 + (ix+1)*self._ca[0]*self._ca[1], _LBE + (ix+1)*self._ca[0]*self._ca[1] - 3, self._ca[0])           
        
        _Ltmp15=[]
        for ix in range(self._ca[2]-2):
            _Ltmp15 += range( _LBE + (ix+1)*self._ca[0]*self._ca[1] - self._ca[0] + 1, _LBE + (ix+1)*self._ca[0]*self._ca[1] - 1, 1)        
        
        _Ltmp21=[]
        for ix in range(self._ca[1]-2):
            _Ltmp21 += range(_LTS + (ix+1)*self._ca[0] + 1, _LTS + (ix+2)*self._ca[0] - 1, 1)        
        
        self._local_cell_indices=[
                            [_LBS],
                            range(_LBS+1,_LBS+self._ca[0]-1,1),
                            [_LBS+self._ca[0]-1],
                            range(_LBS+self._ca[0], _LBS+self._ca[0]*(self._ca[1]-2)+1, self._ca[0]), 
                            _Ltmp4, 
                            range(_LBS+2*self._ca[0]-1,_LBE-self._ca[0],self._ca[0]), 
                            [_LBE-self._ca[0]],
                            range(_LBE-self._ca[0]+1,_LBE-1,1),
                            [_LBE-1],
                            
                            range(_LBS+self._ca[0]*self._ca[1],_LBS+(self._ca[2]-2)*self._ca[0]*self._ca[1]+1,self._ca[0]*self._ca[1]),
                            _Ltmp10,
                            range(_LBE+self._ca[0]-1,_LBE+(self._ca[2]-2)*self._ca[0]*self._ca[1]+self._ca[0] - 1,self._ca[0]*self._ca[1]),
                            _Ltmp12,
                            _Ltmp13,
                            range(_LBE+self._ca[0]*(self._ca[1]-1),_LE-self._ca[0]*self._ca[1],self._ca[0]*self._ca[1]),
                            _Ltmp15,
                            range(_LBE+self._ca[0]*self._ca[1] - 1,_LE-self._ca[0]*self._ca[1],self._ca[0]*self._ca[1]),
                              
                            [_LTS],
                            range(_LTS+1,_LTS+self._ca[0]-1,1),
                            [_LTS+self._ca[0]-1],
                            range(_LTS+self._ca[0], _LTS+self._ca[0]*(self._ca[1]-2)+1, self._ca[0]), 
                            _Ltmp21, 
                            range(_LTS+2*self._ca[0]-1,_LE-self._ca[0],self._ca[0]), 
                            [_LE-self._ca[0]],
                            range(_LE-self._ca[0]+1,_LE-1,1),
                            [_LE-1],
                            ]          
        
        #=====================================================================================================================
        
        
        
        self._cell_indices_len = data.ScalarArray(range(26), dtype=ctypes.c_int)
        _tmp_list=[]
        _tmp_list_local=[]
        for ix in range(26):
            #number of cells in each halo
            self._cell_indices_len[ix] = len(self._cell_indices[ix])        
            _tmp_list+=self._cell_indices[ix]
            _tmp_list_local += self._local_cell_indices[ix]
            
        self._cell_indices_array = data.ScalarArray(_tmp_list, dtype=ctypes.c_int)
        self._local_cell_indices_array = data.ScalarArray(_tmp_list_local, dtype=ctypes.c_int)
        
        
        
        #create cell contents array for each halo that are being sent.
        self._cell_contents_array = data.ScalarArray(ncomp=self._cell_indices_array.ncomp, dtype=ctypes.c_int)
        
        #create cell contents array for each halo that are being recv'd.
        self._cell_contents_recv = data.ScalarArray(ncomp=self._cell_indices_array.ncomp, dtype=ctypes.c_int)        
        
        
        #create list to extract start and end points for each halo from above lists.
        self._cell_contents_array_index = data.ScalarArray(ncomp=27, dtype=ctypes.c_int)
        
        _start_index = 0
        self._cell_contents_array_index[0]=0
        for ix in range(26):
            _start_index+=self._cell_indices_len[ix]
            self._cell_contents_array_index[ix+1] = _start_index
        
        #Code to calculate exchange sizes 
        #==========================================================================================================================        
        
        _exchange_sizes_code='''
        int start_index = 0;
        //CCA_I[0]=0;
        for(int ix = 0; ix < 26; ix++){
            ES[ix] = 0;
            for(int iy = 0; iy < CIL[ix]; iy++){
                
                
                ES[ix] += CCC[CI[start_index+iy]];
                CCA[start_index+iy]=CCC[CI[start_index+iy]];
            }
            start_index+=CIL[ix];
            //CCA_I[ix+1] = start_index;
        }
        
        '''
        
        _static_args = None
        
        _args = {
                 'CCC':data.NullIntScalarArray, 
                 'ES':data.NullIntScalarArray,
                 'CI':data.NullIntScalarArray,
                 'CIL':data.NullIntScalarArray,
                 'CCA':data.NullIntScalarArray,
                 'CCA_I':data.NullIntScalarArray
                 }
                 
        _headers = ['stdio.h']
        _kernel = kernel.Kernel('ExchangeSizeCalc', _exchange_sizes_code, None, _headers, None, None)
        self._exchange_sizes_lib = build.SharedLib(_kernel,_args,DEBUG = True)         
        
        #========================================================================================================================== 
        
        #Code to sort incoming halo particles into cell list 
        #==========================================================================================================================
        _cell_sort_code = '''
        
        int index = shift;
        for(int ix = 0; ix < CC; ix++){
            
            const int _tmp = CRC[ix];
            
            if (_tmp>0){
                Q[end+LCI[ix]] = index;
                //printf("cell=%d, index=%d |", LCI[ix], index);
                for(int iy = 0; iy < _tmp-1; iy++){
                    Q[index+iy]=index+iy+1;
                }
                Q[index+_tmp-1] = -1;
            }
            
            
            index += CRC[ix];
        
        }
        '''
        
        #number of cells         self._cell_contents_recv.ncomp             data.npart         'end':ctypes.c_int(cell_list[cell_list.end])
        _static_args = {'CC':ctypes.c_int,'shift':ctypes.c_int,'end':ctypes.c_int}
        
        
        _cell_sort_dict = {
                           'Q':data.NullIntScalarArray,
                           'LCI':self._local_cell_indices_array,
                           'CRC':self._cell_contents_recv
                           }
                
        
        
        _cell_sort_kernel = kernel.Kernel('halo_cell_list_method', _cell_sort_code, headers = ['stdio.h'], static_args = _static_args)
        self._cell_sort_loop = build.SharedLib(_cell_sort_kernel, _cell_sort_dict, DEBUG = self._DEBUG)
        #==========================================================================================================================        
        
    
        _cell_shifts=[
                            [-1*self._extent[0] ,-1*self._extent[1]  ,-1*self._extent[2]],
                            [0.                 ,-1*self._extent[1]  ,-1*self._extent[2]],
                            [self._extent[0]    ,-1*self._extent[1]  ,-1*self._extent[2]],
                            [-1*self._extent[0] ,0.                  ,-1*self._extent[2]],
                            [0.                 ,0.                  ,-1*self._extent[2]],
                            [self._extent[0]    ,0.                  ,-1*self._extent[2]],
                            [-1*self._extent[0] ,self._extent[1]     ,-1*self._extent[2]],
                            [0.                 ,self._extent[1]     ,-1*self._extent[2]],
                            [self._extent[0]    ,self._extent[1]     ,-1*self._extent[2]],

                            [-1*self._extent[0] ,-1*self._extent[1]  ,0.],
                            [0.                 ,-1*self._extent[1]  ,0.],
                            [self._extent[0]    ,-1*self._extent[1]  ,0.],
                            [-1*self._extent[0] ,0.                  ,0.],
                            [self._extent[0]    ,0.                  ,0.],
                            [-1*self._extent[0] ,self._extent[1]     ,0.],
                            [0.                 ,self._extent[1]     ,0.],
                            [self._extent[0]    ,self._extent[1]     ,0.],

                            [-1*self._extent[0] ,-1*self._extent[1]  ,self._extent[2]],
                            [0.                 ,-1*self._extent[1]  ,self._extent[2]],
                            [self._extent[0]    ,-1*self._extent[1]  ,self._extent[2]],
                            [-1*self._extent[0] ,0.                  ,self._extent[2]],
                            [0.                 ,0.                  ,self._extent[2]],
                            [self._extent[0]    ,0.                  ,self._extent[2]],
                            [-1*self._extent[0] ,self._extent[1]     ,self._extent[2]],
                            [0.                 ,self._extent[1]     ,self._extent[2]],
                            [self._extent[0]    ,self._extent[1]     ,self._extent[2]]
                           ]    
        
        
        
        _tmp_list_local=[]
        for ix in range(26):
            _tmp_list_local+=_cell_shifts[ix]
        self._cell_shifts_array = data.ScalarArray(_tmp_list_local, dtype=ctypes.c_double) 
    
    
    
    
    @property
    def halo_times(self):        
        _tmp = 0.
        for i,h in enumerate(self._halos):
            _tmp+=h._time
        return _tmp
        
    
class Halo(object):
    """
    Class to contain a halo.
    """
    def __init__(self, MPICOMM = None, rank_local = 0, rank_dest = 0, rank_src = 0, local_index = None, cell_count = 1, nrow = 1, ncol = 1, dtype = ctypes.c_double):
        self._DEBUG = True
        assert local_index != None, "Error: No local index specified."
        
        self._MPI = MPICOMM
        self._rank = rank_local
        self._rd = rank_dest
        self._rs = rank_src
        self._MPIstatus=MPI.Status()
        
        
        self._li = local_index #make linear or 3 tuple? leading towards linear.
        self._nc = ncol
        self._nr = nrow
        self._dt = dtype
        self._cell_count = cell_count
        
        
        self._time = 0.        
        
        
        self._send_buffer = particle.Dat(1000, self._nc, name='send_buffer', dtype=ctypes.c_double)
        
    
    def exchange(self, count, cell_counts, recvd_cell_counts, cell_list, data_buffer):
         
        timer = True
        if (timer==True):
            start = time.time()         
        
        '''Send cell counts'''
        self._MPI.Sendrecv(cell_counts[0::], self._rd, self._rd, recvd_cell_counts, self._rs, self._rs, self._MPIstatus)        
      
        
        '''Send packed data'''
        self._MPI.Sendrecv(self._send_buffer.Dat[0:count:1,::], self._rd, self._rd, data_buffer.Dat[data_buffer.halo_start::,::], self._rs, self._rs, self._MPIstatus)
        
        
        _shift=self._MPIstatus.Get_count( data.mpi_map[data_buffer.dtype])
        data_buffer.halo_start_shift(_shift/self._nc)
        
        
        if (timer==True):
            end = time.time()
            self._time+=end - start         
         
        
        
    def __setitem__(self,ix, val):
        self._d[ix] = np.array([val],dtype=self._dt)    
        
    def __str__(self):
        return str(self._d)
        
    def __getitem__(self,ix):
        return self._d[ix]    
    
    @property
    def ctypes_data(self):
        '''Return ctypes-pointer to data.'''
        return self._d.ctypes.data_as(ctypes.POINTER(self._dt))
        
    @property
    def ncol(self):
        '''Return number of columns.'''
        return self._nc
        
    @property
    def nrow(self):
        '''Return number of rows.'''    
        return self._nr
        
    @property
    def index(self):
        '''Return local index.'''
        return self._li
        
    @property
    def dtype(self):
        ''' Return Dat c data ctype'''
        return self._dt
    
    @property
    def send_buffer(self):
        '''
        Return send buffer particle dat
        '''
        return self._send_buffer
    
    
    
    
    
    
    
    