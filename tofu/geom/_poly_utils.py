# This function contain functions that probably should be defined by functions
# directly in ToFu (by D. Vezinet). In the mean time we get this messy functions...
from tofu.geom._GG import CoordShift
import matplotlib.pyplot as plt
import numpy as np


def get_bbox_poly_extruded(lpoly):
    dim = lpoly.shape[0]
    assert dim == 2, "Poly should be of dim 2 (expected shape=(2,Npoints), got "+str(lpoly.shape)+")"
    # # Scatter plot on top of lines
    # plt.subplot(311)
    # plt.plot(lpoly[0,:], lpoly[1,:], 'C3', zorder=1, lw=3)
    # plt.plot(-lpoly[0,:], lpoly[1,:], 'C3', zorder=1, lw=3)
    # plt.scatter(lpoly[0,:], lpoly[1,:], s=120, zorder=2)
    # plt.scatter(-lpoly[0,:], lpoly[1,:], s=120, zorder=2)
    # plt.title('Poly in R,Z')
    # plt.tight_layout()
    # npts = lpoly.shape[1]
    # ones = np.ones_like(lpoly[0,:])*np.pi/2.
    # rzphi_poly = np.zeros((3, npts))
    # rzphi_poly[0, :] = lpoly[0,:]
    # rzphi_poly[1, :] = lpoly[1,:]
    # rzphi_poly[2, :] = ones
    # xyz_poly = CoordShift(rzphi_poly, In='(R,Z,Phi)', Out="(X,Y,Z)")
    ymax = lpoly[0,:].max()
    ymin = -ymax + 0.
    xmin = -ymax + 0.
    xmax = ymax + 0.
    zmin = lpoly[1,:].min()
    zmax = lpoly[1,:].max()
    # plt.clf()
    # plt.subplot(311)
    # plt.plot(    xyz_poly[0,:],  xyz_poly[1,:], 'C3', zorder=1, lw=3)
    # plt.plot(    xyz_poly[0,:], -xyz_poly[1,:], 'C3', zorder=1, lw=3)
    # plt.scatter( xyz_poly[0,:],  xyz_poly[1,:], s=120, zorder=2)
    # plt.scatter( xyz_poly[0,:], -xyz_poly[1,:], s=120, zorder=2)
    # plt.plot([xmin, xmin, xmax, xmax, xmin], [ymin, ymax, ymax, ymin, ymin], 'C3', zorder=1, lw=3)
    # plt.title('Poly in X,Y')
    # plt.subplot(312)
    # plt.plot(    xyz_poly[0,:], xyz_poly[2,:], 'C3', zorder=1, lw=3)
    # plt.plot(   -xyz_poly[0,:], xyz_poly[2,:], 'C3', zorder=1, lw=3)
    # plt.scatter( xyz_poly[0,:], xyz_poly[2,:], s=120, zorder=2)
    # plt.scatter(-xyz_poly[0,:], xyz_poly[2,:], s=120, zorder=2)
    # plt.plot([xmin, xmin, xmax, xmax, xmin], [zmin, zmax, zmax, zmin, zmin], 'C3', zorder=1, lw=3)
    # plt.title('Poly in X,Z')
    # plt.tight_layout()    
    # plt.subplot(313)
    # plt.plot(    xyz_poly[1,:], xyz_poly[2,:], 'C3', zorder=1, lw=3)
    # plt.plot(   -xyz_poly[1,:], xyz_poly[2,:], 'C3', zorder=1, lw=3)
    # plt.scatter( xyz_poly[1,:], xyz_poly[2,:], s=120, zorder=2)
    # plt.scatter(-xyz_poly[1,:], xyz_poly[2,:], s=120, zorder=2)
    # plt.plot([ymin, ymin, ymax, ymax, ymin], [zmin, zmax, zmax, zmin, zmin], 'C3', zorder=1, lw=3)
    # plt.title('Poly in Y,Z')
    # plt.tight_layout()    
    # plt.show(block=True)
    return xmin, ymin, zmin, xmax, ymax, zmax


def get_bbox_poly_limited(lpoly, llim):
    npts = lpoly.shape[1]
    ones = np.ones_like(lpoly[0,:])
    poly_rzmin = np.zeros((3, npts))
    poly_rzmin[0, :] = lpoly[0,:]
    poly_rzmin[1, :] = lpoly[1,:]
    poly_rzmin[2, :] = ones*llim[0]
    poly_rzmax = np.zeros((3, npts))
    poly_rzmax[0, :] = lpoly[0,:]
    poly_rzmax[1, :] = lpoly[1,:]
    poly_rzmax[2, :] = ones*llim[1]

    poly_xyz_min = CoordShift(poly_rzmin, In='(R,Z,Phi)', Out="(X,Y,Z)")
    poly_xyz_max = CoordShift(poly_rzmax, In='(R,Z,Phi)', Out="(X,Y,Z)")

    xmin = min(poly_xyz_min[0,:].min(), poly_xyz_max[0,:].min())
    ymin = min(poly_xyz_min[1,:].min(), poly_xyz_max[1,:].min())
    zmin = min(poly_xyz_min[2,:].min(), poly_xyz_max[2,:].min())
    xmax = max(poly_xyz_min[0,:].max(), poly_xyz_max[0,:].max())
    ymax = max(poly_xyz_min[1,:].max(), poly_xyz_max[1,:].max())
    zmax = max(poly_xyz_min[2,:].max(), poly_xyz_max[2,:].max())

    # axes = plt.gcf().get_axes()
    # if len(axes) > 1:
    #     axes[1].plot([xmin, xmin, xmax, xmax, xmin], [ymin, ymax, ymax, ymin, ymin], 'C3', zorder=1, lw=3, color="blue")
    #     axes[0].plot(    poly_xyz_min[0,:], poly_xyz_min[2,:], 'C3', zorder=1, lw=3)
    #     axes[0].plot([xmin, xmin, xmax, xmax, xmin], [zmin, zmax, zmax, zmin, zmin], 'C3', zorder=1, lw=3, color="blue")
    #     plt.savefig("bbox")

    return xmin, ymin, zmin, xmax, ymax, zmax
