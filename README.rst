ToFu
====

ToFu stands for Tomography for Fusion, it is an open-source machine-independent python library
with non-open source plugins containing all machine-dependent routines.

It is distributed under the MIT license and aims at providing the fusion community with 
a transparent and modular tool for creating / designing diagnostics and using them for 
synthtic diagnostic (direct problem) and tomography (inverse problem).

It was first created at the Max-Planck Institute for Plasma Physics (IPP) in Garching, Germany, 
by Didier Vezinet, and is now maintained / debugged / updated by him and other contributors.

A sphinx-generated documentation can be found at `the ToFu documentation page <https://didou09.github.io/tofu/index.html>`,
and the code itself is hosted on `GitHub <https://github.com/Didou09/tofu>`.


----

ToFu provides the user with a series of python classes for creating, handling and visualizing a diagnostic geometry, meshes and basis functions, 
geometry matrices, pre-treating experimental data and computing tomographic inversions.

Each one of these main tasks is accomplished by a dedicated module in the larger ToFu package.

In its current version, only the geometry and data-handling modules are released. 
The others, while operational, are not user-friendly and documented yet, they will be available in future releases.


The geometry module is sufficient for diagnostic designing and for a synthetic diagnostic approach (i.e.: computing the integrated signal from a simulated 2D or 3D emissivity).
This geometry module allows in particular:

* To handle linear and toroidal vaccum vessels
* To define apertures and detectors as planar polygons of arbitrary shapes, or to define a spherical converging lens and a circular detector in its focal plane.
* To assign an arbitrary number of apertures to each detector (and the apertures do not have to stand in parallel planes)
* To automatically compute the full Volume of Sight (VOS) in 3D of each {detector+aperture(s)} set
* To discretise the VOS for a numerical 3D integration of a simulated emissivity in order to compute the associated signal

It is in this geometrical sense that ToFu enables a synthetic diagnostic approach, it does not provide the tools for simulating the emissivity (that should be an input, provided by another code).






