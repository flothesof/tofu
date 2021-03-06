"""
ToFu: A python library for Tomography for Fusion research
=========================================================

Provides
  1. Objects to handle 3D geometry of diagnostics
  2. Built-in methods for computing key quantities, data treatment, inversions...
  3. Visualisation tools

How to use the documentation
----------------------------
Documentation is available in two forms:
  1. Docstrings provided with the code
  2. A loose standing reference guide, available from `the ToFu homepage <http://www.tofu.org>`_.


Available subpackages
---------------------
geom
    Geometry-handling, with dedicated objects, methods and functions
mesh
    Mesh and basis functions creation and handling, as well as 2D equilibrium storing
matcomp
    Computation of geometry matrix from outputs of both geom and mesh
treat
    Data-handling objects and methods for pre-treatment (visualisation, treatment...)
inv
    Inversion-regularisation algortihms, using outputs from both matcomp and data, plus visualisation methods

Available modules
-----------------
defaults
    Store most default parameters of tofu
pathfile
    Provide a class for identification of all tofu objects and methods and functions for path and file handling, object saving and loading
helper
    miscellaneous helper functions

Utilities
---------
test
    Run tofu unittests
show_config
    Show tofu build configuration
__version__
    tofu version string


Created on Wed May 18 2016

@author: didiervezinet
@author_email: didier.vezinet@gmail.com
"""


#from . import core
#from .core import *
#from . import geom
#from . import mesh
#from . import matcomp
#from . import data
#from . import inv


#__all__ = []
#__all__.extend(['__version__'])
#__all__.extend(core.__all__)
#__all__.extend(['geom', 'mesh', 'matcomp', 'data', 'inv'])

#__name__ = ""
__version__ = "1.1.1"
__author__ = "Didier Vezinet"
__author_email__="didier.vezinet@gmail.com"
#__date__ = "$Mar 05, 2014$"
#__copyright__ = ""
#__license__ = ""
#__url__ = ""
#__path__ =

