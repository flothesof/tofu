# cython: boundscheck=False
# cython: wraparound=False
# cython: cdivision=True
#
cimport cython
cimport numpy as np
import numpy as np
from libc.math cimport sqrt as Csqrt, fabs as Cabs
from libc.math cimport cos as Ccos, acos as Cacos, sin as Csin, asin as Casin
from libc.math cimport atan2 as Catan2, pi as Cpi
from libc.math cimport NAN as Cnan
from cpython.array cimport array, clone
from cython.parallel import prange
from cython.parallel cimport parallel, threadid
from libc.stdlib cimport malloc, free, realloc

cdef double _VSMALL = 1.e-9
cdef double _SMALL = 1.e-6

# =============================================================================
# = Set of functions for Ray-tracing
# =============================================================================

def LOS_Calc_PInOut_VesStruct(double[:, ::1] ray_orig,
                              double[:, ::1] ray_vdir,
                              double[:, ::1] ves_poly,
                              double[:, ::1] ves_norm,
                              double[::1] ves_lims=None,
                              long[::1] lstruct_nlim=None,
                              list lstruct_poly=None,
                              list lstruct_lims=None,
                              list lstruct_norm=None,
                              int nstruct=0,
                              int ves_nlim=-1,
                              double rmin=-1,
                              double eps_uz=_SMALL, double eps_a=_VSMALL,
                              double eps_vz=_VSMALL, double eps_b=_VSMALL,
                              double eps_plane=_VSMALL, str ves_type='Tor',
                              bint forbid=1, bint test=1):
    """
    Computes the entry and exit point of all provided LOS for the provided
    vessel polygon (toroidal or linear) with its associated structures.
    Return the normal vector at impact and the index of the impact segment

    Params
    ======
    ray_orig : (3, num_los) double array
       LOS origin points coordinates
    ray_vdir : (3, num_los) double array
       LOS normalized direction vector
    ves_poly : (2, num_vertex) double array
       Coordinates of the vertices of the Polygon defining the 2D poloidal
       cut of the Vessel
    ves_norm : (2, num_vertex-1) double array
       Normal vectors going "inwards" of the edges of the Polygon defined
       by ves_poly
    nstruct : int
       Total number of structures (counting each limited structure as one)
    ves_nlim : int
       Number of limits of the vessel
           -1 : no limits, vessel continuous all around
            1 : vessel is limited
    ves_lims : array
       If ves_nlim==1 contains the limits min and max of vessel
    lstruct_poly : list
       List of coordinates of the vertices of all structures on poloidal plane
    lstruct_lims : list
       List of limits of all structures
    lstruct_nlim : array of ints
       List of number of limits for all structures
    lstruct_norm : list
       List of coordinates of "inwards" normal vectors of the polygon of all
       the structures
    rmin : double
       Minimal radius of vessel to take into consideration
    eps<val> : double
       Small value, acceptance of error
    vtype : string
       Type of vessel ("Tor" or "Lin")
    forbid : bool
       Should we forbid values behind vissible radius ? (see Rmin)
    test : bool
       Should we run tests ?

    Return
    ======
    coeff_inter_in : (num_los) array
       scalars level of "in" intersection of the LOS (if k=0 at origin)
    coeff_inter_out : (num_los) array
       scalars level of "out" intersection of the LOS (if k=0 at origin)
    vperp_out : (3, num_los) array
       Coordinates of the normal vector of impact of the LOS (NaN if none)
    ind_inter_out : (3, num_los)
       Index of structure impacted by LOS: ind_inter_out[:,ind_los]=(i,j,k)
       where k is the index of edge impacted on the j-th sub structure of the
       structure number i. If the LOS impacted the vessel i=j=0
    """
    cdef int npts_poly = ves_norm.shape[1]
    cdef int num_los = ray_orig.shape[1]
    cdef int nstruct_lim = 0
    cdef int ind_struct = 0
    cdef int totnvert = 0
    cdef int ii, jj, kk
    cdef int len_lim
    cdef int nvert
    cdef double Crit2_base = eps_uz * eps_uz /400.
    cdef double rmin2 = 0.
    cdef double lim_min = 0.
    cdef double lim_max = 0.
    cdef double val_rmin
    cdef str error_message
    cdef bint forbidbis, forbid0
    cdef bint bool1, bool2
    cdef double *lbounds = <double *>malloc(nstruct * 6 * sizeof(double))
    cdef double *langles = <double *>malloc(nstruct * 2 * sizeof(double))
    cdef array vperp_out = clone(array('d'), num_los * 3, True)
    cdef array coeff_inter_in  = clone(array('d'), num_los, True)
    cdef array coeff_inter_out = clone(array('d'), num_los, True)
    cdef array ind_inter_out = clone(array('i'), num_los * 3, True)
    cdef int *llimits = NULL
    cdef int *lnvert  = NULL
    cdef long *lsz_lim = NULL
    cdef double *lpolyx = NULL
    cdef double *lpolyy = NULL
    cdef double *lnormx = NULL
    cdef double *lnormy = NULL
    cdef double[:,::1] lspoly_view # memory view
    cdef double[:,::1] lsvin_view # memory view
    cdef int[1] llim_ves
    cdef double[2] lbounds_ves
    cdef double[2] lim_ves
    cdef double[6] bounds

    # == Testing inputs ========================================================
    if test:
        error_message = "ray_orig and ray_vdir must have the same shape: "\
                        + "(3,) or (3,NL)!"
        assert tuple(ray_orig.shape) == tuple(ray_vdir.shape) and \
          ray_orig.shape[0] == 3, error_message
        error_message = "ves_poly and ves_norm must have the same shape (2,NS)!"
        assert ves_poly.shape[0] == 2 and ves_norm.shape[0] == 2 and \
            npts_poly == ves_poly.shape[1]-1, error_message
        bool1 = lstruct_lims is None or len(lstruct_lims) == len(lstruct_poly)
        bool2 = lstruct_norm is None or len(lstruct_norm) == len(lstruct_poly)
        error_message = "lstruct_poly, lstruct_lims, lstruct_norm must be None"\
                        + " or lists of same len!"
        assert bool1 and bool2, error_message
        error_message = "[eps_uz,eps_vz,eps_a,eps_b] must be floats < 1.e-4!"
        assert all([ee < 1.e-4 for ee in [eps_uz, eps_a,
                                          eps_vz, eps_b,
                                          eps_plane]]), error_message
        error_message = "ves_type must be a str in ['Tor','Lin']!"
        assert ves_type.lower() in ['tor', 'lin'], error_message

    # == Treating input ========================================================
    # if there are, we get the limits for the vessel
    if ves_nlim == 0:
        llim_ves[0] = 1
        lbounds_ves[0] = 0
        lbounds_ves[1] = 0
    elif ves_nlim == 1:
        llim_ves[0] = 0
        lbounds_ves[0] = Catan2(Csin(ves_lims[0]), Ccos(ves_lims[0]))
        lbounds_ves[1] = Catan2(Csin(ves_lims[1]), Ccos(ves_lims[1]))

    # ==========================================================================
    if ves_type.lower() == 'tor':
        # rmin is necessary to avoid looking on the other side of the tokamak
        if rmin < 0.:
            val_rmin = 0.95*min(np.min(ves_poly[0, ...]),
                                np.min(np.hypot(ray_orig[0, ...],
                                                ray_orig[1, ...])))
        else:
            val_rmin = rmin
        rmin2 = val_rmin*val_rmin

        # Variable to avoid looking "behind" blind spot of tore
        if forbid:
            forbid0, forbidbis = 1, 1
        else:
            forbid0, forbidbis = 0, 0

        # Arrays to get X,Y coordinates of the Vessel's poly
        lpolyx = <double *>malloc((npts_poly + 1) * sizeof(double))
        lpolyy = <double *>malloc((npts_poly + 1) * sizeof(double))
        lnormx = <double *>malloc((npts_poly + 1) * sizeof(double))
        lnormy = <double *>malloc((npts_poly + 1) * sizeof(double))
        for ind_vert in range(npts_poly+1):
            lpolyx[ind_vert] = ves_poly[0][ind_vert]
            lpolyy[ind_vert] = ves_poly[1][ind_vert]
            lnormx[ind_vert] = ves_norm[0][ind_vert]
            lnormy[ind_vert] = ves_norm[1][ind_vert]

        # -- Computing intersection between LOS and Vessel ---------------------
        raytracing_inout_struct_tor(num_los, ray_vdir, ray_orig,
                                    coeff_inter_out, coeff_inter_in,
                                    vperp_out, lstruct_nlim, ind_inter_out,
                                    forbid0, forbidbis,
                                    val_rmin, rmin2, Crit2_base,
                                    npts_poly,  NULL, lbounds_ves,
                                    llim_ves, NULL, NULL,
                                    lpolyx, lpolyy, lnormx, lnormy,
                                    eps_uz, eps_vz, eps_a, eps_b, eps_plane,
                                    False) # structure is in

        # We can free local arrays and set them as NULL for structures
        free(lpolyx)
        free(lpolyy)
        free(lnormx)
        free(lnormy)
        lpolyx = NULL
        lpolyy = NULL
        lnormx = NULL
        lnormy = NULL

        # -- Treating the structures (if any) ----------------------------------
        if nstruct > 0:
            ind_struct = 0
            nstruct_lim = len(lstruct_poly) # num of structures (no limits)
            lnvert = <int *>malloc(nstruct_lim * sizeof(int))
            llimits = <int *>malloc(nstruct * sizeof(int))
            lsz_lim = <long *>malloc(nstruct_lim * sizeof(long))
            for ii in range(nstruct_lim):
                # For fast accessing
                lspoly_view = lstruct_poly[ii]
                lsvin_view = lstruct_norm[ii]
                len_lim = lstruct_nlim[ii]
                # We get the limits if any
                if len_lim == 0:
                    lslim = [None]
                    lstruct_nlim[ii] = lstruct_nlim[ii] + 1
                elif len_lim == 1:
                    lslim = [[lstruct_lims[ii][0, 0], lstruct_lims[ii][0, 1]]]
                else:
                    lslim = lstruct_lims[ii]
                # We get the number of vertices and limits of the struct's poly
                nvert = len(lspoly_view[0])
                if ii == 0:
                    lnvert[0] = nvert
                    lsz_lim[0] = 0
                else:
                    lnvert[ii] = nvert + lnvert[ii-1]
                    lsz_lim[ii] = lstruct_nlim[ii-1] + lsz_lim[ii-1]
                # ...and the poly itself (and normal vector)
                lpolyx = <double *>realloc(lpolyx,
                                           (totnvert+nvert) * sizeof(double))
                lpolyy = <double *>realloc(lpolyy,
                                           (totnvert+nvert) * sizeof(double))
                lnormx = <double *>realloc(lnormx,
                                           (totnvert+nvert-1-ii) * sizeof(double))
                lnormy = <double *>realloc(lnormy,
                                           (totnvert+nvert-1-ii) * sizeof(double))
                for jj in range(nvert-1):
                    lpolyx[totnvert + jj] = lspoly_view[0,jj]
                    lpolyy[totnvert + jj] = lspoly_view[1,jj]
                    lnormx[totnvert + jj - ii] = lsvin_view[0,jj]
                    lnormy[totnvert + jj - ii] = lsvin_view[1,jj]
                lpolyx[totnvert + nvert-1] = lspoly_view[0,nvert-1]
                lpolyy[totnvert + nvert-1] = lspoly_view[1,nvert-1]
                totnvert = totnvert + nvert

                # and loop over the limits (one continous structure)
                for jj in range(max(len_lim,1)):
                    # We compute the structure's bounding box:
                    if lslim[jj] is not None:
                        lim_ves[0] = lslim[jj][0]
                        lim_ves[1] = lslim[jj][1]
                        llimits[ind_struct] = 0 # False : struct is limited
                        lim_min = Catan2(Csin(lim_ves[0]), Ccos(lim_ves[0]))
                        lim_max = Catan2(Csin(lim_ves[1]), Ccos(lim_ves[1]))
                        compute_bbox_lim(nvert, lspoly_view, bounds,
                                         lim_min, lim_max)
                    else:
                        llimits[ind_struct] = 1 # True : is continous
                        compute_bbox_extr(nvert, lspoly_view, bounds)
                        lim_min = 0.
                        lim_max = 0.
                    langles[ind_struct*2] = lim_min
                    langles[ind_struct*2 + 1] = lim_max
                    for kk in range(6):
                        lbounds[ind_struct*6 + kk] = bounds[kk]
                    ind_struct = 1 + ind_struct
            # end loops over structures

            # -- Computing intersection between structures and LOS -------------
            raytracing_inout_struct_tor(num_los, ray_vdir, ray_orig,
                                        coeff_inter_out, coeff_inter_in,
                                        vperp_out, lstruct_nlim, ind_inter_out,
                                        forbid0, forbidbis,
                                        val_rmin, rmin2, Crit2_base,
                                        nstruct_lim,
                                        lbounds, langles, llimits,
                                        lnvert, lsz_lim,
                                        lpolyx, lpolyy, lnormx, lnormy,
                                        eps_uz, eps_vz, eps_a, eps_b, eps_plane,
                                        True) # the structure is "OUT"
            free(lpolyx)
            free(lpolyy)
            free(lnormx)
            free(lnormy)
            free(lnvert)
            free(lsz_lim)
            free(llimits)
            del(lspoly_view)
            del(lsvin_view)
            # end if nstruct > 0
    free(lbounds)
    free(langles)

    return np.asarray(coeff_inter_in), np.asarray(coeff_inter_out),\
           np.asarray(vperp_out), np.asarray(ind_inter_out, dtype=int)


@cython.wraparound(False)
@cython.boundscheck(False)
cdef inline void raytracing_inout_struct_tor(int num_los,
                                             double[:,::1] ray_vdir,
                                             double[:,::1] ray_orig,
                                             double[::1] coeff_inter_out,
                                             double[::1] coeff_inter_in,
                                             double[::1] vperp_out,
                                             long[::1] lstruct_nlim,
                                             int[::1] ind_inter_out,
                                             bint forbid0, bint forbidbis,
                                             double val_rmin, double rmin2,
                                             double crit2_base,
                                             int nstruct_lim,
                                             double* lbounds,
                                             double* langles, int* llim_ves,
                                             int* lnvert, long* lsz_lim,
                                             double* lstruct_polyx,
                                             double* lstruct_polyy,
                                             double* lstruct_normx,
                                             double* lstruct_normy,
                                             double eps_uz, double eps_vz,
                                             double eps_a, double eps_b,
                                             double eps_plane,
                                             bint is_out_struct) nogil:

    cdef double upscaDp=0., upar2=0., dpar2=0., crit2=0., invdpar2=0.
    cdef double dist = 0., s1x = 0., s1y = 0., s2x = 0., s2y = 0.
    cdef double lim_min=0., lim_max=0.
    cdef int totnvert=0
    cdef int ind_struct, ind_bounds
    cdef int ind_los, ii, jj, kk
    cdef int nvert
    cdef bint lim_is_none
    cdef bint found_new_kout
    cdef bint inter_bbox
    cdef double* lstruct_polyxii = NULL
    cdef double* lstruct_polyyii = NULL
    cdef double* lstruct_normxii = NULL
    cdef double* lstruct_normyii = NULL
    cdef double* last_pout = NULL
    cdef double* kpout_loc = NULL
    cdef double* kpin_loc = NULL
    cdef double* invr_ray = NULL
    cdef double* loc_org = NULL
    cdef double* loc_nrm = NULL
    cdef double* lim_ves = NULL
    cdef double* loc_vp = NULL
    cdef double* bounds = NULL
    cdef int* sign_ray = NULL
    cdef int* ind_loc = NULL

    # -- Defining parallel part ------------------------------------------------
    with nogil, parallel(num_threads=32):
        # We use local arrays for each thread so
        loc_org   = <double *> malloc(sizeof(double) * 3)
        loc_nrm   = <double *> malloc(sizeof(double) * 3)
        loc_vp    = <double *> malloc(sizeof(double) * 3)
        kpin_loc  = <double *> malloc(sizeof(double) * 1)
        kpout_loc = <double *> malloc(sizeof(double) * 1)
        ind_loc   = <int *> malloc(sizeof(int) * 1)
        if is_out_struct:
            # if the structure is "out" (solid) we need more arrays
            last_pout = <double *> malloc(sizeof(double) * 3)
            invr_ray  = <double *> malloc(sizeof(double) * 3)
            lim_ves   = <double *> malloc(sizeof(double) * 2)
            bounds    = <double *> malloc(sizeof(double) * 6)
            sign_ray  = <int *> malloc(sizeof(int) * 3)

        # -- The parallelization is done over the LOS --------------------------
        for ind_los in prange(num_los, schedule='dynamic'):
            ind_struct = 0
            loc_org[0] = ray_orig[0, ind_los]
            loc_org[1] = ray_orig[1, ind_los]
            loc_org[2] = ray_orig[2, ind_los]
            loc_nrm[0] = ray_vdir[0, ind_los]
            loc_nrm[1] = ray_vdir[1, ind_los]
            loc_nrm[2] = ray_vdir[2, ind_los]
            loc_vp[0] = 0.
            loc_vp[1] = 0.
            loc_vp[2] = 0.
            if is_out_struct:
                # if struct is "Out" type, then we compute the last
                # poit where it went out of a structure. Here
                # kpin_loc = kpout
                kpin_loc[0]  = coeff_inter_out[ind_los]
                ind_loc[0]   = ind_inter_out[2+3*ind_los]
                last_pout[0] = kpin_loc[0] * loc_nrm[0] + loc_org[0]
                last_pout[1] = kpin_loc[0] * loc_nrm[1] + loc_org[1]
                last_pout[2] = kpin_loc[0] * loc_nrm[2] + loc_org[2]
                compute_inv_and_sign(loc_nrm, sign_ray, invr_ray)
            else:
                kpin_loc[0]  = 0
                kpout_loc[0] = 0
                ind_loc[0]   = 0

            # computing sclar prods for Ray and rmin values
            upscaDp = loc_nrm[0]*loc_org[0] + loc_nrm[1]*loc_org[1]
            upar2   = loc_nrm[0]*loc_nrm[0] + loc_nrm[1]*loc_nrm[1]
            dpar2   = loc_org[0]*loc_org[0] + loc_org[1]*loc_org[1]
            invdpar2 = 1./dpar2
            crit2 = upar2*crit2_base
            # Prepare in case forbid is True
            if forbid0 and not dpar2>0:
                forbidbis = 0
            if forbidbis:
                # Compute coordinates of the 2 points where the tangents touch
                # the inner circle
                dist = Csqrt(dpar2-rmin2)
                s1x = (rmin2*loc_org[0]+val_rmin*loc_org[1]*dist)*invdpar2
                s1y = (rmin2*loc_org[1]-val_rmin*loc_org[0]*dist)*invdpar2
                s2x = (rmin2*loc_org[0]-val_rmin*loc_org[1]*dist)*invdpar2
                s2y = (rmin2*loc_org[1]+val_rmin*loc_org[0]*dist)*invdpar2
            if is_out_struct:
                for ii in range(nstruct_lim):
                    if ii == 0:
                        nvert = lnvert[0]
                        totnvert = 0
                    else:
                        totnvert = lnvert[ii-1]
                        nvert = lnvert[ii] - totnvert
                    lstruct_polyxii = <double *>malloc( (nvert)* sizeof(double))
                    lstruct_polyyii = <double *>malloc( (nvert)* sizeof(double))
                    lstruct_normxii  = <double *>malloc( (nvert-1)* sizeof(double))
                    lstruct_normyii  = <double *>malloc( (nvert-1)* sizeof(double))
                    for kk in range(nvert-1):
                        lstruct_polyxii[kk] = lstruct_polyx[totnvert + kk]
                        lstruct_polyyii[kk] = lstruct_polyy[totnvert + kk]
                        lstruct_normxii[kk] = lstruct_normx[totnvert + kk - ii]
                        lstruct_normyii[kk] = lstruct_normy[totnvert + kk - ii]
                    lstruct_polyxii[nvert-1] = lstruct_polyx[totnvert + nvert-1]
                    lstruct_polyyii[nvert-1] = lstruct_polyy[totnvert + nvert-1]
                    ind_struct = lsz_lim[ii]
                    for jj in range(lstruct_nlim[ii]):
                        bounds[0] = lbounds[(ind_struct + jj)*6]
                        bounds[1] = lbounds[(ind_struct + jj)*6 + 1]
                        bounds[2] = lbounds[(ind_struct + jj)*6 + 2]
                        bounds[3] = lbounds[(ind_struct + jj)*6 + 3]
                        bounds[4] = lbounds[(ind_struct + jj)*6 + 4]
                        bounds[5] = lbounds[(ind_struct + jj)*6 + 5]
                        lim_min = langles[(ind_struct+jj)*2]
                        lim_max = langles[(ind_struct+jj)*2 + 1]
                        lim_is_none = llim_ves[ind_struct+jj] == 1
                        # We test if it is really necessary to compute the inter:
                        # We check if the ray intersects the bounding box
                        inter_bbox = inter_ray_aabb_box(sign_ray, invr_ray, bounds, loc_org)
                        if not inter_bbox:
                            continue
                        # # We check that the bounding box is not "behind" the last POut encountered
                        inter_bbox = inter_ray_aabb_box(sign_ray, invr_ray, bounds, last_pout)
                        if inter_bbox:
                            continue
                         # We compute new values
                        found_new_kout = comp_inter_los_vpoly(&loc_org[0], &loc_nrm[0],
                                                              &lstruct_polyxii[0],
                                                              &lstruct_polyyii[0],
                                                              &lstruct_normxii[0],
                                                              &lstruct_normyii[0],
                                                              nvert-1,
                                                              lim_is_none,
                                                              lim_min, lim_max,
                                                              forbidbis,
                                                              upscaDp, upar2,
                                                              dpar2, invdpar2,
                                                              s1x, s1y, s2x, s2y,
                                                              crit2, eps_uz, eps_vz,
                                                              eps_a, eps_b,
                                                              eps_plane, False,
                                                              kpin_loc,
                                                              kpout_loc,
                                                              ind_loc,
                                                              loc_vp)
                        if found_new_kout :
                            coeff_inter_out[ind_los] = kpin_loc[0]
                            vperp_out[0+3*ind_los] = loc_vp[0]
                            vperp_out[1+3*ind_los] = loc_vp[1]
                            vperp_out[2+3*ind_los] = loc_vp[2]
                            ind_inter_out[2+3*ind_los] = ind_loc[0]
                            ind_inter_out[0+3*ind_los] = 1+ii
                            ind_inter_out[1+3*ind_los] = jj
                            last_pout[0] = coeff_inter_out[ind_los] * loc_nrm[0] + loc_org[0]
                            last_pout[1] = coeff_inter_out[ind_los] * loc_nrm[1] + loc_org[1]
                            last_pout[2] = coeff_inter_out[ind_los] * loc_nrm[2] + loc_org[2]
                    free(lstruct_polyxii)
                    free(lstruct_polyyii)
                    free(lstruct_normxii)
                    free(lstruct_normyii)
            else: # if struct is IN
                found_new_kout = comp_inter_los_vpoly(&loc_org[0], &loc_nrm[0],
                                                      &lstruct_polyx[0],
                                                      &lstruct_polyy[0],
                                                      &lstruct_normx[0],
                                                      &lstruct_normy[0],
                                                      nstruct_lim, llim_ves[0],
                                                      langles[0], langles[1],
                                                      forbidbis,
                                                      upscaDp, upar2,
                                                      dpar2, invdpar2,
                                                      s1x, s1y, s2x, s2y,
                                                      crit2, eps_uz, eps_vz, eps_a,
                                                      eps_b, eps_plane, True,
                                                      kpin_loc, kpout_loc,
                                                      ind_loc, loc_vp,)
                if found_new_kout:
                    coeff_inter_in[ind_los]         = kpin_loc[0]
                    coeff_inter_out[ind_los]        = kpout_loc[0]
                    ind_inter_out[2+3*ind_los]     = ind_loc[0]
                    ind_inter_out[0+3*ind_los]     = 0
                    ind_inter_out[1+3*ind_los]     = 0
                    vperp_out[0+3*ind_los] = loc_vp[0]
                    vperp_out[1+3*ind_los] = loc_vp[1]
                    vperp_out[2+3*ind_los] = loc_vp[2]
                else:
                    coeff_inter_in[ind_los]         = Cnan
                    coeff_inter_out[ind_los]        = Cnan
                    ind_inter_out[2+3*ind_los]     = 0
                    ind_inter_out[0+3*ind_los]     = 0
                    ind_inter_out[1+3*ind_los]     = 0
                    vperp_out[0+3*ind_los] = 0.
                    vperp_out[1+3*ind_los] = 0.
                    vperp_out[2+3*ind_los] = 0.

        free(loc_org)
        free(loc_nrm)
        free(loc_vp)
        free(kpin_loc)
        free(kpout_loc)
        free(ind_loc)
        if is_out_struct:
            free(last_pout)
            free(bounds)
            free(lim_ves)
            free(invr_ray)
            free(sign_ray)
    return

cdef inline bint comp_inter_los_vpoly(const double[3] ray_orig,
                                      const double[3] ray_vdir,
                                      const double* lpolyx,
                                      const double* lpolyy,
                                      const double* normx,
                                      const double* normy,
                                      const int nvert,
                                      const bint lim_is_none,
                                      const double lim_min, const double lim_max,
                                      const bint forbidbis,
                                      const double upscaDp, const double upar2,
                                      const double dpar2, const double invdpar2,
                                      const double s1x,   const double s1y,
                                      const double s2x, const double s2y,
                                      const double crit2, const double eps_uz,
                                      const double eps_vz, const double eps_a,
                                      const double eps_b,  const double eps_plane,
                                      const bint struct_is_ves,
                                      double[1] kpin_loc, double[1] kpout_loc,
                                      int[1] ind_loc, double[3] vperpin) nogil:
    cdef int jj
    cdef int indin=0, Done=0
    cdef int indout=0
    cdef bint inter_bbox
    cdef double kout, kin
    cdef double sca=0., sca0=0., sca1=0., sca2=0.
    cdef double q, C, delta, sqd, k, sol0, sol1, phi=0.
    cdef double v0, v1, A, B, ephiIn0, ephiIn1
    cdef double SOut1, SOut0
    cdef double SIn1, SIn0
    cdef double res_kin = kpin_loc[0]
    cdef double[3] opp_dir
    cdef double invupar2
    cdef double invuz
    cdef double cosl0, cosl1, sinl0, sinl1

    ################
    # Computing some useful values
    cosl0 = Ccos(lim_min)
    cosl1 = Ccos(lim_max)
    sinl0 = Csin(lim_min)
    sinl1 = Csin(lim_max)
    invupar2 = 1./upar2
    invuz = 1./ray_vdir[2] #TODO : why am I computing this here ?????!!!!
    # Compute all solutions
    # Set tolerance value for ray_vdir[2,ii]
    # eps_uz is the tolerated DZ across 20m (max Tokamak size)
    kout, kin, Done = 1.e12, 1.e12, 0
    # Case with horizontal semi-line
    if ray_vdir[2]*ray_vdir[2]<crit2:
        for jj in range(0,nvert):
            # Solutions exist only in the case with non-horizontal
            # segment (i.e.: cone, not plane)
            if (lpolyy[jj+1] - lpolyy[jj])**2 > eps_vz*eps_vz:
                q = (ray_orig[2]-lpolyy[jj]) / (lpolyy[jj+1]-lpolyy[jj])
                # The intersection must stand on the segment
                if q>=0 and q<1:
                    C = q*q*(lpolyx[jj+1]-lpolyx[jj])**2 + \
                        2.*q*lpolyx[jj]*(lpolyx[jj+1]-lpolyx[jj]) + \
                        lpolyx[jj]*lpolyx[jj]
                    delta = upscaDp*upscaDp - upar2*(dpar2-C)
                    if delta>0.:
                        sqd = Csqrt(delta)
                        # The intersection must be on the semi-line
                        # (i.e.: k>=0)
                        # First solution
                        if -upscaDp - sqd >=0:
                            k = (-upscaDp - sqd)*invupar2
                            sol0, sol1 = ray_orig[0] + k*ray_vdir[0], \
                                         ray_orig[1] + k*ray_vdir[1]
                            if forbidbis:
                                sca0 = (sol0-s1x)*ray_orig[0] + \
                                       (sol1-s1y)*ray_orig[1]
                                sca1 = (sol0-s1x)*s1x + (sol1-s1y)*s1y
                                sca2 = (sol0-s2x)*s2x + (sol1-s2y)*s2y
                            if not forbidbis or (forbidbis and not
                                                 (sca0<0 and sca1<0 and
                                                  sca2<0)):
                                # Get the normalized perpendicular vector
                                # at intersection
                                phi = Catan2(sol1,sol0)
                                # Check sol inside the Lim
                                if lim_is_none or (not lim_is_none and
                                                   ((lim_min<lim_max and lim_min<=phi and
                                                     phi<=lim_max)
                                                    or (lim_min>lim_max and
                                                        (phi>=lim_min or
                                                         phi<=lim_max)))):
                                    # Get the scalar product to determine
                                    # entry or exit point
                                    sca = Ccos(phi)*normx[jj]*ray_vdir[0] + \
                                          Csin(phi)*normx[jj]*ray_vdir[1] + \
                                          normy[jj]*ray_vdir[2]
                                    if sca<=0 and k<kout:
                                        kout = k
                                        Done = 1
                                        indout = jj
                                    elif sca>=0 and k<min(kin,kout):
                                        kin = k
                                        indin = jj

                        # Second solution
                        if -upscaDp + sqd >=0:
                            k = (-upscaDp + sqd)*invupar2
                            sol0, sol1 = ray_orig[0] + k*ray_vdir[0], ray_orig[1] \
                                         + k*ray_vdir[1]
                            if forbidbis:
                                sca0 = (sol0-s1x)*ray_orig[0] + \
                                       (sol1-s1y)*ray_orig[1]
                                sca1 = (sol0-s1x)*s1x + (sol1-s1y)*s1y
                                sca2 = (sol0-s2x)*s2x + (sol1-s2y)*s2y
                            if not forbidbis or (forbidbis and not
                                                 (sca0<0 and sca1<0 and
                                                  sca2<0)):
                                # Get the normalized perpendicular vector
                                # at intersection
                                phi = Catan2(sol1,sol0)
                                if lim_is_none or (not lim_is_none and
                                                   ((lim_min<lim_max and lim_min<=phi and
                                                     phi<=lim_max) or
                                                    (lim_min>lim_max and
                                                     (phi>=lim_min or phi<=lim_max))
                                                   )):
                                    # Get the scalar product to determine
                                    # entry or exit point
                                    sca = Ccos(phi)*normx[jj]*ray_vdir[0] + \
                                          Csin(phi)*normx[jj]*ray_vdir[1] + \
                                          normy[jj]*ray_vdir[2]
                                    if sca<=0 and k<kout:
                                        kout = k
                                        Done = 1
                                        indout = jj
                                    elif sca>=0 and k<min(kin,kout):
                                        kin = k
                                        indin = jj

    # More general non-horizontal semi-line case
    else:
        for jj in range(nvert):
            v0, v1 = lpolyx[jj+1]-lpolyx[jj], lpolyy[jj+1]-lpolyy[jj]
            A = v0*v0 - upar2*(v1*invuz)*(v1*invuz)
            B = lpolyx[jj]*v0 + v1*(ray_orig[2]-lpolyy[jj])*upar2*invuz*invuz - upscaDp*v1*invuz
            C = -upar2*(ray_orig[2]-lpolyy[jj])**2*invuz*invuz + 2.*upscaDp*(ray_orig[2]-lpolyy[jj])*invuz - dpar2 + lpolyx[jj]*lpolyx[jj]

            if A*A<eps_a*eps_a and B*B>eps_b*eps_b:
                q = -C/(2.*B)
                if q>=0. and q<1.:
                    k = (q*v1 - (ray_orig[2]-lpolyy[jj]))*invuz
                    if k>=0:
                        sol0, sol1 = ray_orig[0] + k*ray_vdir[0], ray_orig[1] + k*ray_vdir[1]
                        if forbidbis:
                            sca0 = (sol0-s1x)*ray_orig[0] + (sol1-s1y)*ray_orig[1]
                            sca1 = (sol0-s1x)*s1x + (sol1-s1y)*s1y
                            sca2 = (sol0-s2x)*s2x + (sol1-s2y)*s2y
                            if sca0<0 and sca1<0 and sca2<0:
                                continue
                        # Get the normalized perpendicular vector at intersection
                        phi = Catan2(sol1,sol0)
                        if lim_is_none or (not lim_is_none and ((lim_min<lim_max and lim_min<=phi and phi<=lim_max) or (lim_min>lim_max and (phi>=lim_min or phi<=lim_max)))):
                            # Get the scalar product to determine entry or exit point
                            sca = Ccos(phi)*normx[jj]*ray_vdir[0] + Csin(phi)*normx[jj]*ray_vdir[1] + normy[jj]*ray_vdir[2]
                            if sca<=0 and k<kout:
                                kout = k
                                Done = 1
                                indout = jj
                            elif sca>=0 and k<min(kin,kout):
                                kin = k
                                indin = jj

            elif A*A>=eps_a*eps_a and B*B>A*C:
                sqd = Csqrt(B*B-A*C)
                # First solution
                q = (-B + sqd)/A
                if q>=0. and q<1.:
                    k = (q*v1 - (ray_orig[2]-lpolyy[jj]))*invuz
                    if k>=0.:
                        sol0, sol1 = ray_orig[0] + k*ray_vdir[0], ray_orig[1] + k*ray_vdir[1]
                        if forbidbis:
                            sca0 = (sol0-s1x)*ray_orig[0] + (sol1-s1y)*ray_orig[1]
                            sca1 = (sol0-s1x)*s1x + (sol1-s1y)*s1y
                            sca2 = (sol0-s2x)*s2x + (sol1-s2y)*s2y
                        if not forbidbis or (forbidbis and not (sca0<0 and sca1<0 and sca2<0)):
                            # Get the normalized perpendicular vector at intersection
                            phi = Catan2(sol1,sol0)
                            if lim_is_none or (not lim_is_none and ((lim_min<lim_max and lim_min<=phi and phi<=lim_max) or (lim_min>lim_max and (phi>=lim_min or phi<=lim_max)))):
                                # Get the scalar product to determine entry or exit point
                                sca = Ccos(phi)*normx[jj]*ray_vdir[0] + Csin(phi)*normx[jj]*ray_vdir[1] + normy[jj]*ray_vdir[2]
                                if sca<=0 and k<kout:
                                    kout = k
                                    Done = 1
                                    indout = jj
                                elif sca>=0 and k<min(kin,kout):
                                    kin = k
                                    indin = jj

                # Second solution
                q = (-B - sqd)/A
                if q>=0. and q<1.:
                    k = (q*v1 - (ray_orig[2]-lpolyy[jj]))*invuz

                    if k>=0.:
                        sol0, sol1 = ray_orig[0] + k*ray_vdir[0], ray_orig[1] + k*ray_vdir[1]
                        if forbidbis:
                            sca0 = (sol0-s1x)*ray_orig[0] + (sol1-s1y)*ray_orig[1]
                            sca1 = (sol0-s1x)*s1x + (sol1-s1y)*s1y
                            sca2 = (sol0-s2x)*s2x + (sol1-s2y)*s2y
                        if not forbidbis or (forbidbis and not (sca0<0 and sca1<0 and sca2<0)):
                            # Get the normalized perpendicular vector at intersection
                            phi = Catan2(sol1,sol0)
                            if lim_is_none or (not lim_is_none and ((lim_min<lim_max and lim_min<=phi and phi<=lim_max) or (lim_min>lim_max and (phi>=lim_min or phi<=lim_max)))):
                                # Get the scalar product to determine entry or exit point
                                sca = Ccos(phi)*normx[jj]*ray_vdir[0] + Csin(phi)*normx[jj]*ray_vdir[1] + normy[jj]*ray_vdir[2]
                                if sca<=0 and k<kout:
                                    kout = k
                                    Done = 1
                                    indout = jj
                                elif sca>=0 and k<min(kin,kout):
                                    kin = k
                                    indin = jj

    if not lim_is_none:
        ephiIn0 = -sinl0
        ephiIn1 =  cosl0
        if Cabs(ray_vdir[0]*ephiIn0+ray_vdir[1]*ephiIn1)>eps_plane:
            k = -(ray_orig[0]*ephiIn0+ray_orig[1]*ephiIn1)/(ray_vdir[0]*ephiIn0+ray_vdir[1]*ephiIn1)
            if k>=0:
                # Check if in ves_poly
                sol0 = (ray_orig[0] + k*ray_vdir[0]) * cosl0 + (ray_orig[1] + k*ray_vdir[1]) * sinl0
                sol1 =  ray_orig[2] + k*ray_vdir[2]
                inter_bbox = is_point_in_path(nvert, lpolyx, lpolyy, sol0, sol1)
                if inter_bbox:
                    # Check PIn (POut not possible for limited torus)
                    sca = ray_vdir[0]*ephiIn0 + ray_vdir[1]*ephiIn1
                    if sca<=0 and k<kout:
                        kout = k
                        Done = 1
                        indout = -1
                    elif sca>=0 and k<min(kin,kout):
                        kin = k
                        indin = -1

        ephiIn0 =  sinl1
        ephiIn1 = -cosl1
        if Cabs(ray_vdir[0]*ephiIn0+ray_vdir[1]*ephiIn1)>eps_plane:
            k = -(ray_orig[0]*ephiIn0+ray_orig[1]*ephiIn1)/(ray_vdir[0]*ephiIn0+ray_vdir[1]*ephiIn1)
            if k>=0:
                sol0, sol1 = (ray_orig[0]+k*ray_vdir[0])*cosl1 + (ray_orig[1]+k*ray_vdir[1])*sinl1, ray_orig[2]+k*ray_vdir[2]
                # Check if in ves_poly
                inter_bbox = is_point_in_path(nvert, lpolyx, lpolyy, sol0, sol1)
                if inter_bbox:
                    # Check PIn (POut not possible for limited torus)
                    sca = ray_vdir[0]*ephiIn0 + ray_vdir[1]*ephiIn1
                    if sca<=0 and k<kout:
                        kout = k
                        Done = 1
                        indout = -2
                    elif sca>=0 and k<min(kin,kout):
                        kin = k
                        indin = -2

    if Done==1:
        if struct_is_ves :
            kpout_loc[0] = kout
            if indout==-1:
                vperpin[0] = -sinl0
                vperpin[1] = cosl0
                vperpin[2] = 0.
            elif indout==-2:
                vperpin[0] = sinl1
                vperpin[1] = -cosl1
                vperpin[2] = 0.
            else:
                SOut0 = ray_orig[0] + kout*ray_vdir[0]
                SOut1 = ray_orig[1] + kout*ray_vdir[1]
                phi = Catan2(SOut1,SOut0)
                vperpin[0] = Ccos(phi)*normx[indout]
                vperpin[1] = Csin(phi)*normx[indout]
                vperpin[2] = normy[indout]
            ind_loc[0] = indout
            if kin<kout:
                kpin_loc[0] = kin

        elif kin<kout and kin < res_kin:
            kpin_loc[0] = kin
            if indin==-1:
                vperpin[0] = sinl0
                vperpin[1] = -cosl0
                vperpin[2] = 0.
            elif indin==-2:
                vperpin[0] = -sinl1
                vperpin[1] = cosl1
                vperpin[2] = 0.
            else:
                SIn0 = ray_orig[0] + kin*ray_vdir[0]
                SIn1 = ray_orig[1] + kin*ray_vdir[1]
                phi = Catan2(SIn1,SIn0)
                vperpin[0] = -Ccos(phi)*normx[indin]
                vperpin[1] = -Csin(phi)*normx[indin]
                vperpin[2] = -normy[indin]
            ind_loc[0] = indin

    return res_kin != kpin_loc[0]

cdef inline void compute_inv_and_sign(const double[3] ray_vdir,
                                      int[3] sign,
                                      double[3] inv_direction) nogil:
    cdef int t0 = 1000000
    # computing sign and direction
    for  ii in range(3):
        if ray_vdir[ii]*ray_vdir[ii] < _VSMALL:
            inv_direction[ii] = t0
        else:
            inv_direction[ii] = 1./ray_vdir[ii]
        if ray_vdir[ii] < 0.:
            sign[ii] = 1
        else:
            sign[ii] = 0

    return

cdef inline bint inter_ray_aabb_box(const int[3] sign,
                                          const double[3] inv_direction,
                                          const double[6] bounds,
                                          const double[3] ds) nogil:
    """
    bounds = [3d coords of lowerleftback point of bounding box,
              3d coords of upperrightfront point of bounding box]
    ds = [3d coords of origin of ray]
    returns True if ray intersects bounding box, else False
    """
    cdef double tmin, tmax, tymin, tymax
    cdef double tzmin, tzmax
    cdef int t0 = 1000000
    cdef bint res

    # computing intersection
    tmin = (bounds[sign[0]*3] - ds[0]) * inv_direction[0];
    tmax = (bounds[(1-sign[0])*3] - ds[0]) * inv_direction[0];
    tymin = (bounds[(sign[1])*3 + 1] - ds[1]) * inv_direction[1];
    tymax = (bounds[(1-sign[1])*3+1] - ds[1]) * inv_direction[1];
    if ( (tmin > tymax) or (tymin > tmax) ):
        return 0
    if (tymin > tmin):
        tmin = tymin
    if (tymax < tmax):
        tmax = tymax
    tzmin = (bounds[(sign[2])*3+2] - ds[2]) * inv_direction[2]
    tzmax = (bounds[(1-sign[2])*3+2] - ds[2]) * inv_direction[2]
    if ( (tmin > tzmax) or (tzmin > tmax) ):
        return 0
    if (tzmin > tmin):
        tmin = tzmin
    if (tzmax < tmax):
        tmax = tzmax

    res = (tmin < t0) and (tmax > -t0)
    if (tmin < 0) :
        return 0
    return  res


cdef inline bint is_point_in_path(int nvert, double* vertx, double* verty,
                                  double testx, double testy) nogil:
    cdef int i
    cdef bint c = 0
    for i in range(nvert):
        if ( ((verty[i]>testy) != (verty[i+1]>testy)) and
            (testx < (vertx[i+1]-vertx[i]) * (testy-verty[i]) / (verty[i+1]-verty[i]) + vertx[i]) ):
            c = not c
    return c


cdef inline void compute_bbox_extr(int nvert, double[:,::1] vert,
                                   double[6] bounds) nogil:
    cdef int ii
    cdef double rmax=vert[0,0], zmin=vert[1,0], zmax=vert[1,0]
    cdef double tmp_val
    for ii in range(1, nvert):
        tmp_val = vert[0,ii]
        if tmp_val > rmax:
            rmax = tmp_val
        tmp_val = vert[1,ii]
        if tmp_val > zmax:
            zmax = tmp_val
        elif tmp_val < zmin:
            zmin = tmp_val
    bounds[0] = -rmax
    bounds[1] = -rmax
    bounds[2] = zmin
    bounds[3] = rmax
    bounds[4] = rmax
    bounds[5] = zmax
    return


cdef inline void compute_bbox_lim(int nvert, double[:,::1] vert,
                                  double[6] bounds, double lmin, double lmax) nogil:
    cdef int ii
    cdef double toto=100000.
    cdef double xmin=toto, xmax=-toto
    cdef double ymin=toto, ymax=-toto
    cdef double zmin=toto, zmax=-toto
    cdef double cos_min = Ccos(lmin)
    cdef double sin_min = Csin(lmin)
    cdef double cos_max = Ccos(lmax)
    cdef double sin_max = Csin(lmax)
    cdef double[3] temp

    for ii in range(nvert):
        temp[0] = vert[0, ii]
        temp[1] = vert[1, ii]
        coordshift_simple1d(temp, in_is_cartesian=False, CrossRef=1.,
                          cos_phi=cos_min, sin_phi=sin_min)
        if xmin > temp[0]:
            xmin = temp[0]
        if xmax < temp[0]:
            xmax = temp[0]
        if ymin > temp[1]:
            ymin = temp[1]
        if ymax < temp[1]:
            ymax = temp[1]
        if zmin > temp[2]:
            zmin = temp[2]
        if zmax < temp[2]:
            zmax = temp[2]
        temp[0] = vert[0, ii]
        temp[1] = vert[1, ii]
        coordshift_simple1d(temp, in_is_cartesian=False, CrossRef=1.,
                          cos_phi=cos_max, sin_phi=sin_max)
        if xmin > temp[0]:
            xmin = temp[0]
        if xmax < temp[0]:
            xmax = temp[0]
        if ymin > temp[1]:
            ymin = temp[1]
        if ymax < temp[1]:
            ymax = temp[1]
        if zmin > temp[2]:
            zmin = temp[2]
        if zmax < temp[2]:
            zmax = temp[2]

    bounds[0] = xmin
    bounds[1] = ymin
    bounds[2] = zmin
    bounds[3] = xmax
    bounds[4] = ymax
    bounds[5] = zmax
    return



cdef inline void coordshift_simple1d(double[3] pts, bint in_is_cartesian=True,
                                     double CrossRef=0., double cos_phi=0.,
                                     double sin_phi=0.) nogil:

    cdef double x, y, z
    cdef double r, p
    if in_is_cartesian:
        if CrossRef==0.:
            x = pts[0]
            y = pts[1]
            z = pts[2]
            pts[0] = Csqrt(x*x+y*y)
            pts[1] = z
            pts[2] = Catan2(y,x)
        else:
            x = pts[0]
            y = pts[1]
            z = pts[2]
            pts[0] = Csqrt(x*x+y*y)
            pts[1] = z
            pts[2] = CrossRef
    else:
        if CrossRef==0.:
            r = pts[0]
            z = pts[1]
            p = pts[2]
            pts[0] = r*Ccos(p)
            pts[1] = r*Csin(p)
            pts[2] = z
        else:
            r = pts[0]
            z = pts[1]
            pts[0] = r*cos_phi
            pts[1] = r*sin_phi
            pts[2] = z
    return
