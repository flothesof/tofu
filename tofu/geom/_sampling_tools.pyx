# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
#
################################################################################
# Utility functions for sampling and discretizating
################################################################################
from libc.math cimport ceil as Cceil, fabs as Cabs
from libc.math cimport floor as Cfloor, round as Cround
from libc.math cimport sqrt as Csqrt
from libc.math cimport isnan as Cisnan
from libc.math cimport NAN as Cnan
from libc.math cimport log2 as Clog2
from libc.stdlib cimport malloc, free, realloc
from cython.parallel import prange
from cython.parallel cimport parallel
from _basic_geom_tools cimport _VSMALL
# for utility functions:
import numpy as np
cimport numpy as cnp
# ==============================================================================
# =  LINEAR MESHING
# ==============================================================================
cdef inline long discretize_line1d_core(double* lminmax, double dstep,
                                        double[2] dl, bint lim,
                                        int mode, double margin,
                                        double** ldiscret_arr,
                                        double[1] resolution,
                                        long** lindex_arr, long[1] n) nogil:
    cdef int[1] nL0
    cdef long[1] nind

    first_discretize_line1d_core(lminmax, dstep,
                                 resolution, n, nind, nL0,
                                 dl, lim, mode, margin)
    if ldiscret_arr[0] == NULL:
        ldiscret_arr[0] = <double *>malloc(nind[0] * sizeof(double))
    else:
        ldiscret_arr[0] = <double *>realloc(ldiscret_arr[0],
                                            nind[0] * sizeof(double))
    if lindex_arr[0] == NULL:
        lindex_arr[0] = <long *>malloc(nind[0] * sizeof(long))
    else:
        lindex_arr[0] = <long *>realloc(lindex_arr[0], nind[0] * sizeof(long))
    second_discretize_line1d_core(lminmax, ldiscret_arr[0], lindex_arr[0],
                                  nL0[0], resolution[0], nind[0])
    return nind[0]

cdef inline void first_discretize_line1d_core(double* lminmax,
                                              double dstep,
                                              double[1] resolution,
                                              long[1] num_cells,
                                              long[1] nind,
                                              int[1] nl0,
                                              double[2] dl,
                                              bint lim,
                                              int mode,
                                              double margin) nogil:
    """
    Computes the resolution, the desired limits, and the number of cells when
    discretising the segmen lminmax with the given parameters. It doesn't do the
    actual discretization.
    For that part, please refer to: second_discretize_line1d_core
    """
    cdef int nl1, ii, jj
    cdef double abs0, abs1
    cdef double inv_resol, new_margin
    cdef double[2] desired_limits

    # .. Computing "real" discretization step, depending on `mode`..............
    if mode == 1: # absolute
        num_cells[0] = <int>Cceil((lminmax[1] - lminmax[0]) / dstep)
    else: # relative
        num_cells[0] = <int>Cceil(1./dstep)
    resolution[0] = (lminmax[1] - lminmax[0]) / num_cells[0]
    # .. Computing desired limits ..............................................
    if Cisnan(dl[0]) and Cisnan(dl[1]):
        desired_limits[0] = lminmax[0]
        desired_limits[1] = lminmax[1]
    else:
        if Cisnan(dl[0]):
            dl[0] = lminmax[0]
        if Cisnan(dl[1]):
            dl[1] = lminmax[1]
        if lim and dl[0]<=lminmax[0]:
            dl[0] = lminmax[0]
        if lim and dl[1]>=lminmax[1]:
            dl[1] = lminmax[1]
        desired_limits[0] = dl[0]
        desired_limits[1] = dl[1]
    # .. Get the extreme indices of the mesh elements that really need to be
    # created within those limits...............................................
    inv_resol = 1./resolution[0]
    new_margin = margin*resolution[0]
    abs0 = Cabs(desired_limits[0] - lminmax[0])
    if abs0 - resolution[0] * Cfloor(abs0 * inv_resol) < new_margin:
        nl0[0] = int(Cround((desired_limits[0] - lminmax[0]) * inv_resol))
    else:
        nl0[0] = int(Cfloor((desired_limits[0] - lminmax[0]) * inv_resol))
    abs1 = Cabs(desired_limits[1] - lminmax[0])
    if abs1 - resolution[0] * Cfloor(abs1 * inv_resol) < new_margin:
        nl1 = int(Cround((desired_limits[1] - lminmax[0]) * inv_resol) - 1)
    else:
        nl1 = int(Cfloor((desired_limits[1] - lminmax[0]) * inv_resol))
    # Get the total number of indices
    nind[0] = nl1 + 1 - nl0[0]
    return

cdef inline void second_discretize_line1d_core(double* lminmax,
                                               double* ldiscret,
                                               long* lindex,
                                               int nl0,
                                               double resolution,
                                               long nind) nogil:
    """
    Does the actual discretization of the segment lminmax.
    Computes the coordinates of the cells on the discretized segment and the
    associated list of indices.
    This function need some parameters computed with the first algorithm:
    first_discretize_line1d_core
    """
    cdef int ii, jj
    # .. Computing coordinates and indices .....................................
    for ii in range(nind):
        jj = nl0 + ii
        lindex[ii] = jj
        ldiscret[ii] = lminmax[0] + (0.5 + jj) * resolution
    return


cdef inline void simple_discretize_line1d(double[2] lminmax, double dstep,
                                          int mode, double margin,
                                          double** ldiscret_arr,
                                          double[1] resolution,
                                          long[1] n) nogil:
    """
    Similar version, more simple :
    - Not possible to define a sub set
    - Gives back a discretized line WITH the min boundary
    - WITHOUT max boundary
    """
    cdef int ii
    cdef int numcells
    cdef double resol
    cdef double first = lminmax[0]

    if mode == 1: # absolute
        numcells = <int>Cceil((lminmax[1] - first) / dstep)
    else: # relative
        num_cells = <int>Cceil(1./dstep)
    if num_cells < 1 :
        num_cells = 1
    resol = (lminmax[1] - first) / numcells
    resolution[0] = resol
    n[0] = numcells
    if ldiscret_arr[0] == NULL:
        ldiscret_arr[0] = <double *>malloc(n[0] * sizeof(double))
    else:
        ldiscret_arr[0] = <double *>realloc(ldiscret_arr[0],
							n[0] * sizeof(double))
    for ii in range(numcells):
        ldiscret_arr[0][ii] = first + resol * ii
    return

# ==============================================================================
# =  Vessel's poloidal cut discretization
# ==============================================================================

cdef inline void discretize_vpoly_core(double[:, ::1] ves_poly, double dstep,
                                       int mode, double margin, double din,
                                       double[:, ::1] ves_vin,
                                       double** xcross, double** ycross,
                                       double** reso, long** ind,
                                       long** numcells, double** rref,
                                       double** xpolybis, double** ypolybis,
                                       int[1] tot_sz_vb, int[1] tot_sz_ot,
                                       int np) nogil:
    cdef Py_ssize_t sz_vbis = 0
    cdef Py_ssize_t sz_others = 0
    cdef Py_ssize_t last_sz_vbis = 0
    cdef Py_ssize_t last_sz_othr = 0
    cdef int ii, jj
    cdef double v0, v1
    cdef double rv0, rv1
    cdef double inv_norm
    cdef double shiftx, shifty
    cdef double[1] loc_resolu
    cdef double[2] lminmax
    cdef double[2] dl_array
    cdef double* ldiscret = NULL
    cdef long* lindex = NULL

    #.. initialization..........................................................
    lminmax[0] = 0.
    dl_array[0] = Cnan
    dl_array[1] = Cnan
    numcells[0] = <long*>malloc((np-1)*sizeof(long))
    #.. Filling arrays..........................................................
    if Cabs(din) < _VSMALL:
        for ii in range(np-1):
            v0 = ves_poly[0,ii+1]-ves_poly[0,ii]
            v1 = ves_poly[1,ii+1]-ves_poly[1,ii]
            lminmax[1] = Csqrt(v0 * v0 + v1 * v1)
            inv_norm = 1. / lminmax[1]
            discretize_line1d_core(lminmax, dstep, dl_array, True,
                                   mode, margin, &ldiscret, loc_resolu,
                                   &lindex, &numcells[0][ii])
            # .. preparing Poly bis array......................................
            last_sz_vbis = sz_vbis
            sz_vbis += 1 + numcells[0][ii]
            xpolybis[0] = <double*>realloc(xpolybis[0], sz_vbis*sizeof(double))
            ypolybis[0] = <double*>realloc(ypolybis[0], sz_vbis*sizeof(double))
            xpolybis[0][sz_vbis - (1 + numcells[0][ii])] = ves_poly[0, ii]
            ypolybis[0][sz_vbis - (1 + numcells[0][ii])] = ves_poly[1, ii]
            # .. preparing other arrays ........................................
            last_sz_othr = sz_others
            sz_others += numcells[0][ii]
            reso[0] = <double*>realloc(reso[0], sizeof(double)*sz_others)
            rref[0] = <double*>realloc(rref[0], sizeof(double)*sz_others)
            xcross[0] = <double*>realloc(xcross[0], sizeof(double)*sz_others)
            ycross[0] = <double*>realloc(ycross[0], sizeof(double)*sz_others)
            ind[0] = <long*>realloc(ind[0], sizeof(long)*sz_others)
            # ...
            v0 = v0 * inv_norm
            v1 = v1 * inv_norm
            rv0 = loc_resolu[0]*v0
            rv1 = loc_resolu[0]*v1
            for jj in range(numcells[0][ii]):
                ind[0][last_sz_othr + jj] = last_sz_othr + jj
                reso[0][last_sz_othr + jj] = loc_resolu[0]
                rref[0][last_sz_othr + jj] = ves_poly[0,ii] + ldiscret[jj] * v0
                xcross[0][last_sz_othr + jj] = ves_poly[0,ii] + ldiscret[jj] * v0
                ycross[0][last_sz_othr + jj] = ves_poly[1,ii] + ldiscret[jj] * v1
                xpolybis[0][last_sz_vbis + jj] = ves_poly[0,ii] + jj * rv0
                ypolybis[0][last_sz_vbis + jj] = ves_poly[1,ii] + jj * rv1
        # We close the polygon of VPolybis
        sz_vbis += 1
        xpolybis[0] = <double*>realloc(xpolybis[0], sz_vbis*sizeof(double))
        ypolybis[0] = <double*>realloc(ypolybis[0], sz_vbis*sizeof(double))
        xpolybis[0][sz_vbis - 1] = ves_poly[0, 0]
        ypolybis[0][sz_vbis - 1] = ves_poly[1, 0]
    else:
        for ii in range(np-1):
            v0 = ves_poly[0,ii+1]-ves_poly[0,ii]
            v1 = ves_poly[1,ii+1]-ves_poly[1,ii]
            lminmax[1] = Csqrt(v0 * v0 + v1 * v1)
            inv_norm = 1. / lminmax[1]
            discretize_line1d_core(lminmax, dstep, dl_array, True,
                                   mode, margin, &ldiscret, loc_resolu,
                                   &lindex, &numcells[0][ii])
            # .. prepaaring Poly bis array......................................
            last_sz_vbis = sz_vbis
            sz_vbis += 1 + numcells[0][ii]
            xpolybis[0] = <double*>realloc(xpolybis[0], sz_vbis*sizeof(double))
            ypolybis[0] = <double*>realloc(ypolybis[0], sz_vbis*sizeof(double))
            xpolybis[0][sz_vbis - (1 + numcells[0][ii])] = ves_poly[0, ii]
            ypolybis[0][sz_vbis - (1 + numcells[0][ii])] = ves_poly[1, ii]
            # .. preparing other arrays ........................................
            last_sz_othr = sz_others
            sz_others += numcells[0][ii]
            reso[0]  = <double*>realloc(reso[0],  sizeof(double)*sz_others)
            rref[0]   = <double*>realloc(rref[0],   sizeof(double)*sz_others)
            xcross[0] = <double*>realloc(xcross[0], sizeof(double)*sz_others)
            ycross[0] = <double*>realloc(ycross[0], sizeof(double)*sz_others)
            ind[0] = <long*>realloc(ind[0], sizeof(long)*sz_others)
            # ...
            v0 = v0 * inv_norm
            v1 = v1 * inv_norm
            rv0 = loc_resolu[0]*v0
            rv1 = loc_resolu[0]*v1
            shiftx = din*ves_vin[0,ii]
            shifty = din*ves_vin[1,ii]
            for jj in range(numcells[0][ii]):
                ind[0][last_sz_othr] = last_sz_othr
                reso[0][last_sz_othr] = loc_resolu[0]
                rref[0][last_sz_othr]   = ves_poly[0,ii] + ldiscret[jj]*v0
                xcross[0][last_sz_othr] = ves_poly[0,ii] + ldiscret[jj]*v0 + shiftx
                ycross[0][last_sz_othr] = ves_poly[1,ii] + ldiscret[jj]*v1 + shifty
                xpolybis[0][last_sz_vbis + jj] = ves_poly[0,ii] + jj * rv0
                ypolybis[0][last_sz_vbis + jj] = ves_poly[1,ii] + jj * rv1
                last_sz_othr += 1
        # We close the polygon of VPolybis
        sz_vbis += 1
        xpolybis[0] = <double*>realloc(xpolybis[0], sz_vbis*sizeof(double))
        ypolybis[0] = <double*>realloc(ypolybis[0], sz_vbis*sizeof(double))
        xpolybis[0][sz_vbis - 1] = ves_poly[0, 0]
        ypolybis[0][sz_vbis - 1] = ves_poly[1, 0]
    tot_sz_vb[0] = sz_vbis
    tot_sz_ot[0] = sz_others
    return


# ------------------------------------------------------------------------------
# - Simplified version of previous algo
# ------------------------------------------------------------------------------
cdef inline void simple_discretize_vpoly_core(double[:, ::1] ves_poly,
                                              int num_pts,
                                              double dstep,
                                              double** xcross,
                                              double** ycross,
                                              int[1] new_nb_pts,
                                              int mode,
                                              double margin) nogil:
    cdef Py_ssize_t sz_others = 0
    cdef Py_ssize_t last_sz_othr = 0
    cdef int ii, jj
    cdef double v0, v1
    cdef double inv_norm
    cdef double[1] loc_resolu
    cdef double[2] lminmax
    cdef long[1] numcells
    cdef double* ldiscret = NULL
    #.. initialization..........................................................
    lminmax[0] = 0.
    #.. Filling arrays..........................................................
    for ii in range(num_pts-1):
        v0 = ves_poly[0,ii+1]-ves_poly[0,ii]
        v1 = ves_poly[1,ii+1]-ves_poly[1,ii]
        lminmax[1] = Csqrt(v0 * v0 + v1 * v1)
        inv_norm = 1. / lminmax[1]
        simple_discretize_line1d(lminmax, dstep, mode, margin,
                                 &ldiscret, loc_resolu, &numcells[0])
        # .. preparing other arrays ........................................
        last_sz_othr = sz_others
        sz_others += numcells[0]
        xcross[0] = <double*>realloc(xcross[0], sizeof(double)*sz_others)
        ycross[0] = <double*>realloc(ycross[0], sizeof(double)*sz_others)
        # ...
        v0 = v0 * inv_norm
        v1 = v1 * inv_norm
        for jj in range(numcells[0]):
            xcross[0][last_sz_othr + jj] = ves_poly[0,ii] + ldiscret[jj] * v0
            ycross[0][last_sz_othr + jj] = ves_poly[1,ii] + ldiscret[jj] * v1
    # We close the polygon of VPolybis
    new_nb_pts[0] = sz_others
    free(ldiscret)
    return


# ==============================================================================
# == LOS sampling
# ==============================================================================

# -- Quadrature Rules : Middle Rule --------------------------------------------
cdef inline void middle_rule_rel_single(int num_raf,
                                        double los_kmin,
                                        double loc_resol,
                                        double* los_coeffs) nogil:
    # Middle quadrature rule with relative resolution step
    # for a single particle
    cdef Py_ssize_t jj
    for jj in range(num_raf):
        los_coeffs[jj] = los_kmin + (0.5 + jj)*loc_resol
    return

cdef inline void middle_rule_rel(int num_los, int num_raf,
                                 double* los_kmin,
                                 double* los_kmax,
                                 double* los_resolution,
                                 double* los_coeffs,
                                 long* los_ind,
                                 int num_threads) nogil:
    # Middle quadrature rule with relative resolution step
    # for MULTIPLE LOS
    cdef Py_ssize_t ii
    cdef int first_index
    cdef double inv_nraf
    cdef double loc_resol
    inv_nraf = 1./num_raf
    with nogil, parallel(num_threads=num_threads):
        for ii in prange(num_los):
            if ii == 0:
                los_ind[ii] = num_raf
            else:
                los_ind[ii] = num_raf + los_ind[ii-1]
                loc_resol = (los_kmax[ii] - los_kmin[ii])*inv_nraf
                los_resolution[ii] = loc_resol
                first_index = ii*num_raf
                middle_rule_rel_single(num_raf, los_kmin[ii],
                                       loc_resol, &los_coeffs[first_index])
    return

cdef inline void middle_rule_abs_1_single(double inv_resol,
                                          double los_kmin,
                                          double los_kmax,
                                          double* los_resolution,
                                          long* ind_cum) nogil:
    # Middle quadrature rule with absolute resolution step
    # for one LOS
    # First step of the function, this function should be called
    # before middle_rule_abs_2, this function computes the resolutions
    # and the right indices
    cdef long num_raf
    cdef double seg_length
    cdef double loc_resol
    # ...
    seg_length = los_kmax - los_kmin
    num_raf = <long>(Cceil(seg_length*inv_resol))
    loc_resol = seg_length / num_raf
    los_resolution[0] = loc_resol
    ind_cum[0] = num_raf
    return


cdef inline void middle_rule_abs_1(int num_los, double resol,
                                   double* los_kmin,
                                   double* los_kmax,
                                   double* los_resolution,
                                   long* ind_cum,
                                   int num_threads) nogil:
    # Middle quadrature rule with absolute resolution step
    # for SEVERAL LOS
    # First step of the function, this function should be called
    # before middle_rule_abs_2, this function computes the resolutions
    # and the right indices
    cdef Py_ssize_t ii
    cdef double inv_resol
    # ...
    with nogil, parallel(num_threads=num_threads):
        inv_resol = 1./resol
        for ii in prange(num_los):
            middle_rule_abs_1_single(inv_resol, los_kmin[ii],
                                     los_kmax[ii],
                                     &los_resolution[ii],
                                     &ind_cum[ii])
    return

cdef inline void middle_rule_abs_2_single(long num_raf,
                                          double loc_x,
                                          double loc_resol,
                                          double* los_coeffs,
                                          int num_threads) nogil:
    # Middle quadrature rule with absolute resolution step
    # for one LOS
    # First step of the function, this function should be called
    # before middle_rule_abs_2, this function computes the coeffs
    cdef Py_ssize_t jj
    with nogil, parallel(num_threads=num_threads):
        for jj in prange(num_raf):
            los_coeffs[jj] = loc_x + (0.5 + jj) * loc_resol
    return

cdef inline void middle_rule_abs_2(int num_los,
                                   double* los_kmin,
                                   long* ind_cum,
                                   double* los_resolution,
                                   double* los_coeffs,
                                   int num_threads) nogil:
    # Middle quadrature rule with absolute resolution step
    # for SEVERAL LOS
    # First step of the function, this function should be called
    # before middle_rule_abs_2, this function computes the coeffs
    cdef Py_ssize_t ii
    cdef long num_raf
    cdef long first_index
    cdef double loc_resol
    cdef double loc_x
    # filling tab......
    for ii in range(num_los):
        num_raf = ind_cum[ii]
        if ii==0:
            first_index = 0
        else:
            first_index = ind_cum[ii-1]
            ind_cum[ii] = first_index + ind_cum[ii]
        loc_resol = los_resolution[ii]
        loc_x = los_kmin[ii]
        middle_rule_abs_2_single(num_raf, loc_x, loc_resol,
                                 &los_coeffs[first_index],
                                 num_threads)
    return


cdef inline void middle_rule_abs_var_single(int num_raf,
                                            double loc_resol,
                                            double los_kmin,
                                            double* los_coeffs) nogil:
    # Middle quadrature rule with absolute variable resolution step
    # for one LOS
    cdef Py_ssize_t jj
    # ...
    for jj in range(num_raf):
        los_coeffs[jj] = los_kmin + (0.5 + jj) * loc_resol
    return


cdef inline void middle_rule_abs_var_step1(int num_los, double* resolutions,
                                           double* los_kmin,
                                           double* los_kmax,
                                           double* los_resolution,
                                           double** los_coeffs,
                                           long* los_ind,
                                           int num_threads) nogil:
    # Middle quadrature rule with absolute variable resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii
    cdef int num_raf
    cdef int first_index
    cdef double loc_resol
    cdef double seg_length
    # ...
    for ii in range(num_los):
        seg_length = los_kmax[ii] - los_kmin[ii]
        num_raf = <int>(Cceil(seg_length/resolutions[ii]))
        loc_resol = seg_length / num_raf
        los_resolution[ii] = loc_resol
        if ii == 0:
            los_ind[ii] = num_raf
            first_index = 0
        else:
            first_index = los_ind[ii-1]
            los_ind[ii] = num_raf + first_index
    return




cdef inline void middle_rule_abs_var_step2(int num_los, double* resolutions,
                                     double* los_kmin,
                                     double* los_kmax,
                                     double* los_resolution,
                                     double** los_coeffs,
                                     long* los_ind,
                                     int num_threads) nogil:
    # Middle quadrature rule with absolute variable resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii
    cdef int num_raf
    cdef int first_index
    cdef double loc_resol
    cdef double seg_length
    # ...
    for ii in range(num_los):
        if ii == 0:
            first_index = 0
        else:
            first_index = los_ind[ii-1]
        loc_resol = seg_length / num_raf
        loc_resol = los_resolution[ii]
        middle_rule_abs_var_single(num_raf,
                                   loc_resol,
                                   los_kmin[ii],
                                   &los_coeffs[0][first_index])
    return



cdef inline void middle_rule_abs_var_2s(int num_los, double* resolutions,
                                     double* los_kmin,
                                     double* los_kmax,
                                     double* los_resolution,
                                     double** los_coeffs,
                                     long* los_ind,
                                     int num_threads) nogil:
    # Middle quadrature rule with absolute variable resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii
    cdef int num_raf
    cdef int first_index
    cdef double loc_resol
    cdef double seg_length
    middle_rule_abs_var_step1(num_los, resolutions, los_kmin, los_kmax,
                              los_resolution, los_coeffs,
                              los_ind, num_threads)
    middle_rule_abs_var_step2(num_los, resolutions, los_kmin, los_kmax,
                              los_resolution, los_coeffs,
                              los_ind, num_threads)

    # ...
    return


cdef inline void middle_rule_abs_var(int num_los, double* resolutions,
                                     double* los_kmin,
                                     double* los_kmax,
                                     double* los_resolution,
                                     double** los_coeffs,
                                     long* los_ind,
                                     int num_threads) nogil:
    with gil:
        print("........................ here ........................")
    # Middle quadrature rule with absolute variable resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii
    cdef int num_raf
    cdef int first_index
    cdef double loc_resol
    cdef double seg_length
    # ...
    for ii in range(num_los):
        seg_length = los_kmax[ii] - los_kmin[ii]
        num_raf = <int>(Cceil(seg_length/resolutions[ii]))
        loc_resol = seg_length / num_raf
        los_resolution[ii] = loc_resol
        if ii == 0:
            los_ind[ii] = num_raf
            los_coeffs[0] = <double*>malloc(num_raf * sizeof(double))
            first_index = 0
        else:
            first_index = los_ind[ii-1]
            los_ind[ii] = num_raf + first_index
            los_coeffs[0] = <double*>realloc(los_coeffs[0],
                                          los_ind[ii] * sizeof(double))
        middle_rule_abs_var_single(num_raf,
                                   loc_resol,
                                   los_kmin[ii],
                                       &los_coeffs[0][first_index])
    return


cdef inline void middle_rule_rel_var_single(int num_raf,
                                            double loc_resol,
                                            double los_kmin,
                                            double* los_coeffs) nogil:
    # Middle quadrature rule with relative variable resolution step
    # for one LOS
    cdef Py_ssize_t jj
    # ...
    for jj in prange(num_raf):
        los_coeffs[jj] = los_kmin + (0.5 + jj) * loc_resol
    return

cdef inline void middle_rule_rel_var(int num_los, double* resolutions,
                                     double* los_kmin,
                                     double* los_kmax,
                                     double* los_resolution,
                                     double** los_coeffs,
                                     long* los_ind,
                                     int num_threads) nogil:
    # Middle quadrature rule with relative variable resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii
    cdef int num_raf
    cdef int first_index
    cdef double seg_length
    cdef double loc_resol
    # ...
    for ii in range(num_los):
        num_raf = <int>(Cceil(1./resolutions[ii]))
        loc_resol = 1./num_raf
        los_resolution[ii] = loc_resol
        if ii == 0:
            first_index = 0
            los_ind[ii] = num_raf
            los_coeffs[0] = <double*>malloc(num_raf * sizeof(double))
        else:
            first_index = los_ind[ii-1]
            los_ind[ii] = num_raf + first_index
            los_coeffs[0] = <double*>realloc(los_coeffs[0],
                                          los_ind[ii] * sizeof(double))
        middle_rule_rel_var_single(num_raf, loc_resol, los_kmin[ii],
                                   &los_coeffs[0][first_index])
    return

# -- Quadrature Rules : Left Rule ----------------------------------------------
cdef inline void left_rule_rel_single(int num_raf,
                                      double inv_nraf,
                                      double loc_x,
                                      double loc_resol,
                                      double* los_coeffs) nogil:
    # Left quadrature rule with relative resolution step
    # for one LOS
    cdef Py_ssize_t jj
    # ...
    for jj in range(num_raf + 1):
        los_coeffs[jj] = loc_x + jj * loc_resol
    return


cdef inline void left_rule_rel(int num_los, int num_raf,
                               double* los_kmin,
                               double* los_kmax,
                               double* los_resolution,
                               double* los_coeffs,
                               long* los_ind, int num_threads) nogil:
    # Left quadrature rule with relative resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii
    cdef int first_index
    cdef double inv_nraf
    cdef double loc_resol
    cdef double loc_x
    inv_nraf = 1./num_raf
    # ...
    with nogil, parallel(num_threads=num_threads):
        for ii in prange(num_los):
            loc_x = los_kmin[ii]
            loc_resol = (los_kmax[ii] - loc_x)*inv_nraf
            los_resolution[ii] = loc_resol
            first_index = ii*(num_raf + 1)
            los_ind[ii] = first_index + num_raf + 1
            left_rule_rel_single(num_raf, inv_nraf, loc_x, loc_resol,
                                 &los_coeffs[first_index])
    return

cdef inline void simps_left_rule_abs_single(int num_raf,
                                            double loc_resol,
                                            double los_kmin,
                                            double* los_coeffs) nogil:
    # Simpson left quadrature rule with absolute resolution step
    # for one LOS
    cdef Py_ssize_t jj
    # ...
    for jj in prange(num_raf + 1):
        los_coeffs[jj] = los_kmin + jj * loc_resol
    return


cdef inline void simps_left_rule_abs(int num_los, double resol,
                                     double* los_kmin,
                                     double* los_kmax,
                                     double* los_resolution,
                                     double** los_coeffs,
                                     long* los_ind,
                                     int num_threads) nogil:
    # Simpson left quadrature rule with absolute resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii, jj
    cdef int num_raf
    cdef int first_index
    cdef double seg_length
    cdef double loc_resol
    cdef double inv_resol = 1./resol
    # ...
    for ii in range(num_los):
        seg_length = los_kmax[ii] - los_kmin[ii]
        num_raf = <int>(Cceil(seg_length*inv_resol))
        if num_raf%2==1:
            num_raf = num_raf + 1
        loc_resol = seg_length / num_raf
        los_resolution[ii] = loc_resol
        if ii == 0:
            first_index = 0
            los_ind[ii] = num_raf + 1
            los_coeffs[0] = <double*>malloc((num_raf + 1) * sizeof(double))
        else:
            first_index = los_ind[ii -1]
            los_ind[ii] = num_raf +  1 + first_index
            los_coeffs[0] = <double*>realloc(los_coeffs[0],
                                             los_ind[ii] * sizeof(double))
        simps_left_rule_abs_single(num_raf, loc_resol, los_kmin[ii],
                                   &los_coeffs[0][first_index])
    return

cdef inline void romb_left_rule_abs_single(int num_raf,
                                           double loc_resol,
                                           double los_kmin,
                                           double* los_coeffs) nogil:
    # Romboid left quadrature rule with relative resolution step
    # for one LOS
    cdef Py_ssize_t jj
    # ...
    for jj in prange(num_raf + 1):
        los_coeffs[jj] = los_kmin + jj * loc_resol
    return

cdef inline void romb_left_rule_abs(int num_los, double resol,
                                    double* los_kmin,
                                    double* los_kmax,
                                    double* los_resolution,
                                    double** los_coeffs,
                                    long* los_ind, int num_threads) nogil:
    # Romboid left quadrature rule with relative resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii, jj
    cdef int num_raf
    cdef int first_index
    cdef double seg_length
    cdef double loc_resol
    cdef double inv_resol = 1./resol
    # ...
    for ii in range(num_los):
        seg_length = los_kmax[ii] - los_kmin[ii]
        num_raf = <int>(Cceil(seg_length*inv_resol))
        num_raf = 2**(<int>(Cceil(Clog2(num_raf))))
        loc_resol = seg_length / num_raf
        los_resolution[ii] = loc_resol
        if ii == 0:
            first_index = 0
            los_ind[ii] = num_raf + 1
            los_coeffs[0] = <double*>malloc((num_raf + 1) * sizeof(double))
        else:
            first_index = los_ind[ii-1]
            los_ind[ii] = num_raf +  1 + first_index
            los_coeffs[0] = <double*>realloc(los_coeffs[0],
                                             los_ind[ii] * sizeof(double))
        romb_left_rule_abs_single(num_raf, loc_resol, los_kmin[ii],
                                  &los_coeffs[0][first_index])
    return


cdef inline void simps_left_rule_rel_var_single(int num_raf,
                                                double loc_resol,
                                                double los_kmin,
                                                double* los_coeffs) nogil:
    # Simpson left quadrature rule with variable relative resolution step
    # for one LOS
    cdef Py_ssize_t jj
    # ...
    for jj in prange(num_raf + 1):
        los_coeffs[jj] = los_kmin + jj * loc_resol
    return

cdef inline void simps_left_rule_rel_var(int num_los, double* resolutions,
                                         double* los_kmin,
                                         double* los_kmax,
                                         double* los_resolution,
                                         double** los_coeffs,
                                         long* los_ind,
                                         int num_threads) nogil:
    # Simpson left quadrature rule with variable relative resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii
    cdef int num_raf
    cdef int first_index
    cdef double loc_resol
    # ...
    for ii in range(num_los):
        num_raf = <int>(Cceil(1./resolutions[ii]))
        if num_raf%2==1:
            num_raf = num_raf+1
        loc_resol = 1. / num_raf
        los_resolution[ii] = loc_resol
        if ii == 0:
            first_index = 0
            los_ind[ii] = num_raf + 1
            los_coeffs[0] = <double*>malloc((num_raf + 1) * sizeof(double))
        else:
            first_index = los_ind[ii-1]
            los_ind[ii] = num_raf +  1 + first_index
            los_coeffs[0] = <double*>realloc(los_coeffs[0],
                                             los_ind[ii] * sizeof(double))
        simps_left_rule_rel_var_single(num_raf, loc_resol, los_kmin[ii],
                                       &los_coeffs[0][first_index])
    return



cdef inline void simps_left_rule_abs_var_single(int num_raf,
                                                double loc_resol,
                                                double los_kmin,
                                                double* los_coeffs) nogil:
    # Simpson left quadrature rule with absolute variable resolution step
    # for one LOS
    cdef Py_ssize_t jj
    # ...
    for jj in prange(num_raf + 1):
        los_coeffs[jj] = los_kmin + jj * loc_resol
    return

cdef inline void simps_left_rule_abs_var(int num_los, double* resolutions,
                                         double* los_kmin,
                                         double* los_kmax,
                                         double* los_resolution,
                                         double** los_coeffs,
                                         long* los_ind,
                                         int num_threads) nogil:
    # Simpson left quadrature rule with absolute variable resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii, jj
    cdef int num_raf
    cdef int first_index
    cdef double seg_length
    cdef double loc_resol
    # ...
    for ii in range(num_los):
        seg_length = los_kmax[ii] - los_kmin[ii]
        num_raf = <int>(Cceil(seg_length/resolutions[ii]))
        if num_raf%2==1:
            num_raf = num_raf+1
        loc_resol = seg_length / num_raf
        los_resolution[ii] = loc_resol
        if ii == 0:
            first_index = 0
            los_ind[ii] = num_raf + 1
            los_coeffs[0] = <double*>malloc((num_raf + 1) * sizeof(double))
        else:
            first_index = los_ind[ii-1]
            los_ind[ii] = num_raf +  1 + first_index
            los_coeffs[0] = <double*>realloc(los_coeffs[0],
                                             los_ind[ii] * sizeof(double))
        simps_left_rule_abs_var_single(num_raf, loc_resol,
                                       los_kmin[ii],
                                       &los_coeffs[0][first_index])
    return

cdef inline void romb_left_rule_rel_var_single(int num_raf,
                                               double loc_resol,
                                               double los_kmin,
                                               double* los_coeffs) nogil:
    # Romboid left quadrature rule with relative variable resolution step
    # for ONE LOS
    cdef Py_ssize_t jj
    # ...
    for jj in prange(num_raf + 1):
        los_coeffs[jj] = los_kmin + jj * loc_resol
    return


cdef inline void romb_left_rule_rel_var(int num_los, double* resolutions,
                                        double* los_kmin,
                                        double* los_kmax,
                                        double* los_resolution,
                                        double** los_coeffs,
                                        long* los_ind,
                                        int num_threads) nogil:
    # Romboid left quadrature rule with relative variable resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii, jj
    cdef int num_raf
    cdef int first_index
    cdef double loc_resol
    # ...
    for ii in range(num_los):
        num_raf = <int>(Cceil(1./resolutions[ii]))
        num_raf = 2**(<int>(Cceil(Clog2(num_raf))))
        loc_resol = 1. / num_raf
        los_resolution[ii] = loc_resol
        if ii == 0:
            first_index = 0
            los_ind[ii] = num_raf + 1
            los_coeffs[0] = <double*>malloc((num_raf + 1) * sizeof(double))
        else:
            first_index = los_ind[ii-1]
            los_ind[ii] = num_raf +  1 + first_index
            los_coeffs[0] = <double*>realloc(los_coeffs[0],
                                             los_ind[ii] * sizeof(double))
        romb_left_rule_rel_var_single(num_raf, loc_resol, los_kmin[ii],
                                      &los_coeffs[0][first_index])
    return


cdef inline void romb_left_rule_abs_var_single(int num_raf,
                                               double loc_resol,
                                               double los_kmin,
                                               double* los_coeffs) nogil:
    # Romboid left quadrature rule with absolute variable resolution step
    # for ONE LOS
    cdef Py_ssize_t jj
    # ...
    for jj in prange(num_raf + 1):
        los_coeffs[jj] = los_kmin + jj * loc_resol
    return

cdef inline void romb_left_rule_abs_var(int num_los, double* resolutions,
                                        double* los_kmin,
                                        double* los_kmax,
                                        double* los_resolution,
                                        double** los_coeffs,
                                        long* los_ind,
                                        int num_threads) nogil:
    # Romboid left quadrature rule with absolute variable resolution step
    # for SEVERAL LOS
    cdef Py_ssize_t ii, jj
    cdef int num_raf
    cdef int first_index
    cdef double seg_length
    cdef double loc_resol
    # ...
    for ii in range(num_los):
        seg_length = los_kmax[ii] - los_kmin[ii]
        num_raf = <int>(Cceil(seg_length/resolutions[ii]))
        num_raf = 2**(<int>(Cceil(Clog2(num_raf))))
        loc_resol = seg_length / num_raf
        los_resolution[ii] = loc_resol
        if ii == 0:
            first_index = 0
            los_ind[ii] = num_raf + 1
            los_coeffs[0] = <double*>malloc((num_raf + 1) * sizeof(double))
        else:
            first_index = los_ind[ii-1]
            los_ind[ii] = num_raf +  1 + first_index
            los_coeffs[0] = <double*>realloc(los_coeffs[0],
                                             los_ind[ii] * sizeof(double))

        romb_left_rule_abs_var_single(num_raf, loc_resol, los_kmin[ii],
                                      &los_coeffs[0][first_index])
    return

# -- Get number of integration mode --------------------------------------------
cdef inline int get_nb_imode(str imode) :
    # gil required...........
    if imode == 'sum':
        return 0
    if imode == 'simps':
        return 1
    if imode == 'romb':
        return 2
    return -1

cdef inline int get_nb_dmode(str dmode) :
    # gil required...........
    if dmode == 'rel':
        return 1
    return 0 # absolute


# ==============================================================================
# == LOS sampling Algorithm for a SINGLE LOS
# ==============================================================================
cdef inline int los_get_sample_single(double los_kmin, double los_kmax,
                                      double resol, int n_dmode, int n_imode,
                                      double[1] eff_res,
                                      double** coeffs) nogil:
    """
    Sampling line of sight of origin ray_orig, direction vector ray_vdir,
    with discretization step resol, using the discretization method n_dmode,
    and the quadrature rule n_imode. los_kmin defines the first limit of the LOS
    Out parameters
    --------------
    eff_res : effective resolution used
    coeffs : 'k' coefficients on ray.
    Returns
    =======
       size of elements in coeffs[0]
    The different type of discretizations and quadratures:
    n_dmode
    =======
      - 0 : the discretization step given is absolute ('abs')
      - 1 : the discretization step given is relative ('rel')
    n_imode
    =====
      - 0 : 'sum' quadrature, using the n segment centers
      - 1 : 'simps' return n+1 egdes, n even (for scipy.integrate.simps)
      - 2 : 'romb' return n+1 edges, n+1 = 2**k+1 (for scipy.integrate.romb)
    """
    cdef int nraf
    cdef long[1] ind_cum
    cdef double invnraf
    cdef double invresol
    cdef double seg_length
    # ...
    if n_dmode == 1:
        # discretization step is relative
        nraf = <int> Cceil(1./resol)
        if n_imode==0:
            # 'sum' quad
            coeffs[0] = <double*>malloc(nraf*sizeof(double))
            eff_res[0] = (los_kmax - los_kmin)/resol
            middle_rule_rel_single(nraf, los_kmin, eff_res[0],
                                   &coeffs[0][0])
            return nraf
        elif n_imode==1:
            # 'simps' quad
            if nraf%2==1:
                nraf = nraf+1
            invnraf = 1./nraf
            coeffs[0] = <double*>malloc((nraf + 1)*sizeof(double))
            eff_res[0] = (los_kmax - los_kmin)*invnraf
            left_rule_rel_single(nraf, invnraf, los_kmin,
                                 eff_res[0], &coeffs[0][0])
            return nraf + 1
        elif n_imode==2:
            # 'romb' quad
            nraf = 2**(<int>(Cceil(Clog2(nraf))))
            invnraf = 1./nraf
            coeffs[0] = <double*>malloc((nraf + 1)*sizeof(double))
            eff_res[0] = (los_kmax - los_kmin)*invnraf
            left_rule_rel_single(nraf, invnraf, los_kmin,
                                 eff_res[0], &coeffs[0][0])
            return nraf + 1
    else:
        # discretization step is absolute, n_dmode==0
        if n_imode==0:
            # 'sum' quad
            invresol = 1./resol
            middle_rule_abs_1_single(invresol, los_kmin, los_kmax,
                                         &eff_res[0], &ind_cum[0])
            coeffs[0] = <double*>malloc((ind_cum[0])*sizeof(double))
            middle_rule_abs_2_single(ind_cum[0], los_kmin, eff_res[0],
                                     &coeffs[0][0], 32)
            return ind_cum[0]
        elif n_imode==1:
            # 'simps' quad
            seg_length = los_kmax - los_kmin
            nraf = <int>(Cceil(seg_length/resol))
            if nraf%2==1:
                nraf = nraf+1
            eff_res[0] = seg_length / nraf
            coeffs[0] = <double*>malloc((nraf+1)*sizeof(double))
            simps_left_rule_abs_single(nraf, eff_res[0],
                                       los_kmin, &coeffs[0][0])
            return nraf + 1
        elif n_imode==2:
            # 'romb' quad
            seg_length = los_kmax - los_kmin
            nraf = <int>(Cceil(seg_length/resol))
            nraf = 2**(<int>(Cceil(Clog2(nraf))))
            eff_res[0] = seg_length / nraf
            coeffs[0] = <double*>malloc((nraf+1)*sizeof(double))
            romb_left_rule_abs_single(nraf, eff_res[0], los_kmin,
                                      &coeffs[0][0])
            return nraf + 1
    return -1


# ==============================================================================
# == Utility functions for signal computation (LOS_calc_signal)
# ==============================================================================

# -- anisotropic case ----------------------------------------------------
cdef inline call_get_sample_single_ani(double los_kmin, double los_kmax,
                                       double resol,
                                       int n_dmode, int n_imode,
                                       double[1] eff_res,
                                       double[:,::1] ray_orig,
                                       double[:,::1] ray_vdir):
    # This function doesn't compute anything new.
    # It's a utility function for LOS_calc_signal to avoid reptitions
    # It samples a LOS and recreates the points on that LOS
    # plus this is for the anisotropic version so it also compute usbis
    cdef int sz_coeff
    cdef double** los_coeffs = NULL
    cdef cnp.ndarray[double,ndim=1,mode='c'] ksbis
    cdef cnp.ndarray[double,ndim=2,mode='c'] usbis
    cdef cnp.ndarray[double,ndim=2,mode='c'] pts

    # Initialization utility array
    los_coeffs = <double**>malloc(sizeof(double*))
    los_coeffs[0] = NULL
    # Sampling
    sz_coeff = los_get_sample_single(los_kmin, los_kmax,
                                     resol,
                                     n_dmode, n_imode,
                                     &eff_res[0],
                                     &los_coeffs[0])
    # computing points
    usbis = np.repeat(ray_vdir, sz_coeff, axis=1)
    ksbis = np.asarray(<double[:sz_coeff]>los_coeffs[0])
    pts = ray_orig + ksbis[None,:] * usbis
    if los_coeffs != NULL:
        if los_coeffs[0] != NULL:
            free(los_coeffs[0])
        free(los_coeffs)
    return pts, usbis

# -- not anisotropic ------------------------------------------------------
cdef inline call_get_sample_single(double los_kmin, double los_kmax,
                                   double resol,
                                   int n_dmode, int n_imode,
                                   double[1] eff_res,
                                   double[:,::1] ray_orig,
                                   double[:,::1] ray_vdir):
    # This function doesn't compute anything new.
    # It's a utility function for LOS_calc_signal to avoid reptitions
    # It samples a LOS and recreates the points on that LOS
    # plus this is for the anisotropic version so it also compute usbis
    cdef int sz_coeff
    cdef double** los_coeffs = NULL
    cdef cnp.ndarray[double,ndim=2,mode='c'] pts

    # Initialization utility array
    los_coeffs = <double**>malloc(sizeof(double*))
    los_coeffs[0] = NULL
    # Sampling
    sz_coeff = los_get_sample_single(los_kmin, los_kmax,
                                     resol,
                                     n_dmode, n_imode,
                                     &eff_res[0],
                                     &los_coeffs[0])
    # computing points
    pts = ray_orig + np.asarray(<double[:sz_coeff]>los_coeffs[0]) * np.repeat(ray_vdir, sz_coeff, axis=1)
    if los_coeffs != NULL:
        if los_coeffs[0] != NULL:
            free(los_coeffs[0])
        free(los_coeffs)
    return pts

