"""
This module is the geometrical part of the ToFu general package
It includes all functions and object classes necessary for tomography on Tokamaks
"""

# Built-in
import os
import warnings
from abc import ABCMeta, abstractmethod
import copy

# Common
import numpy as np
import matplotlib as mpl
import datetime as dtm
try:
    import pandas as pd
except Exception:
    lm = ['tf.geom.Config.get_description()']
    msg = "Could not import pandas, "
    msg += "the following may not work :"
    msg += "\n    - ".join(lm)
    warnings.warn(msg)


# ToFu-specific
import tofu.pathfile as tfpf
import tofu.utils as utils
try:
    import tofu.geom._def as _def
    import tofu.geom._GG as _GG
    import tofu.geom._comp as _comp
    import tofu.geom._plot as _plot
except Exception:
    from . import _def as _def
    from . import _GG as _GG
    from . import _comp as _comp
    from . import _plot as _plot

__all__ = ['PlasmaDomain', 'Ves', 'PFC', 'CoilPF', 'CoilCS', 'Config',
           'Rays','LOSCam1D','LOSCam2D']


_arrayorder = 'C'
_Clock = False
_Type = 'Tor'




"""
###############################################################################
###############################################################################
                        Ves class and functions
###############################################################################
"""



class Struct(utils.ToFuObject):
    """ A class defining a Linear or Toroidal vaccum vessel (i.e. a 2D polygon representing a cross-section and assumed to be linearly or toroidally invariant)

    A Ves object is mostly defined by a close 2D polygon, which can be understood as a poloidal cross-section in (R,Z) cylindrical coordinates if Type='Tor' (toroidal shape) or as a straight cross-section through a cylinder in (Y,Z) cartesian coordinates if Type='Lin' (linear shape).
    Attributes such as the surface, the angular volume (if Type='Tor') or the center of mass are automatically computed.
    The instance is identified thanks to an attribute Id (which is itself a tofu.ID class object) which contains informations on the specific instance (name, Type...).

    Parameters
    ----------
    Id :            str / tfpf.ID
        A name string or a pre-built tfpf.ID class to be used to identify this particular instance, if a string is provided, it is fed to tfpf.ID()
    Poly :          np.ndarray
        An array (2,N) or (N,2) defining the contour of the vacuum vessel in a cross-section, if not closed, will be closed automatically
    Type :          str
        Flag indicating whether the vessel will be a torus ('Tor') or a linear device ('Lin')
    Lim :         list / np.ndarray
        Array or list of len=2 indicating the limits of the linear device volume on the x axis
    Sino_RefPt :    None / np.ndarray
        Array specifying a reference point for computing the sinogram (i.e. impact parameter), if None automatically set to the (surfacic) center of mass of the cross-section
    Sino_NP :       int
        Number of points in [0,2*pi] to be used to plot the vessel sinogram envelop
    Clock :         bool
        Flag indicating whether the input polygon should be made clockwise (True) or counter-clockwise (False)
    arrayorder:     str
        Flag indicating whether the attributes of type=np.ndarray (e.g.: Poly) should be made C-contiguous ('C') or Fortran-contiguous ('F')
    Exp :           None / str
        Flag indicating which experiment the object corresponds to, allowed values are in [None,'AUG','MISTRAL','JET','ITER','TCV','TS','Misc']
    shot :          None / int
        Shot number from which this Ves is usable (in case of change of geometry)
    SavePath :      None / str
        If provided, forces the default saving path of the object to the provided value

    Returns
    -------
    Ves :        Ves object
        The created Ves object, with all necessary computed attributes and methods

    """

    __metaclass__ = ABCMeta


    # Fixed (class-wise) dictionary of default properties
    _ddef = {'Id':{'shot':0,
                   'include':['Mod','Cls','Exp','Diag',
                              'Name','shot','version']},
             'dgeom':{'Type':'Tor', 'Lim':[], 'arrayorder':'C'},
             'dsino':{},
             'dphys':{},
             'dmisc':{'color':'k'}}
    _dplot = {'cross':{'Elt':'P',
                       'dP':{'c':'k','lw':2},
                       'dI':{'c':'k','ls':'--','m':'x','ms':8,'mew':2},
                       'dBs':{'c':'b','ls':'--','m':'x','ms':8,'mew':2},
                       'dBv':{'c':'g','ls':'--','m':'x','ms':8,'mew':2},
                       'dVect':{'color':'r','scale':10}},
              'hor':{'Elt':'P',
                     'dP':{'c':'k','lw':2},
                     'dI':{'c':'k','ls':'--'},
                     'dBs':{'c':'b','ls':'--'},
                     'dBv':{'c':'g','ls':'--'},
                     'Nstep':50},
              '3d':{'Elt':'P',
                    'dP':{'color':(0.8,0.8,0.8,1.),
                          'rstride':1,'cstride':1,
                          'linewidth':0., 'antialiased':False},
                    'Lim':None,
                    'Nstep':50}}


    def __init_subclass__(cls, color='k', **kwdargs):
        super().__init_subclass__(**kwdargs)
        cls._ddef = copy.deepcopy(Struct._ddef)
        cls._dplot = copy.deepcopy(Struct._dplot)
        cls._set_color_ddef(color)

    @classmethod
    def _set_color_ddef(cls, color):
        cls._ddef['dmisc']['color'] = mpl.colors.to_rgba(color)

    def __init__(self, Poly=None, Type=None, Lim=None, mobile=False,
                 Id=None, Name=None, Exp=None, shot=None,
                 sino_RefPt=None, sino_nP=_def.TorNP,
                 Clock=False, arrayorder='C', fromdict=None,
                 SavePath=os.path.abspath('./'),
                 SavePath_Include=tfpf.defInclude, color=None):

        # Create a dplot at instance level
        self._dplot = copy.deepcopy(self.__class__._dplot)

        kwdargs = locals()
        del kwdargs['self']
        super().__init__(**kwdargs)

    def _reset(self):
        super()._reset()
        self._dgeom = dict.fromkeys(self._get_keys_dgeom())
        self._dsino = dict.fromkeys(self._get_keys_dsino())
        self._dphys = dict.fromkeys(self._get_keys_dphys())
        self._dmisc = dict.fromkeys(self._get_keys_dmisc())
        #self._dplot = copy.deepcopy(self.__class__._ddef['dplot'])

    @classmethod
    def _checkformat_inputs_Id(cls, Id=None, Name=None,
                               Exp=None, shot=None, Type=None,
                               include=None,
                               **kwdargs):
        if Id is not None:
            assert isinstance(Id,utils.ID)
            Name, Exp, shot, Type = Id.Name, Id.Exp, Id.shot, Id.Type
        assert type(Name) is str
        assert type(Exp) is str
        if shot is None:
            shot = cls._ddef['Id']['shot']
        assert type(shot) is int
        if Type is None:
            Type = cls._ddef['dgeom']['Type']
        assert Type in ['Tor','Lin']
        if include is None:
            include = cls._ddef['Id']['include']
        kwdargs.update({'Name':Name, 'Exp':Exp, 'shot':shot, 'Type':Type,
                        'include':include})
        return kwdargs

    ###########
    # Get largs
    ###########

    @staticmethod
    def _get_largs_dgeom(sino=True):
        largs = ['Poly','Lim','mobile','Clock','arrayorder']
        if sino:
            lsino = Struct._get_largs_dsino()
            largs += ['sino_{0}'.format(s) for s in lsino]
        return largs

    @staticmethod
    def _get_largs_dsino():
        largs = ['RefPt','nP']
        return largs

    @staticmethod
    def _get_largs_dphys():
        largs = ['lSymbols']
        return largs

    @staticmethod
    def _get_largs_dmisc():
        largs = ['color']
        return largs

    ###########
    # Get check and format inputs
    ###########

    @staticmethod
    def _checkformat_inputs_dgeom(Poly=None, Lim=None, mobile=False,
                                  Type=None, Clock=False, arrayorder=None):
        assert type(Clock) is bool
        assert type(mobile) is bool
        if arrayorder is None:
            arrayorder = Struct._ddef['dgeom']['arrayorder']
        assert arrayorder in ['C','F']
        assert Poly is not None and hasattr(Poly,'__iter__')
        Poly = np.asarray(Poly).astype(float)
        assert Poly.ndim==2 and 2 in Poly.shape
        if Poly.shape[0]!=2:
            Poly = Poly.T
        if Type is None:
            Type = Struct._ddef['dgeom']['Type']
        assert Type in ['Tor','Lin']
        if Lim is None:
            Lim = Struct._ddef['dgeom']['Lim']
        assert hasattr(Lim,'__iter__')
        Lim = np.asarray(Lim).astype(float)
        assert Lim.ndim in [1,2] and (2 in Lim.shape or 0 in Lim.shape)
        if Lim.ndim==1:
            assert Lim.size in [0,2]
            if Lim.size==2:
                Lim = Lim.reshape((1,2))
        else:
            if Lim.shape[1]!=2:
                Lim = Lim.T
        if Type=='Lin':
            assert Lim.size>0
        return Poly, Lim, Type, arrayorder

    def _checkformat_inputs_dsino(self, RefPt=None, nP=None):
        assert type(nP) is int and nP>0
        assert RefPt is None or hasattr(RefPt,'__iter__')
        if RefPt is None:
            RefPt = self._dgeom['BaryS']
        RefPt = np.asarray(RefPt,dtype=float).flatten()
        assert RefPt.size==2, "RefPt must be of size=2 !"
        return RefPt

    @staticmethod
    def _checkformat_inputs_dphys(lSymbols=None):
        if lSymbols is not None:
            assert type(lSymbols) in [list,str]
            if type(lSymbols) is list:
                assert all([type(ss) is str for ss in lSymbols])
            else:
                lSymbols = [lSymbols]
            lSymbols = np.asarray(lSymbols,dtype=str)
        return lSymbols

    @classmethod
    def _checkformat_inputs_dmisc(cls, color=None):
        if color is None:
            color = mpl.colors.to_rgba(cls._ddef['dmisc']['color'])
        assert mpl.colors.is_color_like(color)
        return tuple(mpl.colors.to_rgba(color))

    ###########
    # Get keys of dictionnaries
    ###########

    @staticmethod
    def _get_keys_dgeom():
        lk = ['Poly','Lim','nLim','Multi','nP',
              'P1Max','P1Min','P2Max','P2Min',
              'BaryP','BaryL','BaryS','BaryV',
              'Surf','VolAng','Vect','VIn','mobile',
              'circ-C','circ-r','Clock','arrayorder']
        return lk

    @staticmethod
    def _get_keys_dsino():
        lk = ['RefPt','nP','EnvTheta','EnvMinMax']
        return lk

    @staticmethod
    def _get_keys_dphys():
        lk = ['lSymbols']
        return lk

    @staticmethod
    def _get_keys_dmisc():
        lk = ['color']
        return lk

    ###########
    # _init
    ###########

    def _init(self, Poly=None, Type=_Type, Lim=None,
              Clock=_Clock, arrayorder=_arrayorder,
              sino_RefPt=None, sino_nP=_def.TorNP, **kwdargs):
        largs = self._get_largs_dgeom(sino=True)
        kwdgeom = self._extract_kwdargs(locals(), largs)
        largs = self._get_largs_dphys()
        kwdphys = self._extract_kwdargs(locals(), largs)
        largs = self._get_largs_dmisc()
        kwdmisc = self._extract_kwdargs(locals(), largs)
        self._set_dgeom(**kwdgeom)
        self.set_dphys(**kwdphys)
        self._set_dmisc(**kwdmisc)
        self._dstrip['strip'] = 0

    ###########
    # set dictionaries
    ###########

    def _set_dgeom(self, Poly=None, Lim=None, mobile=False,
                   Clock=False, arrayorder='C',
                   sino_RefPt=None, sino_nP=_def.TorNP, sino=True):
        out = self._checkformat_inputs_dgeom(Poly=Poly, Lim=Lim, mobile=mobile,
                                             Type=self.Id.Type, Clock=Clock)
        Poly, Lim, Type, arrayorder = out
        dgeom = _comp._Struct_set_Poly(Poly, Lim=Lim,
                                       arrayorder=arrayorder,
                                       Type=self.Id.Type, Clock=Clock)
        dgeom['arrayorder'] = arrayorder
        dgeom['mobile'] = mobile
        self._dgeom = dgeom
        if sino:
            self.set_dsino(sino_RefPt, nP=sino_nP)

    def set_dsino(self, RefPt=None, nP=_def.TorNP):
        RefPt = self._checkformat_inputs_dsino(RefPt=RefPt, nP=nP)
        EnvTheta, EnvMinMax = _GG.Sino_ImpactEnv(RefPt, self.Poly_closed,
                                                 NP=nP, Test=False)
        self._dsino = {'RefPt':RefPt, 'nP':nP,
                       'EnvTheta':EnvTheta, 'EnvMinMax':EnvMinMax}

    def set_dphys(self, lSymbols=None):
        lSymbols = self._checkformat_inputs_dphys(lSymbols)
        self._dphys['lSymbols'] = lSymbols

    def _set_color(self, color=None):
        color = self._checkformat_inputs_dmisc(color=color)
        self._dmisc['color'] = color
        self._dplot['cross']['dP']['c'] = color
        self._dplot['hor']['dP']['c'] = color
        self._dplot['3d']['dP']['color'] = color

    def _set_dmisc(self, color=None):
        self._set_color(color)

    ###########
    # strip dictionaries
    ###########

    def _strip_dgeom(self, lkeep=['Poly','Lim','mobile','Clock','arrayorder']):
        utils.ToFuObject._strip_dict(self._dgeom, lkeep=lkeep)

    def _strip_dsino(self, lkeep=['RefPt','nP']):
        utils.ToFuObject._strip_dict(self._dsino, lkeep=lkeep)

    def _strip_dphys(self, lkeep=['lSymbols']):
        utils.ToFuObject._strip_dict(self._dphys, lkeep=lkeep)

    def _strip_dmisc(self, lkeep=['color']):
        utils.ToFuObject._strip_dict(self._dmisc, lkeep=lkeep)

    ###########
    # rebuild dictionaries
    ###########

    def _rebuild_dgeom(self, lkeep=['Poly','Lim','mobile','Clock','arrayorder']):
        reset = utils.ToFuObject._test_Rebuild(self._dgeom, lkeep=lkeep)
        if reset:
            utils.ToFuObject._check_Fields4Rebuild(self._dgeom,
                                                   lkeep=lkeep, dname='dgeom')
            self._set_dgeom(self.Poly, Lim=self.Lim,
                            Clock=self.dgeom['Clock'],
                            arrayorder=self.dgeom['arrayorder'],
                            sino=False)

    def _rebuild_dsino(self, lkeep=['RefPt','nP']):
        reset = utils.ToFuObject._test_Rebuild(self._dsino, lkeep=lkeep)
        if reset:
            utils.ToFuObject._check_Fields4Rebuild(self._dsino,
                                                   lkeep=lkeep, dname='dsino')
            self.set_dsino(RefPt=self.dsino['RefPt'], nP=self.dsino['nP'])

    def _rebuild_dphys(self, lkeep=['lSymbols']):
        reset = utils.ToFuObject._test_Rebuild(self._dphys, lkeep=lkeep)
        if reset:
            utils.ToFuObject._check_Fields4Rebuild(self._dphys,
                                                   lkeep=lkeep, dname='dphys')
            self.set_dphys(lSymbols=self.dphys['lSymbols'])

    def _rebuild_dmisc(self, lkeep=['color']):
        reset = utils.ToFuObject._test_Rebuild(self._dmisc, lkeep=lkeep)
        if reset:
            utils.ToFuObject._check_Fields4Rebuild(self._dmisc,
                                                   lkeep=lkeep, dname='dmisc')
            self._set_dmisc(color=self.dmisc['color'])

    ###########
    # _strip and get/from dict
    ###########

    @classmethod
    def _strip_init(cls):
        cls._dstrip['allowed'] = [0,1,2]
        nMax = max(cls._dstrip['allowed'])
        doc = """
                 1: Remove dsino expendables
                 2: Remove also dgeom, dphys and dmisc expendables"""
        doc = utils.ToFuObjectBase.strip.__doc__.format(doc,nMax)
        cls.strip.__doc__ = doc

    def strip(self, strip=0):
        super().strip(strip=strip)

    def _strip(self, strip=0):
        if strip==0:
            self._rebuild_dgeom()
            self._rebuild_dsino()
            self._rebuild_dphys()
            self._rebuild_dmisc()
        elif strip==1:
            self._strip_dsino()
            self._rebuild_dgeom()
            self._rebuild_dphys()
            self._rebuild_dmisc()
        else:
            self._strip_dsino()
            self._strip_dgeom()
            self._strip_dphys()
            self._strip_dmisc()

    def _to_dict(self):
        dout = {'dgeom':{'dict':self.dgeom, 'lexcept':None},
                'dsino':{'dict':self.dsino, 'lexcept':None},
                'dphys':{'dict':self.dphys, 'lexcept':None},
                'dmisc':{'dict':self.dmisc, 'lexcept':None}}
        return dout

    def _from_dict(self, fd):
        self._dgeom.update(**fd['dgeom'])
        self._dsino.update(**fd['dsino'])
        self._dphys.update(**fd['dphys'])
        self._dmisc.update(**fd['dmisc'])


    ###########
    # Properties
    ###########

    @property
    def Type(self):
        """Return the type of structure """
        return self._Id.Type
    @property
    def dgeom(self):
        return self._dgeom
    @property
    def Poly(self):
        """Return the polygon defining the structure cross-section"""
        return self._dgeom['Poly']
    @property
    def Poly_closed(self):
        """ Returned the closed polygon """
        return np.hstack((self._dgeom['Poly'],self._dgeom['Poly'][:,0:1]))
    @property
    def Lim(self):
        return self._dgeom['Lim']
    @property
    def nLim(self):
        return self._dgeom['nLim']
    @property
    def dsino(self):
        return self._dsino
    @property
    def dphys(self):
        return self._dphys
    @property
    def dmisc(self):
        return self._dmisc


    ###########
    # public methods
    ###########

    def set_color(self, col):
        self._set_color(col)

    def get_color(self):
        return self._dmisc['color']

    @abstractmethod
    def isMobile(self):
        return self._dgeom['mobile']

    def isInside(self, pts, In='(X,Y,Z)'):
        """ Return an array of booleans indicating whether each point lies
        inside the Struct volume

        Tests for each point whether it lies inside the Struct object.
        The points coordinates can be provided in 2D or 3D
        You must specify which coordinate system is used with 'In' kwdarg.
        An array of boolean flags is returned.

        Parameters
        ----------
        pts :   np.ndarray
            (2,N) or (3,N) array, coordinates of the points to be tested
        In :    str
            Flag indicating the coordinate system in which pts are provided
            e.g.: '(X,Y,Z)' or '(R,Z)'

        Returns
        -------
        ind :   np.ndarray
            (N,) array of booleans, True if a point is inside the volume

        """
        ind = _GG._Ves_isInside(pts, self.Poly, Lim=self.Lim,
                                nLim=self._dgeom['nLim'],
                                VType=self.Id.Type,
                                In=In, Test=True)
        return ind


    def get_InsideConvexPoly(self, RelOff=_def.TorRelOff, ZLim='Def',
                             Spline=True, Splprms=_def.TorSplprms,
                             NP=_def.TorInsideNP, Plot=False, Test=True):
        """ Return a polygon that is a smaller and smoothed approximation of Ves.Poly, useful for excluding the divertor region in a Tokamak

        For some uses, it can be practical to approximate the polygon defining the Ves object (which can be non-convex, like with a divertor), by a simpler, sligthly smaller and convex polygon.
        This method provides a fast solution for computing such a proxy.

        Parameters
        ----------
        RelOff :    float
            Fraction by which an homothetic polygon should be reduced (1.-RelOff)*(Poly-BaryS)
        ZLim :      None / str / tuple
            Flag indicating what limits shall be put to the height of the polygon (used for excluding divertor)
        Spline :    bool
            Flag indiating whether the reduced and truncated polygon shall be smoothed by 2D b-spline curves
        Splprms :   list
            List of 3 parameters to be used for the smoothing [weights,smoothness,b-spline order], fed to scipy.interpolate.splprep()
        NP :        int
            Number of points to be used to define the smoothed polygon
        Plot :      bool
            Flag indicating whether the result shall be plotted for visual inspection
        Test :      bool
            Flag indicating whether the inputs should be tested for conformity

        Returns
        -------
        Poly :      np.ndarray
            (2,N) polygon resulting from homothetic transform, truncating and optional smoothing

        """
        return _comp._Ves_get_InsideConvexPoly(self.Poly, self.dgeom['P2Min'],
                                               self.dgeom['P2Max'],
                                               self.dgeom['BaryS'],
                                               RelOff=RelOff, ZLim=ZLim,
                                               Spline=Spline, Splprms=Splprms,
                                               NP=NP, Plot=Plot, Test=Test)

    def get_sampleEdge(self, res, DS=None, resMode='abs', offsetIn=0.):
        """ Sample the polygon edges, with resolution res

        Sample each segment of the 2D polygon
        Sampling can be limited to a subdomain defined by DS
        """
        pts, dlr, ind = _comp._Ves_get_sampleEdge(self.Poly, res, DS=DS,
                                                  dLMode=resMode, DIn=offsetIn,
                                                  VIn=self.dgeom['VIn'],
                                                  margin=1.e-9)
        return pts, dlr, ind

    def get_sampleCross(self, res, DS=None, resMode='abs', ind=None):
        """ Sample, with resolution res, the 2D cross-section

        The sampling domain can be limited by DS or ind
        """
        args = [self.Poly, self.dgeom['P1Min'][0], self.dgeom['P1Max'][0],
                self.dgeom['P2Min'][1], self.dgeom['P2Max'][1], res]
        kwdargs = dict(DS=DS, dSMode=resMode, ind=ind, margin=1.e-9)
        pts, dS, ind, reseff = _comp._Ves_get_sampleCross(*args, **kwdargs)
        return pts, dS, ind, reseff

    def get_sampleS(self, res, DS=None, resMode='abs',
                    ind=None, offsetIn=0., Out='(X,Y,Z)', Ind=None):
        """ Sample, with resolution res, the surface defined by DS or ind

        An optionnal offset perpendicular to the surface can be used
        (offsetIn>0 => inwards)

        Parameters
        ----------
        res     :   float / list of 2 floats
            Desired resolution of the surfacic sample
                float   : same resolution for all directions of the sample
                list    : [dl,dXPhi] where:
                    dl      : res. along polygon contours (cross-section)
                    dXPhi   : res. along axis (toroidal/linear direction)
        DS      :   None / list of 3 lists of 2 floats
            Limits of the domain in which the sample should be computed
                None : whole surface of the object
                list : [D1,D2,D3], where Di is a len()=2 list
                       (increasing floats, setting limits along coordinate i)
                    [DR,DZ,DPhi]: in toroidal geometry (self.Id.Type=='Tor')
                    [DX,DY,DZ]  : in linear geometry (self.Id.Type=='Lin')
        resMode  :   str
            Flag, specifies if res is absolute or relative to element sizes
                'abs'   :   res is an absolute distance
                'rel'   :   if res=0.1, each polygon segment is divided in 10,
                            as is the toroidal/linear length
        ind     :   None / np.ndarray of int
            If provided, DS is ignored and the sample points corresponding to
            the provided indices are returned
            Example (assuming obj is a Ves object)
                > # We create a 5x5 cm2 sample of the whole surface
                > pts, dS, ind, reseff = obj.get_sample(0.05)
                > # Perform operations, save only the points indices (save space)
                > ...
                > # Retrieve the points from their indices (requires same res)
                > pts2, dS2, ind2, reseff2 = obj.get_sample(0.05, ind=ind)
                > np.allclose(pts,pts2)
                True
        offsetIn:   float
            Offset distance from the actual surface of the object
            Inwards if positive
            Useful to avoid numerical errors
        Out     :   str
            Flag indicating the coordinate system of returned points
            e.g. : '(X,Y,Z)' or '(R,Z,Phi)'
        Ind     :   None / iterable of ints
            Array of indices of the entities to be considered
            (only when multiple entities, i.e.: self.nLim>1)

        Returns
        -------
        pts     :   np.ndarray / list of np.ndarrays
            Sample points coordinates, as a (3,N) array.
            A list is returned if the object has multiple entities
        dS      :   np.ndarray / list of np.ndarrays
            The surface (in m^2) associated to each point
        ind     :   np.ndarray / list of np.ndarrays
            The index of each point
        reseff  :   np.ndarray / list of np.ndarrays
            Effective resolution in both directions after sample computation
        """
        if Ind is not None:
            assert self.dgeom['Multi']
        kwdargs = dict(DS=DS, dSMode=resMode, ind=ind, DIn=offsetIn,
                       VIn=self.dgeom['VIn'], VType=self.Id.Type,
                       VLim=self.Lim, nVLim=self.nLim,
                       Out=Out, margin=1.e-9,
                       Multi=self.dgeom['Multi'], Ind=Ind)
        args = [self.Poly, self.dgeom['P1Min'][0], self.dgeom['P1Max'][0],
                self.dgeom['P2Min'][1], self.dgeom['P2Max'][1], res]
        pts, dS, ind, reseff = _comp._Ves_get_sampleS(*args, **kwdargs)
        return pts, dS, ind, reseff

    def get_sampleV(self, res, DV=None, resMode='abs', ind=None, Out='(X,Y,Z)'):
        """ Sample, with resolution res, the volume defined by DV or ind """

        args = [self.Poly, self.dgeom['P1Min'][0], self.dgeom['P1Max'][0],
                self.dgeom['P2Min'][1], self.dgeom['P2Max'][1], res]
        kwdargs = dict(DV=DV, dVMode=resMode, ind=ind, VType=self.Id.Type,
                      VLim=self.Lim, Out=Out, margin=1.e-9)
        pts, dV, ind, reseff = _comp._Ves_get_sampleV(*args, **kwdargs)
        return pts, dV, ind, reseff


    def plot(self, lax=None, proj='all', Elt='PIBsBvV',
             dP=None, dI=_def.TorId, dBs=_def.TorBsd, dBv=_def.TorBvd,
             dVect=_def.TorVind, dIHor=_def.TorITord, dBsHor=_def.TorBsTord,
             dBvHor=_def.TorBvTord, Lim=None, Nstep=_def.TorNTheta,
             dLeg=_def.TorLegd, draw=True, fs=None, wintit='tofu', Test=True):
        """ Plot the polygon defining the vessel, in chosen projection

        Generic method for plotting the Ves object
        The projections to be plotted, the elements to plot can be specified
        Dictionaries of properties for each elements can also be specified
        If an ax is not provided a default one is created.

        Parameters
        ----------
        Lax :       list or plt.Axes
            The axes to be used for plotting
            Provide a list of 2 axes if proj='All'
            If None a new figure with axes is created
        proj :      str
            Flag specifying the kind of projection
                - 'Cross' : cross-section projection
                - 'Hor' : horizontal projection
                - 'All' : both
                - '3d' : a 3d matplotlib plot
        Elt  :      str
            Flag specifying which elements to plot
            Each capital letter corresponds to an element:
                * 'P': polygon
                * 'I': point used as a reference for impact parameters
                * 'Bs': (surfacic) center of mass
                * 'Bv': (volumic) center of mass for Tor type
                * 'V': vector pointing inward perpendicular to each segment
        dP :        dict / None
            Dict of properties for plotting the polygon
            Fed to plt.Axes.plot() or plt.plot_surface() if proj='3d'
        dI :        dict / None
            Dict of properties for plotting point 'I' in Cross-section projection
        dIHor :     dict / None
            Dict of properties for plotting point 'I' in horizontal projection
        dBs :       dict / None
            Dict of properties for plotting point 'Bs' in Cross-section projection
        dBsHor :    dict / None
            Dict of properties for plotting point 'Bs' in horizontal projection
        dBv :       dict / None
            Dict of properties for plotting point 'Bv' in Cross-section projection
        dBvHor :    dict / None
            Dict of properties for plotting point 'Bv' in horizontal projection
        dVect :     dict / None
            Dict of properties for plotting point 'V' in cross-section projection
        dLeg :      dict / None
            Dict of properties for plotting the legend, fed to plt.legend()
            The legend is not plotted if None
        Lim :       list or tuple
            Array of a lower and upper limit of angle (rad.) or length for
            plotting the '3d' proj
        Nstep :     int
            Number of points for sampling in ignorable coordinate (toroidal angle or length)
        draw :      bool
            Flag indicating whether the fig.canvas.draw() shall be called automatically
        a4 :        bool
            Flag indicating whether the figure should be plotted in a4 dimensions for printing
        Test :      bool
            Flag indicating whether the inputs should be tested for conformity

        Returns
        -------
        La          list / plt.Axes
            Handles of the axes used for plotting (list if several axes where used)

        """
        kwdargs = locals()
        lout = ['self']
        for k in lout:
            del kwdargs[k]
        return _plot.Struct_plot(self, **kwdargs)


    def plot_sino(self, ax=None, Ang=_def.LOSImpAng,
                  AngUnit=_def.LOSImpAngUnit, Sketch=True, dP=None,
                  dLeg=_def.TorLegd, draw=True, fs=None, wintit='tofu',
                  Test=True):
        """ Plot the sinogram of the vessel polygon, by computing its envelopp in a cross-section, can also plot a 3D version of it

        The envelop of the polygon is computed using self.Sino_RefPt as a reference point in projection space,
        and plotted using the provided dictionary of properties.
        Optionaly a small sketch can be included illustrating how the angle
        and the impact parameters are defined (if the axes is not provided).

        Parameters
        ----------
        proj :      str
            Flag indicating whether to plot a classic sinogram ('Cross') from the vessel cross-section (assuming 2D)
            or an extended 3D version '3d' of it with additional angle
        ax   :      None or plt.Axes
            The axes on which the plot should be done, if None a new figure and axes is created
        Ang  :      str
            Flag indicating which angle to use for the impact parameter, the angle of the line itself (xi) or of its impact parameter (theta)
        AngUnit :   str
            Flag for the angle units to be displayed, 'rad' for radians or 'deg' for degrees
        Sketch :    bool
            Flag indicating whether a small skecth showing the definitions of angles 'theta' and 'xi' should be included or not
        Pdict :     dict
            Dictionary of properties used for plotting the polygon envelopp,
            fed to plt.plot() if proj='Cross' and to plt.plot_surface() if proj='3d'
        LegDict :   None or dict
            Dictionary of properties used for plotting the legend, fed to plt.legend(), the legend is not plotted if None
        draw :      bool
            Flag indicating whether the fig.canvas.draw() shall be called automatically
        a4 :        bool
            Flag indicating whether the figure should be plotted in a4 dimensions for printing
        Test :      bool
            Flag indicating whether the inputs shall be tested for conformity

        Returns
        -------
        ax :        plt.Axes
            The axes used to plot

        """
        if Test:
            msg = "The impact parameters must be set ! (self.set_dsino())"
            assert not self.dsino['RefPt'] is None, msg

        # Only plot cross sino, from version 1.4.0
        dP = _def.TorPFilld if dP is None else dP
        ax = _plot.Plot_Impact_PolProjPoly(self, ax=ax, Ang=Ang,
                                           AngUnit=AngUnit, Sketch=Sketch,
                                           Leg=self.Id.NameLTX, dP=dP,
                                           dLeg=dLeg, draw=False,
                                           fs=fs, wintit=wintit, Test=Test)
        # else:
        # Pdict = _def.TorP3DFilld if Pdict is None else Pdict
        # ax = _plot.Plot_Impact_3DPoly(self, ax=ax, Ang=Ang, AngUnit=AngUnit,
                                      # Pdict=Pdict, dLeg=LegDict, draw=False,
                                      # fs=fs, wintit=wintit, Test=Test)
        if draw:
            ax.figure.canvas.draw()
        return ax



"""
###############################################################################
###############################################################################
                      Effective Struct subclasses
###############################################################################
"""

class Ves(Struct, color='k'):

    def __init__(self, Poly=None, Type=None, Lim=None,
                 Id=None, Name=None, Exp=None, shot=None,
                 sino_RefPt=None, sino_nP=_def.TorNP,
                 Clock=False, arrayorder='C', fromdict=None,
                 SavePath=os.path.abspath('./'),
                 SavePath_Include=tfpf.defInclude, color=None):
        kwdargs = locals()
        del kwdargs['self'], kwdargs['__class__']
        super().__init__(mobile=False, **kwdargs)

    @classmethod
    def _set_color_ddef(cls, color):
        super()._set_color_ddef(color)
        color = mpl.colors.to_rgba(color)
        cls._dplot['cross']['dP']['c'] = color
        cls._dplot['hor']['dP']['c'] = color
        cls._dplot['3d']['dP']['color'] = color


    @staticmethod
    def _checkformat_inputs_dgeom(Poly=None, Lim=None, mobile=False,
                                  Type=None, Clock=False, arrayorder=None):
        kwdargs = locals()
        out = Struct._checkformat_inputs_dgeom(**kwdargs)
        Poly, Lim, Type, arrayorder = out
        msg = "Ves instances cannot be mobile !"
        assert mobile is False, msg
        msg = "There cannot be Lim if Type='Tor' !"
        if Type=='Tor':
            assert Lim.size==0, msg
        return out

    ######
    # Overloading of asbtract methods

    def isMobile(self):
        assert self._dgeom['mobile'] is False
        return False

class PlasmaDomain(Ves, color='k'): pass


class PFC(Struct, color=(0.8,0.8,0.8,0.8)):

    @classmethod
    def _set_color_ddef(cls, color):
        super()._set_color_ddef(color)
        color = mpl.colors.to_rgba(color)
        cls._dplot['cross']['dP'] = {'fc':color,'ec':'k','linewidth':1}
        cls._dplot['hor']['dP'] = {'fc':color,'ec':'none'}
        cls._dplot['3d']['dP']['color'] = color

    def _set_color(self, color=None):
        color = self._checkformat_inputs_dmisc(color=color)
        self._dmisc['color'] = color
        self._dplot['cross']['dP']['fc'] = color
        self._dplot['hor']['dP']['fc'] = color
        self._dplot['3d']['dP']['color'] = color

    def move(self):
        """ To be overriden at object-level after instance creation

        To do so:
            1/ create the instance:
                >> S = tfg.Struct('test', poly, Exp='Test')
            2/ Define a moving function f taking the instance as first argument
                >> def f(self, Delta=1.):
                       Polynew = self.Poly
                       Polynew[0,:] = Polynew[0,:] + Delta
                       self._set_geom(Polynew, Lim=self.Lim)
            3/ Bound your custom function to the self.move() method
               using types.MethodType() found in the types module
                >> import types
                >> S.move = types.MethodType(f, S)

            See the following page for info and details on method-patching:
            https://tryolabs.com/blog/2013/07/05/run-time-method-patching-python/
        """
        print(self.move.__doc__)


    def get_sampleV(self, *args, **kwdargs):
        msg = "class cannot use get_sampleV() method !"
        raise Exception(msg)

    ######
    # Overloading of asbtract methods

    def isMobile(self):
        super(PFC, self).isMobile()


class CoilPF(Struct, color='r'):

    def __init__(self, Poly=None, Type=None, Lim=None,
                 Id=None, Name=None, Exp=None, shot=None,
                 sino_RefPt=None, sino_nP=_def.TorNP,
                 Clock=False, arrayorder='C', fromdict=None,
                 SavePath=os.path.abspath('./'),
                 SavePath_Include=tfpf.defInclude, color=None):
        kwdargs = locals()
        del kwdargs['self'], kwdargs['__class__']
        super().__init__(mobile=False, **kwdargs)

    @classmethod
    def _set_color_ddef(cls, color):
        super()._set_color_ddef(color)
        color = mpl.colors.to_rgba(color)
        cls._dplot['cross']['dP'] = {'fc':color,'ec':'k','linewidth':1}
        cls._dplot['hor']['dP'] = {'fc':color,'ec':'none'}
        cls._dplot['3d']['dP']['color'] = color

    def _set_color(self, color=None):
        color = self._checkformat_inputs_dmisc(color=color)
        self._dmisc['color'] = color
        self._dplot['cross']['dP']['fc'] = color
        self._dplot['hor']['dP']['fc'] = color
        self._dplot['3d']['dP']['color'] = color

    def __init__(self, nturns=None, superconducting=None, active=None,
                 **kwdargs):
        super().__init__(**kwdargs)

    def _reset(self):
        super()._reset()
        self._dmag = dict.fromkeys(self._get_keys_dmag())
        self._dmag['nI'] = 0

    ###########
    # Get largs
    ###########

    @staticmethod
    def _get_largs_dmag():
        largs = ['nturns','superconducting','active']
        return largs

    ###########
    # Get check and format inputs
    ###########

    @staticmethod
    def _checkformat_inputs_dmag(nturns=None, superconducting=None, active=None):
        C0 = nturns is None
        C1 = type(nturns) in [int,float,np.int64,np.float64] and nturns>0
        assert C0 or C1
        if C1:
            nturns = int(nturns)
        C0 = superconducting is None
        C1 = type(superconducting) is bool
        assert C0 or C1
        C0 = active is None
        C1 = type(active) is bool
        assert C0 or C1
        return nturns

    ###########
    # Get keys of dictionnaries
    ###########

    @staticmethod
    def _get_keys_dmag():
        lk = ['nturns','superconducting','active','I','nI']
        return lk

    ###########
    # _init
    ###########

    def _init(self, nturns=None, superconducting=None, active=None, **kwdargs):
        super()._init(**kwdargs)
        self.set_dmag(nturns=nturns, superconducting=superconducting,
                      active=active)


    ###########
    # set dictionaries
    ###########

    def set_dmag(self, superconducting=None, nturns=None, active=None):
        nturns = self._checkformat_inputs_dmag(nturns=nturns, active=active,
                                                superconducting=superconducting)
        self._dmag.update({'superconducting':superconducting,
                           'nturns':nturns, 'active':active})

    ###########
    # strip dictionaries
    ###########

    def _strip_dmag(self, lkeep=['nturns','superconducting','active']):
        utils.ToFuObject._strip_dict(self._dmag, lkeep=lkeep)
        self._dmag['nI'] = 0

    ###########
    # rebuild dictionaries
    ###########

    def _rebuild_dmag(self, lkeep=['nturns','superconducting','active']):
        self.set_dmag(nturns=self.nturns, active=self._dmag['active'],
                      superconducting=self._dmag['superconducting'])

    ###########
    # _strip and get/from dict
    ###########

    @classmethod
    def _strip_init(cls):
        cls._dstrip['allowed'] = [0,1,2]
        nMax = max(cls._dstrip['allowed'])
        doc = """
                 1: Remove dsino and dmag expendables
                 2: Remove also dgeom, dphys and dmisc expendables"""
        doc = utils.ToFuObjectBase.strip.__doc__.format(doc,nMax)
        cls.strip.__doc__ = doc

    def strip(self, strip=0):
        super().strip(strip=strip)

    def _strip(self, strip=0):
        out = super()._strip(strip=strip)
        if strip==0:
            self._rebuild_dmag()
        else:
            self._strip_dmag()
        return out

    def _to_dict(self):
        dout = super()._to_dict()
        dout.update({'dmag':{'dict':self.dmag, 'lexcept':None}})
        return dout

    def _from_dict(self, fd):
        super()._from_dict(fd)
        self._dmag.update(**fd['dmag'])


    ###########
    # Properties
    ###########

    @property
    def dmag(self):
        return self._dmag

    @property
    def nturns(self):
        return self._dmag['nturns']

    @property
    def I(self):
        return self._dmag['I']

    ###########
    # public methods
    ###########

    def set_I(self, I=None):
        """ Set the current circulating on the coil (A) """
        C0 = I is None
        C1 = type(I) in [int,float,np.int64,np.float64]
        C2 = type(I) in [list,tuple,np.ndarray]
        msg = "Arg I must be None, a float or an 1D np.ndarray !"
        assert C0 or C1 or C2, msg
        if C1:
            I = np.array([I],dtype=float)
        elif C2:
            I = np.asarray(I,dtype=float).ravel()
        self._dmag['I'] = I
        if C0:
            self._dmag['nI'] = 0
        else:
            self._dmag['nI'] = I.size


class CoilCS(CoilPF, color='r'): pass



"""
###############################################################################
###############################################################################
                        Overall Config object
###############################################################################
"""

class Config(utils.ToFuObject):


    # Special dict subclass with attr-like value access


    # Fixed (class-wise) dictionary of default properties
    _ddef = {'Id':{'shot':0, 'Type':'Tor',
                   'include':['Mod','Cls','Exp',
                              'Name','shot','version']},
             'dstruct':{'order':['Ves','PFC','CoilPF','CoilCS'],
                        'dextraprop':{'visible':True}}}

    def __init__(self, lStruct=None, dextraprop=None,
                 Id=None, Name=None, Exp=None, shot=None, Type=None,
                 SavePath=os.path.abspath('./'),
                 SavePath_Include=tfpf.defInclude,
                 fromdict=None):

        kwdargs = locals()
        del kwdargs['self']
        super().__init__(**kwdargs)

    def _reset(self):
        super()._reset()
        self._dstruct = dict.fromkeys(self._get_keys_dstruct())
        self._dextraprop = dict.fromkeys(self._get_keys_dextraprop())
        self._dsino = dict.fromkeys(self._get_keys_dsino())

    @classmethod
    def _checkformat_inputs_Id(cls, Id=None, Name=None, Type=None,
                               shot=None, include=None, **kwdargs):
        if Id is not None:
            assert isinstance(Id,utils.ID)
            Name, shot = Id.Name, Id.shot
        assert type(Name) is str
        if Type is None:
            Type = cls._ddef['Id']['Type']
        assert Type in ['Tor','Lin']
        if shot is None:
            shot = cls._ddef['Id']['shot']
        assert type(shot) is int
        if include is None:
            include = cls._ddef['Id']['include']
            kwdargs.update({'Name':Name, 'Type':Type,
                            'include':include, 'shot':shot})
        return kwdargs

    ###########
    # Get largs
    ###########

    @staticmethod
    def _get_largs_dstruct():
        largs = ['lStruct']
        return largs
    @staticmethod
    def _get_largs_dextraprop():
        largs = ['dextraprop']
        return largs
    @staticmethod
    def _get_largs_dsino():
        largs = ['RefPt','nP']
        return largs

    ###########
    # Get check and format inputs
    ###########

    @staticmethod
    def _checkformat_inputs_dstruct(lStruct=None):
        msg = "Arg lStruct must be"
        msg += " a tofu.geom.Struct subclass or a list of such !"
        msg += "\nValid subclasses include:"
        lsub = ['Ves','PFC','CoilPF','CoilCS']
        for ss in lsub:
            msg += "\n    - tf.geom.{0}".format(ss)
        assert type(lStruct) is not None, msg
        C0 = isinstance(lStruct,list) or isinstance(lStruct,tuple)
        C1 = issubclass(lStruct.__class__,Struct)
        assert C0 or C1, msg
        if C0:
            Ci = [issubclass(ss.__class__,Struct) for ss in lStruct]
            assert all(Ci), msg
            lStruct = list(lStruct)
        else:
            lStruct = [lStruct]
        C = all([ss.Id.Exp==lStruct[0].Id.Exp for ss in lStruct])
        msg = "All Struct objects must have the same Exp !"
        msg += "\nCurrently we have:"
        ls = ["{0}: {1}".format(ss.Id.SaveName, ss.Id.Exp)for ss in lStruct]
        msg += "\n    - " + "\n    - ".join(ls)
        assert C, msg

        return lStruct

    def _checkformat_inputs_extraval(self, extraval, key='',
                                             multi=True, size=None):
        lsimple = [bool,float,int,np.int64,np.float64]
        C0 = type(extraval) in lsimple
        C1 = isinstance(extraval,np.ndarray)
        C2 = isinstance(extraval,dict)
        if multi:
            assert C0 or C1 or C2
        else:
            assert C0
        if multi and C1:
            size = self._dstruct['nStruct'] if size is None else size
            C = extraval.shape==((self._dstruct['nStruct'],))
            if not C:
                msg = "The value for %s has wrong shape!"%key
                msg += "\n    Expected: ({0},)".format(self._dstruct['nStruct'])
                msg += "\n    Got:      {0}".format(str(extraval.shape))
                raise Exception(msg)
            C = np.ndarray
        elif multi and C2:
            msg0 = "If an extra attribute is provided as a dict,"
            msg0 += "It should have the same structure as self.dStruct !"
            lk = sorted(self._dstruct['lCls'])
            c = lk==sorted(extraval.keys())
            if not c:
                msg = "\nThe value for %s has wrong keys !"%key
                msg += "\n    expected : "+str(lk)
                msg += "\n    received : "+str(sorted(extraval.keys()))
                raise Exception(msg0+msg)
            c = [isinstance(extraval[k],dict) for k in lk]
            if not all(c):
                msg = "\nThe value for %s shall be a dict of nested dict !"%key
                msg += "\n    "
                msg += "\n    ".join(['{0} : {1}'.format(lk[ii],c[ii])
                                     for ii in range(0,len(lk))])
                raise Exception(msg0+msg)
            c = [sorted(v.keys())==sorted(self.dstruct['dStruct'][k].keys())
                 for k, v in extraval.items()]
            if not all(c):
                msg = "\nThe value for %s shall has wrong nested dict !"%key
                msg += "\n    "
                raise Exception(msg0+msg)
            for k in lk:
                for kk,v in extraval[k].items():
                    msg = "\n%s[%s][%s] should be in %s"%(key,k,kk,str(lsimple))
                    assert v in lsimple, msg
            C = dict
        elif C0:
            C = int
        return C

    def _checkformat_inputs_dextraprop(self, dextraprop=None):
        if dextraprop is None:
            dextraprop = self._ddef['dstruct']['dextraprop']
        if dextraprop is None:
            dextraprop = {}
        assert isinstance(dextraprop,dict)
        dC = {}
        for k in dextraprop.keys():
            dC[k] = self._checkformat_inputs_extraval(dextraprop[k], key=k)
        return dextraprop, dC

    def _checkformat_inputs_dsino(self, RefPt=None, nP=None):
        assert type(nP) is int and nP>0
        assert hasattr(RefPt,'__iter__')
        RefPt = np.asarray(RefPt,dtype=float).flatten()
        assert RefPt.size==2, "RefPt must be of size=2 !"
        return RefPt

    ###########
    # Get keys of dictionnaries
    ###########

    @staticmethod
    def _get_keys_dstruct():
        lk = ['dStruct',
              'nStruct','lorder','lCls']
        return lk

    @staticmethod
    def _get_keys_dextraprop():
        lk = ['lprop']
        return lk

    @staticmethod
    def _get_keys_dsino():
        lk = ['RefPt','nP']
        return lk

    ###########
    # _init
    ###########

    def _init(self, lStruct=None, dextraprop=None, **kwdargs):
        largs = self._get_largs_dstruct()
        kwdstruct = self._extract_kwdargs(locals(), largs)
        largs = self._get_largs_dextraprop()
        kwdextraprop = self._extract_kwdargs(locals(), largs)
        self._set_dstruct(**kwdstruct)
        self._set_dextraprop(**kwdextraprop)
        self._dynamicattr()
        self._dstrip['strip'] = 0

    ###########
    # set dictionaries
    ###########


    def _set_dstruct(self, lStruct=None):
        lStruct = self._checkformat_inputs_dstruct(lStruct=lStruct)
        # Make sure to kill the link to the mutable being provided
        nStruct = len(lStruct)
        # Get extra info
        lCls = list(set([ss.Id.Cls for ss in lStruct]))
        lorder = [ss.Id.SaveName_Conv(Cls=ss.Id.Cls,
                                      Name=ss.Id.Name,
                                      include=['Cls','Name']) for ss in lStruct]

        msg = "There is an ambiguity in the names :"
        msg += "\n    - " + "\n    - ".join(lorder)
        msg += "\n => Please clarify (choose unique Cls/Names)"
        assert len(list(set(lorder)))==nStruct, msg

        self._dstruct = {'dStruct':dict([(k,{}) for k in lCls])}

        for k in lCls:
            lk = [ss for ss in lStruct if ss.Id.Cls==k]
            for ss in lk:
                self._dstruct['dStruct'][k].update({ss.Id.Name:ss.copy()})

        self._dstruct.update({'nStruct':nStruct,
                              'lorder':lorder, 'lCls':lCls})


    def _set_dextraprop(self, dextraprop=None):
        dextraprop, dC = self._checkformat_inputs_dextraprop(dextraprop)
        self._dextraprop['lprop'] = sorted(list(dextraprop.keys()))

        # Init dict
        lCls = self._dstruct['lCls']
        for pp in dextraprop.keys():
            dp = 'd'+pp
            dd = dict.fromkeys(lCls,{})
            for k in lCls:
                dd[k] = dict.fromkeys(self._dstruct['dStruct'][k].keys())
            self._dextraprop.update({dp:dd})

        # Populate
        for pp in dextraprop.keys():
            self._set_extraprop(pp, dextraprop[pp])


    def add_extraprop(self, key, val):
        assert type(key) is str
        dx = {}
        for k in self._dextraprop['lprop']:
            dx[k] = eval('self.get_%s()'%k)
        dx[key] = val

        # Decide what is best here---------------------
        for k in dx.keys():
            self._set_extraprop(k, dx[k])
        self._dynamicattr()

    def _set_extraprop(self, pp, val, k0=None, k1=None):
        assert not (k0 is None and k1 is not None)
        dp = 'd'+pp
        if k0 is None and k1 is None:
            C = self._checkformat_inputs_extraval(val, pp)
            if C is int:
                for k0 in self._dstruct['dStruct'].keys():
                    for k1 in self._dextraprop[dp][k0].keys():
                        self._dextraprop[dp][k0][k1] = val
            elif C is np.ndarray:
                ii = 0
                for k in self._dstruct['lorder']:
                    k0, k1 = k.split('_')
                    self._dextraprop[dp][k0][k1] = val[ii]
                    ii += 1
            else:
                for k0 in self._dstruct['dStruct'].keys():
                    for k1 in self._dextraprop[dp][k0].keys():
                        self._dextraprop[dp][k0][k1] = val[k0][k1]
        elif k1 is None:
            size = len(self._dextraprop[dp][k0].keys())
            C = self._checkformat_inputs_extraval(val, pp, size=size)
            assert C in [int,np.ndarray]
            if C is int:
                for k1 in self._dextraprop[dp][k0].keys():
                    self._dextraprop[dp][k0][k1] = val
            elif C is np.ndarray:
                ii = 0
                for k in self._dstruct['lorder']:
                    kk, k1 = k.split('_')
                    if k0==kk:
                        self._dextraprop[dp][k0][k1] = val[ii]
                        ii += 1
        else:
            C = self._checkformat_inputs_extraval(val, pp, multi=False)
            assert C is int
            self._dextraprop[dp][k0][k1] = val

    def _get_extraprop(self, pp, k0=None, k1=None):
        assert not (k0 is None and k1 is not None)
        dp = 'd'+pp
        if k0 is None and k1 is None:
            val = np.zeros((self._dstruct['nStruct'],),dtype=bool)
            ii = 0
            for k in self._dstruct['lorder']:
                k0, k1 = k.split('_')
                val[ii] = self._dextraprop[dp][k0][k1]
                ii += 1
        elif k1 is None:
            val = np.zeros((len(self._dstruct['dStruct'][k0].keys()),),dtype=bool)
            ii = 0
            for k in self._dstruct['lorder']:
                k, k1 = k.split('_')
                if k0==k:
                    val[ii] = self._dextraprop[dp][k0][k1]
                    ii += 1
        else:
            val = self._dextraprop[dp][k0][k1]
        return val

    def _set_color(self, k0, val):
        for k1 in self._dstruct['dStruct'][k0].keys():
            self._dstruct['dStruct'][k0][k1].set_color(val)

    def _dynamicattr(self):
        # get (key, val) pairs

        # Purge
        for k in self._ddef['dstruct']['order']:
            if hasattr(self,k):
                exec("del self.{0}".format(k))

        # Set
        for k in self._dstruct['dStruct'].keys():
            # Find a way to programmatically add dynamic properties to the
            # instances , like visible
            # In the meantime use a simple functions
            lset = ['set_%s'%pp for pp in self._dextraprop['lprop']]
            lget = ['get_%s'%pp for pp in self._dextraprop['lprop']]
            if not type(list(self._dstruct['dStruct'][k].values())[0]) is str:
                for kk in self._dstruct['dStruct'][k].keys():
                    for pp in self._dextraprop['lprop']:
                        setattr(self._dstruct['dStruct'][k][kk],
                                'set_%s'%pp,
                                lambda val, pk=pp, k0=k, k1=kk: self._set_extraprop(pk, val, k0, k1))
                        setattr(self._dstruct['dStruct'][k][kk],
                                'get_%s'%pp,
                                lambda pk=pp, k0=k, k1=kk: self._get_extraprop(pk, k0, k1))
                dd = utils.dictattr(self._dstruct['dStruct'][k],
                                    extra=['set_color']+lset+lget)
                for pp in self._dextraprop['lprop']:
                    setattr(dd,
                            'set_%s'%pp,
                            lambda val, pk=pp, k0=k: self._set_extraprop(pk, val, k0))
                    setattr(dd,
                            'get_%s'%pp,
                            lambda pk=pp, k0=k: self._get_extraprop(pk, k0))
                setattr(dd,
                        'set_color',
                        lambda col, k0=k: self._set_color(k0, col))
                setattr(self, k, dd)
        for pp in self._dextraprop['lprop']:
            setattr(self, 'set_%s'%pp,
                    lambda val, pk=pp: self._set_extraprop(pk,val))
            setattr(self, 'get_%s'%pp,
                    lambda pk=pp: self._get_extraprop(pk))

    def set_dsino(self, RefPt, nP=_def.TorNP):
        RefPt = self._checkformat_inputs_dsino(RefPt=RefPt, nP=nP)
        for k in self._dstruct['dStruct'].keys():
            for kk in self._dstruct['dStruct'][k].keys():
                self._dstruct['dStruct'][k][kk].set_dsino(RefPt=RefPt, nP=nP)
        self._dsino = {'RefPt':RefPt, 'nP':nP}


    ###########
    # strip dictionaries
    ###########

    def _strip_dstruct(self, strip=0, force=False):
        if self._dstrip['strip']==strip:
            return

        if self._dstrip['strip']>strip:

            # Reload if necessary
            if self._dstrip['strip']==3:
                for k in self._dstruct['dStruct'].keys():
                    for kk in self._dstruct['dStruct'][k].keys():
                        pfe = self._dstruct['dStruct'][k][kk]
                        try:
                            self._dstruct['dStruct'][k][kk] = utils.load(pfe)
                        except Exception as err:
                            msg = str(err)
                            msg += "\n    type(pfe) = {0}".format(str(type(pfe)))
                            msg += "\n    self._dstrip['strip'] = {0}".format(self._dstrip['strip'])
                            msg += "\n    strip = {0}".format(strip)
                            raise Exception(msg)

            for k in self._dstruct['dStruct'].keys():
                for kk in self._dstruct['dStruct'][k].keys():
                    self._dstruct['dStruct'][k][kk].strip(strip=strip)

            lkeep = self._get_keys_dstruct()
            reset = utils.ToFuObject._test_Rebuild(self._dstruct, lkeep=lkeep)
            if reset:
                utils.ToFuObject._check_Fields4Rebuild(self._dstruct,
                                                       lkeep=lkeep,
                                                       dname='dstruct')
            self._set_dstruct(lStruct=self.lStruct)

        else:
            if strip in [1,2]:
                for k in self._dstruct['lCls']:
                    for kk, v  in self._dstruct['dStruct'][k].items():
                        self._dstruct['dStruct'][k][kk].strip(strip=strip)
                lkeep = self._get_keys_dstruct()

            elif strip==3:
                for k in self._dstruct['lCls']:
                    for kk, v  in self._dstruct['dStruct'][k].items():
                        path, name = v.Id.SavePath, v.Id.SaveName
                        # --- Check !
                        lf = os.listdir(path)
                        lf = [ff for ff in lf
                              if all([s in ff for s in [name,'.npz']])]
                        exist = len(lf)==1
                        # ----------
                        pathfile = os.path.join(path, name)+'.npz'
                        if not exist:
                            msg = """BEWARE:
                                You are about to delete the Struct objects
                                Only the path/name to saved objects will be kept

                                But it appears that the following object has no
                                saved file where specified (obj.Id.SavePath)
                                Thus it won't be possible to retrieve it
                                (unless available in the current console:"""
                            msg += "\n    - {0}".format(pathfile)
                            if force:
                                warning.warn(msg)
                            else:
                                raise Exception(msg)
                        self._dstruct['dStruct'][k][kk] = pathfile
                self._dynamicattr()
                lkeep = self._get_keys_dstruct()
            utils.ToFuObject._strip_dict(self._dstruct, lkeep=lkeep)

    def _strip_dextraprop(self, strip=0):
        lkeep = list(self._dextraprop.keys())
        utils.ToFuObject._strip_dict(self._dextraprop, lkeep=lkeep)

    def _strip_dsino(self, lkeep=['RefPt','nP']):
        for k in self._dstruct['dStruct'].keys():
            for kk in self._dstruct['dStruct'][k].keys():
                self._dstruct['dStruct'][k][kk]._strip_dsino(lkeep=lkeep)

    ###########
    # _strip and get/from dict
    ###########

    @classmethod
    def _strip_init(cls):
        cls._dstrip['allowed'] = [0,1,2,3]
        nMax = max(cls._dstrip['allowed'])
        doc = """
                 1: apply strip(1) to objects in self.lStruct
                 2: apply strip(2) to objects in self.lStruct
                 3: replace objects in self.lStruct by their SavePath+SaveName"""
        doc = utils.ToFuObjectBase.strip.__doc__.format(doc,nMax)
        cls.strip.__doc__ = doc

    def strip(self, strip=0, force=False):
        super().strip(strip=strip, force=force)

    def _strip(self, strip=0, force=False):
        self._strip_dstruct(strip=strip, force=force)
        #self._strip_dextraprop()
        #self._strip_dsino()

    def _to_dict(self):
        dout = {'dstruct':{'dict':self.dstruct, 'lexcept':None},
                'dextraprop':{'dict':self._dextraprop, 'lexcept':None},
                'dsino':{'dict':self.dsino, 'lexcept':None}}
        return dout

    def _from_dict(self, fd):
        self._dstruct.update(**fd['dstruct'])
        self._dextraprop.update(**fd['dextraprop'])
        self._dsino.update(**fd['dsino'])
        self._dynamicattr()


    ###########
    # Properties
    ###########

    @property
    def dstruct(self):
       return self._dstruct
    @property
    def lStruct(self):
        """ Return the list of Struct that was used for creation

        As tofu objects of SavePath+SaveNames (according to strip status)
        """
        lStruct = []
        for k in self._dstruct['lorder']:
            k0, k1 = k.split('_')
            lStruct.append(self._dstruct['dStruct'][k0][k1])
        return lStruct

    @property
    def dextraprop(self):
       return self._dextraprop
    @property
    def dsino(self):
       return self._dsino

    ###########
    # public methods
    ###########

    def get_color(self):
        """ Return the array of rgba colors (same order as lStruct) """
        col = np.full((self._dstruct['nStruct'],4), np.nan)
        ii = 0
        for k in self._dstruct['lorder']:
            k0, k1 = k.split('_')
            col[ii,:] = self._dstruct['dStruct'][k0][k1].get_color()
            ii += 1
        return col

    def get_summary(self, verb=False, max_columns=100, width=1000):
        """ Summary description of the object content as a pandas DataFrame """
        # Make sure the data is accessible
        msg = "The data is not accessible because self.strip(2) was used !"
        assert self._dstrip['strip']<2, msg

        # Build the list
        d = self._dstruct['dStruct']
        data = []
        for k in self._ddef['dstruct']['order']:
            if k not in d.keys():
                continue
            for kk in d[k].keys():
                lu = [k,
                      self._dstruct['dStruct'][k][kk]._Id._dall['Name'],
                      self._dstruct['dStruct'][k][kk]._Id._dall['SaveName'],
                      self._dstruct['dStruct'][k][kk]._dgeom['nP'],
                      self._dstruct['dStruct'][k][kk]._dgeom['nLim'],
                      self._dstruct['dStruct'][k][kk]._dgeom['mobile'],
                      self._dstruct['dStruct'][k][kk]._dmisc['color']]
                for pp in self._dextraprop['lprop']:
                    lu.append(self._dextraprop['d'+pp][k][kk])
                data.append(lu)

        # Build the pandas DataFrame
        col = ['class', 'Name', 'SaveName', 'nP', 'nLim',
               'mobile', 'color'] + self._dextraprop['lprop']
        df = pd.DataFrame(data, columns=col)
        pd.set_option('display.max_columns',max_columns)
        pd.set_option('display.width',width)

        if verb:
            print(df)
        return df

    def isInside(self, pts, In='(X,Y,Z)', log='any'):
        """ Return a 2D array of bool

        Equivalent to applying isInside to each Struct
        Check self.lStruct[0].isInside? for details

        Arg log determines how Struct with multiple Limits are treated
            - 'all' : True only if pts belong to all elements
            - 'any' : True if pts belong to any element
        """
        msg = "Arg pts must be a 1D or 2D np.ndarray !"
        assert isinstance(pts,np.ndarray) and pts.ndim in [1,2], msg
        msg = "Arg log must be in ['any','all']"
        assert log in ['any','all'], msg
        if pts.ndim==1:
            msg = "Arg pts must contain the coordinates of a point !"
            assert pts.size in [2,3], msg
            pts = pts.reshape((pts.size,1)).astype(float)
        else:
            msg = "Arg pts must contain the coordinates of points !"
            assert pts.shape[0] in [2,3], pts
        nP = pts.shape[1]

        ind = np.zeros((self._dstruct['nStruct'],nP), dtype=bool)
        lStruct = self.lStruct
        for ii in range(0,self._dstruct['nStruct']):
            indi = _GG._Ves_isInside(pts,
                                     lStruct[ii].Poly,
                                     Lim=lStruct[ii].Lim,
                                     nLim=lStruct[ii].nLim,
                                     VType=lStruct[ii].Id.Type,
                                     In=In, Test=True)
            if lStruct[ii].nLim>1:
                if log=='any':
                    indi = np.any(indi,axis=0)
                else:
                    indi = np.all(indi,axis=0)
            ind[ii,:] = indi
        return ind

    def plot(self, lax=None, proj='all', Elt='P', dLeg=_def.TorLegd,
             draw=True, fs=None, wintit=None, tit=None, Test=True):
        assert tit is None or isinstance(tit,str)
        vis = self.get_visible()
        lStruct, lS = self.lStruct, []
        for ii in range(0,self._dstruct['nStruct']):
            if vis[ii]:
                lS.append(lStruct[ii])

        if tit is None:
            tit = self.Id.Name
        lax = _plot.Struct_plot(lS, lax=lax, proj=proj, Elt=Elt,
                                dLeg=dLeg, draw=draw, fs=fs,
                                wintit=wintit, tit=tit, Test=Test)
        return lax


    def plot_sino(self, ax=None, dP=None,
                  Ang=_def.LOSImpAng, AngUnit=_def.LOSImpAngUnit,
                  Sketch=True, dLeg=_def.TorLegd,
                  draw=True, fs=None, wintit=None, tit=None, Test=True):

        msg = "Set the sino params before plotting !"
        msg += "\n    => run self.set_sino(...)"
        assert self.dsino['RefPt'] is not None, msg
        msg = "The sinogram can only be plotted for a Ves object !"
        assert 'Ves' in self.dstruct['dStruct'], msg
        assert tit is None or isinstance(tit,str)
        # Check uniformity of sinogram parameters
        for ss in self.lStruct:
            msg = "{0} {1} has different".format(ss.Id.Cls, ss.Id.Name)
            msgf = "\n    => run self.set_sino(...)"
            msg0 = msg+" sino RefPt"+msgf
            assert np.allclose(self.dsino['RefPt'],ss.dsino['RefPt']), msg0
            msg1 = msg+" sino nP"+msgf
            assert self.dsino['nP']==ss.dsino['nP'], msg1

        # Check there is only one Ves object and it is visible
        msg = "There should be only one Ves object !"
        assert len(self.dstruct['dStruct']['Ves'].keys())==1, msg
        if 'visible' in self._dextraprop['lprop']:
            msg = "The Ves object is not visible !"
            assert list(self.dextraprop['dvisible']['Ves'].values())[0], msg

        if tit is None:
            tit = self.Id.Name

        Ves = list(self.dstruct['dStruct']['Ves'].values())[0]
        ax = _plot.Plot_Impact_PolProjPoly([Ves],
                                           ax=ax, Ang=Ang,
                                           AngUnit=AngUnit, Sketch=Sketch,
                                           dP=dP, dLeg=dLeg, draw=draw,
                                           fs=fs, tit=tit, wintit=wintit, Test=Test)
        return ax



"""
###############################################################################
###############################################################################
                        Rays-derived classes and functions
###############################################################################
"""


class Rays(utils.ToFuObject):
    """ Parent class of rays (ray-tracing), LOS, LOSCam1D and LOSCam2D

    Focused on optimizing the computation time for many rays.

    Each ray is defined by a starting point (D) and a unit vector(u).
    If a vessel (Ves) and structural elements (LStruct) are provided,
    the intersection points are automatically computed.

    Methods for plootting, computing synthetic signal are provided.

    Parameters
    ----------
    Id :            str  / :class:`~tofu.pathfile.ID`
        A name string or a :class:`~tofu.pathfile.ID` to identify this instance,
        if a string is provided, it is fed to :class:`~tofu.pathfile.ID`
    Du :            iterable
        Iterable of len=2, containing 2 np.ndarrays represnting, for N rays:
            - Ds: a (3,N) array of the (X,Y,Z) coordinates of starting points
            - us: a (3,N) array of the (X,Y,Z) coordinates of the unit vectors
    Ves :           None / :class:`~tofu.geom.Ves`
        A :class:`~tofu.geom.Ves` instance to be associated to the rays
    LStruct:        None / :class:`~tofu.geom.Struct` / list
        A :class:`~tofu.geom.Struct` instance or list of such, for obstructions
    Sino_RefPt :    None / np.ndarray
        Iterable of len=2 with the coordinates of the sinogram reference point
            - (R,Z) coordinates if the vessel is of Type 'Tor'
            - (Y,Z) coordinates if the vessel is of Type 'Lin'
    Type :          None
        (not used in the current version)
    Exp        :    None / str
        Experiment to which the LOS belongs:
            - if both Exp and Ves are provided: Exp==Ves.Id.Exp
            - if Ves is provided but not Exp: Ves.Id.Exp is used
    Diag       :    None / str
        Diagnostic to which the LOS belongs
    shot       :    None / int
        Shot number from which this LOS is valid
    SavePath :      None / str
        If provided, default saving path of the object

    """

    # Fixed (class-wise) dictionary of default properties
    _ddef = {'Id':{'shot':0,
                   'include':['Mod','Cls','Exp','Diag',
                              'Name','shot','version']},
             'dgeom':{'Type':'Tor', 'Lim':[], 'arrayorder':'C'},
             'dsino':{},
             'dmisc':{'color':'k'}}
    _dplot = {'cross':{'Elt':'P',
                       'dP':{'c':'k','lw':2},
                       'dI':{'c':'k','ls':'--','m':'x','ms':8,'mew':2},
                       'dBs':{'c':'b','ls':'--','m':'x','ms':8,'mew':2},
                       'dBv':{'c':'g','ls':'--','m':'x','ms':8,'mew':2},
                       'dVect':{'color':'r','scale':10}},
              'hor':{'Elt':'P',
                     'dP':{'c':'k','lw':2},
                     'dI':{'c':'k','ls':'--'},
                     'dBs':{'c':'b','ls':'--'},
                     'dBv':{'c':'g','ls':'--'},
                     'Nstep':50},
              '3d':{'Elt':'P',
                    'dP':{'color':(0.8,0.8,0.8,1.),
                          'rstride':1,'cstride':1,
                          'linewidth':0., 'antialiased':False},
                    'Lim':None,
                    'Nstep':50}}

    def __init_subclass__(cls, color='k', **kwdargs):
        super().__init_subclass__(**kwdargs)
        cls._ddef = copy.deepcopy(Rays._ddef)
        cls._dplot = copy.deepcopy(Rays._dplot)
        cls._set_color_ddef(color)

    @classmethod
    def _set_color_ddef(cls, color):
        cls._ddef['dmisc']['color'] = mpl.colors.to_rgba(color)

    def __init__(self, dgeom=None, Etendues=None, Surfaces=None,
                 config=None, dchans=None,
                 Id=None, Name=None, Exp=None, shot=None, Diag=None,
                 sino_RefPt=None, fromdict=None,
                 SavePath=os.path.abspath('./'), color=None, plotdebug=True):

        # Create a dplot at instance level
        self._dplot = copy.deepcopy(self.__class__._dplot)

        kwdargs = locals()
        del kwdargs['self']
        super().__init__(**kwdargs)

    def _reset(self):
        super()._reset()
        self._dgeom = dict.fromkeys(self._get_keys_dgeom())
        self._dconfig = dict.fromkeys(self._get_keys_dconfig())
        self._dsino = dict.fromkeys(self._get_keys_dsino())
        self._dchans = dict.fromkeys(self._get_keys_dchans())
        self._dmisc = dict.fromkeys(self._get_keys_dmisc())
        #self._dplot = copy.deepcopy(self.__class__._ddef['dplot'])

    @classmethod
    def _checkformat_inputs_Id(cls, Id=None, Name=None,
                               Exp=None, shot=None, Diag=None,
                               include=None,
                               **kwdargs):
        if Id is not None:
            assert isinstance(Id,utils.ID)
            Name, Exp, shot, Diag = Id.Name, Id.Exp, Id.shot, Id.Diag
        assert type(Name) is str
        assert type(Exp) is str
        assert type(Diag) is str
        if shot is None:
            shot = cls._ddef['Id']['shot']
        assert type(shot) is int
        if include is None:
            include = cls._ddef['Id']['include']
        kwdargs.update({'Name':Name, 'Exp':Exp, 'shot':shot, 'Diag':Diag,
                        'include':include})
        return kwdargs

    ###########
    # Get largs
    ###########

    @staticmethod
    def _get_largs_dgeom(sino=True):
        largs = ['dgeom']
        if sino:
            lsino = Rays._get_largs_dsino()
            largs += ['sino_{0}'.format(s) for s in lsino]
        return largs

    @staticmethod
    def _get_largs_dconfig():
        largs = ['config']
        return largs

    @staticmethod
    def _get_largs_dsino():
        largs = ['RefPt']
        return largs

    @staticmethod
    def _get_largs_dchans():
        largs = ['dchans']
        return largs

    @staticmethod
    def _get_largs_dmisc():
        largs = ['color']
        return largs

    ###########
    # Get check and format inputs
    ###########


    def _checkformat_inputs_dES(self, val=None):
        if val is not None:
            C0 = type(val) in [int,float,np.int64,np.float64]
            C1 = hasattr(val,'__iter__')
            assert C0 or C1
            if C1:
                val = np.asarray(val,dtype=float).ravel()
                assert val.size==self._dgeom['nRays']
        return val

    @staticmethod
    def _checkformat_inputs_dgeom(dgeom=None):
        assert dgeom is not None
        C0 = (isinstance(dgeom,dict)
              and all([k in dgeom.keys() for k in ['D','u']]))
        C1 = (isinstance(dgeom,dict)
              and all([k in dgeom.keys() for k in ['D','pinhole']]))
        C2 = isinstance(dgeom,tuple) and len(dgeom)==2
        msg = "Arg dgeom must be a dict or a tuple of len=2"
        assert C0 or C1 or C2, msg

        def _checkformat_Du(arr, name):
            arr = np.asarray(arr,dtype=float)
            msg = "Arg %s must be an iterable convertible into either:"%name
            msg += "\n    - a 1D np.ndarray of size=3"
            msg += "\n    - a 2D np.ndarray of shape (3,N)"
            assert arr.ndim in [1,2], msg
            if arr.ndim==1:
                assert arr.size==3, msg
                arr = arr.reshape((3,1))
            else:
                assert 3 in arr.shape, msg
                if arr.shape[0]!=3:
                    arr = arr.T
            arr = np.ascontiguousarray(arr)
            return arr

        D = dgeom[0] if C2 else dgeom['D']
        D = _checkformat_Du(D, 'D')
        if C1:
            pinhole = _checkformat_Du(dgeom['pinhole'], 'pinhole')
            nD, npinhole = D.shape[1], pinhole.shape[1]
            assert npinhole==1
            pinhole = pinhole.ravel()
            nRays = nD
            dgeom = {'D':D, 'pinhole':pinhole, 'nRays':nRays}

        else:
            u = dgeom[1] if C2 else dgeom['u']
            u = _checkformat_Du(u, 'u')
            # Normalize u
            u = u/np.sqrt(np.sum(u**2,axis=0))[np.newaxis,:]
            nD, nu = D.shape[1], u.shape[1]
            C0 = nD==1 and nu>1
            C1 = nD>1 and nu==1
            C2 = nD==nu
            msg = "The number of rays is ambiguous from D and u shapes !"
            assert C0 or C1 or C2, msg
            nRays = max(nD,nu)
            dgeom = {'D':D, 'u':u, 'nRays':nRays}
        return dgeom

    @staticmethod
    def _checkformat_inputs_dconfig(config=None):
        C0 = isinstance(config,Config)
        msg = "Arg config must be a Config instance !"
        msg += "\n    expected : {0}".format(str(Config))
        msg += "\n    obtained : {0}".format(str(config.__class__))
        assert C0, msg
        msg = "Arg config must have a PlasmaDomain !"
        assert 'PlasmaDomain' in config.dstruct['dStruct'].keys(), msg
        if not 'compute' in config._dextraprop['lprop']:
            config = config.copy()
            config.add_extraprop('compute',True)
        return config

    def _checkformat_inputs_dsino(self, RefPt=None):
        assert RefPt is None or hasattr(RefPt,'__iter__')
        if RefPt is not None:
            RefPt = np.asarray(RefPt,dtype=float).flatten()
            assert RefPt.size==2, "RefPt must be of size=2 !"
        return RefPt

    def _checkformat_inputs_dchans(self, dchans=None):
        assert dchans is None or isinstance(dchans,dict)
        if dchans is None:
            dchans = {}
        for k in dchans.keys():
            arr = np.asarray(dchans[k]).ravel()
            assert arr.size==self_dgeom['nRays']
            dchans[k] = arr
        return dchans


    @classmethod
    def _checkformat_inputs_dmisc(cls, color=None):
        if color is None:
            color = mpl.colors.to_rgba(cls._ddef['dmisc']['color'])
        assert mpl.colors.is_color_like(color)
        return tuple(mpl.colors.to_rgba(color))

    ###########
    # Get keys of dictionnaries
    ###########

    @staticmethod
    def _get_keys_dgeom():
        lk = ['D','u','pinhole',
              'kMin', 'kMax', 'PkMin', 'PkMax', 'vperp', 'indout',
              'kRMin', 'PRMin', 'RMin',
              'Etendues', 'Surfaces']
        return lk

    @staticmethod
    def _get_keys_dsino():
        lk = ['RefPt', 'k', 'pts',
              'theta','p','phi']
        return lk

    @staticmethod
    def _get_keys_dconfig():
        lk = ['config']
        return lk

    @staticmethod
    def _get_keys_dchans():
        lk = []
        return lk

    @staticmethod
    def _get_keys_dmisc():
        lk = ['color']
        return lk

    ###########
    # _init
    ###########

    def _init(self, dgeom=None, config=None, Etendues=None, Surfaces=None,
              sino_RefPt=None, dchans=None, **kwdargs):
        largs = self._get_largs_dgeom(sino=True)
        kwdgeom = self._extract_kwdargs(locals(), largs)
        largs = self._get_largs_dconfig()
        kwdconfig = self._extract_kwdargs(locals(), largs)
        largs = self._get_largs_dchans()
        kwdchans = self._extract_kwdargs(locals(), largs)
        largs = self._get_largs_dmisc()
        kwdmisc = self._extract_kwdargs(locals(), largs)
        self.set_dconfig(calcdgeom=False, **kwdconfig)
        self._set_dgeom(sino=True, **kwdgeom)
        self.set_dchans(**kwdchans)
        self._set_dmisc(**kwdmisc)
        self._dstrip['strip'] = 0

    ###########
    # set dictionaries
    ###########

    def set_dconfig(self, config=None, calcdgeom=True):
        config = self._checkformat_inputs_dconfig(config)
        self._dconfig['config'] = config.copy()
        if calcdgeom:
            self._compute_dgeom()

    def _compute_dgeom(self, extra=True):
        # Can only be computed if config if provided
        if self._dconfig['config'] is None:
            msg = "The dgeom cannot be computed without a config !"
            warnings.warn(msg)
            return

        # Prepare input
        D = np.ascontiguousarray(self.D)
        u = np.ascontiguousarray(self.u)

        # Get reference
        S = list(self.config._dstruct['dStruct']['PlasmaDomain'].values())[0]
        assert S.get_compute()
        VPoly = S.Poly_closed
        VVIn =  S.dgeom['VIn']
        Lim = S.Lim
        nLim = S.nLim
        VType = S.Id.Type

        lS = self.lStruct_compute
        lSPoly, lSVIn, lSLim, lSnLim = [], [], [], []
        for ss in lS:
            if not ss.Id.Cls=='PlasmaDomain':
                lSPoly.append(ss.Poly_closed)
                lSVIn.append(ss.dgeom['VIn'])
                lSLim.append(ss.Lim)
                lSnLim.append(ss.nLim)

        kargs = dict(RMin=None, Forbid=True, EpsUz=1.e-6, EpsVz=1.e-9,
                     EpsA=1.e-9, EpsB=1.e-9, EpsPlane=1.e-9, Test=True)

        #####################
        # call the dedicated function (Laura)
        out = _GG.LOS_Calc_PInOut_VesStruct(D, u,
                                            VPoly, VVIn, Lim=Lim, nLim=nLim,
                                            LSPoly=lSPoly, LSLim=lSLim,
                                            lSnLim=lSnLim, LSVIn=lSVIn,
                                            VType=VType, **kargs)
        # Currently computes and returns too many things
        PIn, POut, kMin, kMax, VperpIn, vperp, IIn, indout = out
        ######################

        ind = np.isnan(kMin)
        kMin[ind] = 0.
        ind = np.isnan(kMax) | np.isinf(kMax)
        if np.any(ind):
            kMax[ind] = np.nan
            msg = "Some LOS have no visibility inside the plasma domain !"
            warnings.warn(msg)
            if plotdebug:
                # To be updated
                _plot._LOS_calc_InOutPolProj_Debug(self.Ves, D[:,ind], u[:,ind],
                                                   PIn[:,ind], POut[:,ind],
                                                   fs=fs, wintit=wintit,
                                                   draw=draw)

        dd = {'kMin':kMin, 'kMax':kMax, 'vperp':vperp, 'indout':indout}
        self._dgeom.update(dd)
        if extra:
            self._compute_dgeom_kRMin()
            self._compute_dgeom_extra1()
            self._compute_dgeom_extra2D()

    def _compute_dgeom_kRMin(self):
        # Get RMin if Type is Tor
        if self.config.Id.Type=='Tor':
            kRMin = _comp.LOS_PRMin(self.D, self.u, kPOut=self.kMax, Eps=1.e-12)
        else:
            kRMin = None
        self._dgeom.update({'kRMin':kRMin})

    def _compute_dgeom_extra1(self):
        if self._dgeom['kRMin'] is not None:
            PRMin = self.D + self._dgeom['kRMin'][np.newaxis,:]*self.u
            RMin = np.hypot(PRMin[0,:],PRMin[1,:])
        PkMin = self.D + self._dgeom['kMin'][np.newaxis,:]*self.u
        PkMax = self.D + self._dgeom['kMax'][np.newaxis,:]*self.u
        dd = {'PkMin':PkMin, 'PkMax':PkMax, 'PRMin':PRMin, 'RMin':RMin}
        self._dgeom.update(dd)

    def _compute_dgeom_extra2D(self):
        if not '2d' in self.Id.Cls.lower():
            return
        D, u = self.D, self.u
        C = np.nanmean(D,axis=1)
        CD0 = D[:,:-1] - C[:,np.newaxis]
        CD1 = D[:,1:] - C[:,np.newaxis]
        cross = np.array([CD1[1,1:]*CD0[2,:-1]-CD1[2,1:]*CD0[1,:-1],
                          CD1[2,1:]*CD0[0,:-1]-CD1[0,1:]*CD0[2,:-1],
                          CD1[0,1:]*CD0[1,:-1]-CD1[1,1:]*CD0[0,:-1]])
        crossn2 = np.sum(cross**2,axis=0)
        if np.all(np.abs(crossn2)<1.e-12):
            msg = "Is %s really a 2D camera ? (LOS aligned?)"%self.Id.Name
            warnings.warn(msg)
        cross = cross[:,np.nanargmax(crossn2)]
        cross = cross / np.linalg.norm(cross)
        nIn = cross if np.sum(cross*np.nanmean(u,axis=1))>0. else -cross
        # Find most relevant e1 (for pixels alignment), without a priori info
        D0D = D-D[:,0][:,np.newaxis]
        dist = np.sqrt(np.sum(D0D**2,axis=0))
        dd = np.min(dist[1:])
        e1 = (D[:,1]-D[:,0])/np.linalg.norm(D[:,1]-D[:,0])
        cross = np.sqrt((D0D[1,:]*e1[2]-D0D[2,:]*e1[1])**2
                        + (D0D[2,:]*e1[0]-D0D[0,:]*e1[2])**2
                        + (D0D[0,:]*e1[1]-D0D[1,:]*e1[0])**2)
        D0D = D0D[:,cross<dd/3.]
        sca = np.sum(D0D*e1[:,np.newaxis],axis=0)
        e1 = D0D[:,np.argmax(np.abs(sca))]
        nIn, e1, e2 = utils.get_nIne1e2(C, nIn=nIn, e1=e1)
        if np.abs(np.abs(nIn[2])-1.)>1.e-12:
            if np.abs(e1[2])>np.abs(e2[2]):
                e1, e2 = e2, e1
        e2 = e2 if e2[2]>0. else -e2
        self._geom.update({'C':C, 'nIn':nIn, 'e1':e1, 'e2':e2})

    def set_Etendues(self, val):
        val = self._checkformat_inputs_dES(val)
        self._dgeom['Etendues'] = val

    def set_Surfaces(self, val):
        val = self._checkformat_inputs_dES(val)
        self._dgeom['Surfaces'] = val

    def _set_dgeom(self, dgeom=None, Etendues=None, Surfaces=None,
                   sino_RefPt=None,
                   extra=True, sino=True):
        dgeom = self._checkformat_inputs_dgeom(dgeom=dgeom)
        self._dgeom.update(dgeom)
        self._compute_dgeom(extra=extra)
        self.set_Etendues(Etendues)
        self.set_Etendues(Surfaces)
        if sino:
            self.set_dsino(sino_RefPt)

    def _compute_dsino_extra(self):
        if self._dsino['k'] is not None:
            pts = self.D + self._dsino['k'][np.newaxis,:]*self.u
            R = np.hypot(pts[0,:],pts[1,:])
            DR = R-self._dsino['RefPt'][0]
            DZ = pts[2,:]-self._dsino['RefPt'][1]
            p = np.hypot(DR,DZ)
            theta = np.arctan2(DZ,DR)
            ind = theta<0
            p[ind] = -p[ind]
            theta[ind] = -theta[ind]
            phipts = np.arctan2(pts[1,:],pts[0,:])
            etheta = np.array([np.cos(phipts)*np.cos(theta),
                               np.sin(phipts)*np.cos(theta),
                               np.sin(theta)])
            phi = np.arccos(np.abs(np.sum(etheta*self.u,axis=0)))
            dd = {'pts':pts, 'p':p, 'theta':theta, 'phi':phi}
            self._dsino.update(dd)

    def set_dsino(self, RefPt=None, extra=True):
        RefPt = self._checkformat_inputs_dsino(RefPt=RefPt)
        self._dsino.update({'RefPt':RefPt})
        VType = self.config.Id.Type
        if RefPt is not None:
            self._dconfig['config'].set_dsino(RefPt=RefPt)
            kMax = np.copy(self._dgeom['kMax'])
            kMax[np.isnan(kMax)] = np.inf
            try:
                out = _GG.LOS_sino(self.D, self.u, RefPt, kMax,
                                   Mode='LOS', VType=VType)
                Pt, k, r, Theta, p, theta, Phi = out
                self._dsino.update({'k':k})
            except Exception as err:
                msg = str(err)
                msg += "\nError while computing sinogram !"
                raise Exception(msg)
        if extra:
            self._compute_dsino_extra()

    def set_dchans(self, dchans=None):
        dchans = self._checkformat_inputs_dchans(dchans)
        self._dchans = dchans

    def _set_color(self, color=None):
        color = self._checkformat_inputs_dmisc(color=color)
        self._dmisc['color'] = color
        self._dplot['cross']['dP']['c'] = color
        self._dplot['hor']['dP']['c'] = color
        self._dplot['3d']['dP']['color'] = color

    def _set_dmisc(self, color=None):
        self._set_color(color)

    ###########
    # strip dictionaries
    ###########

    def _strip_dgeom(self, strip=0):
        if self._dstrip['strip']==strip:
            return

        if strip<self._dstrip['strip']:
            # Reload
            if self._dstrip['strip']==1:
                self._compute_dgeom_extra1()
                self._compute_dgeom_extra2D()
            elif self._dstrip['strip']>=2 and strip==1:
                self._compute_dgeom_kRMin()
            elif self._dstrip['strip']>=2 and strip==0:
                self._compute_dgeom_kRMin()
                self._compute_dgeom_extra1()
                self._compute_dgeom_extra2D()
        else:
            # strip
            if strip==1:
                lkeep = ['D','u','pinhole','nRays',
                         'kMin','kMax','vperp','indout', 'kRMin',
                         'Etendues','Surfaces']
                utils.ToFuObject._strip_dict(self._dgeom, lkeep=lkeep)
            elif self._dstrip['strip']<=1 and strip>=2:
                lkeep = ['D','u','pinhole','nRays',
                         'kMin','kMax','vperp','indout',
                         'Etendues','Surfaces']
                utils.ToFuObject._strip_dict(self._dgeom, lkeep=lkeep)

    def _strip_dconfig(self, strip=0):
        if self._dstrip['strip']==strip:
            return

        if strip<self._dstrip['strip']:
            if self._dstrip['strip']==4:
                pfe = self._dconfig['config']
                try:
                    self._dconfig['config'] = utils.load(pfe)
                except Exception as err:
                    msg = str(err)
                    msg += "\n    type(pfe) = {0}".format(str(type(pfe)))
                    msg += "\n    self._dstrip['strip'] = {0}".format(self._dstrip['strip'])
                    msg += "\n    strip = {0}".format(strip)
                    raise Exception(msg)

            self._dconfig['config'].strip(strip)
        else:
            if strip==4:
                path, name = self.config.Id.SavePath, self.config.Id.SaveName
                # --- Check !
                lf = os.listdir(path)
                lf = [ff for ff in lf
                      if all([s in ff for s in [name,'.npz']])]
                exist = len(lf)==1
                # ----------
                pathfile = os.path.join(path,name)+'.npz'
                if not exist:
                    msg = """BEWARE:
                        You are about to delete the Config object
                        Only the path/name to saved a object will be kept

                        But it appears that the following object has no
                        saved file where specified (obj.Id.SavePath)
                        Thus it won't be possible to retrieve it
                        (unless available in the current console:"""
                    msg += "\n    - {0}".format(pathfile)
                    if force:
                        warning.warn(msg)
                    else:
                        raise Exception(msg)
                self._dconfig['config'] = pathfile

            else:
                self._dconfig['config'].strip(strip)


    def _strip_dsino(self, strip=0):
        if self._dstrip['strip']==strip:
            return

        if strip<self._dstrip['strip']:
            if strip<=1 and self._dsino['k'] is not None:
                self._compute_dsino_extra()
        else:
            if self._dstrip['strip']<=1:
                utils.ToFuObject._strip_dict(self._dsino, lkeep=['RefPt','k'])

    def _strip_dmisc(self, lkeep=['color']):
        utils.ToFuObject._strip_dict(self._dmisc, lkeep=lkeep)


    ###########
    # _strip and get/from dict
    ###########

    @classmethod
    def _strip_init(cls):
        cls._dstrip['allowed'] = [0,1,2,3,4]
        nMax = max(cls._dstrip['allowed'])
        doc = """
                 1: dgeom w/o pts + config.strip(1)
                 2: dgeom w/o pts + config.strip(2) + dsino empty
                 3: dgeom w/o pts + config.strip(3) + dsino empty
                 4: dgeom w/o pts + config=pathfile + dsino empty
                 """
        doc = utils.ToFuObjectBase.strip.__doc__.format(doc,nMax)
        cls.strip.__doc__ = doc

    def strip(self, strip=0):
        super().strip(strip=strip)

    def _strip(self, strip=0):
        self._strip_dconfig(strip=strip)
        self._strip_dgeom(strip=strip)
        self._strip_dsino(strip=strip)

    def _to_dict(self):
        dout = {'dconfig':{'dict':self._dconfig, 'lexcept':None},
                'dgeom':{'dict':self.dgeom, 'lexcept':None},
                'dchans':{'dict':self.dchans, 'lexcept':None},
                'dsino':{'dict':self.dsino, 'lexcept':None}}
        return dout

    def _from_dict(self, fd):
        self._dconfig.update(**fd['dconfig'])
        self._dgeom.update(**fd['dgeom'])
        self._dsino.update(**fd['dsino'])
        if 'dchans' in fd.keys():
            self._dchans.update(**fd['dchans'])


    ###########
    # properties
    ###########


    @property
    def dgeom(self):
        return self._dgeom
    @property
    def dchans(self):
        return self._dchans
    @property
    def dsino(self):
        return self._dsino

    @property
    def isPinhole(self):
        return self._dgeom['u'] is None

    @property
    def nRays(self):
        return self._dgeom['nRays']

    @property
    def D(self):
        if self._dgeom['D'].shape[1]<self._dgeom['nRays']:
            D = np.tile(self._dgeom['D'], self._dgeom['nRays'])
        else:
            D = self._dgeom['D']
        return D

    @property
    def u(self):
        if self.isPinhole:
            u = self._dgeom['pinhole'][:,np.newaxis]-self._dgeom['D']
            u = u/np.sqrt(np.sum(u**2,axis=0))[np.newaxis,:]
        elif self._dgeom['u'].shape[1]<self._dgeom['nRays']:
            u = np.tile(self._dgeom['u'], self._dgeom['nRays'])
        else:
            u = self._dgeom['u']
        return u

    @property
    def pinhole(self):
        if self._dgeom['pinhole'] is None:
            msg = "This is not a pinhole camera => pinhole is None"
            warnings.warn(msg)
        return self._dgeom['pinhole']

    @property
    def config(self):
        return self._dconfig['config']

    @property
    def lStruct_compute(self):
        compute = self.config.get_compute()
        lS = self.config.lStruct
        lS = [lS[ii] for ii in range(0,len(lS)) if compute[ii]]
        return lS

    @property
    def Etendues(self):
        return self._dgeom['Etendues']
    @property
    def Surfaces(self):
        return self._dgeom['Surfaces']

    @property
    def kMin(self):
        return self._dgeom['kMin']
    @property
    def kMax(self):
        return self._dgeom['kMax']


    ###########
    # public methods
    ###########

    def select(self, key=None, val=None, touch=None, log='any', out=int):
        """ Return the indices of the rays matching selection criteria

        The criterion can be of two types:
            - a key found in self.dchans, with a matching value
            - a touch tuple (indicating which element in self.config is touched
                by the desired rays)

        Parameters
        ----------
        key :    None / str
            A key to be found in self.dchans
        val :   int / str / float / list of such
            The value to be matched
            If a list of values is provided, the behaviour depends on log
        log :   str
            A flag indicating which behaviour to use when val is a list
                - any : Returns indices of rays matching any value in val
                - all : Returns indices of rays matching all values in val
                - not : Returns indices of rays matching None of the val
        touch:  None / str / int / tuple
            Used if key is None
            Tuple that can be of len()=1, 2 or 3
            Tuple indicating you want the rays that are touching some specifi            elements of self.config:
                - touch[0] : str / int or list of such
                    str : a 'Cls_Name' string indicating the element
                    int : the index of the element in self.lStruct_compute
                - touch[1] : int / list of int
                    Indices of the desired segments on the polygon
                    (i.e.: of the cross-section polygon of the above element)
                - touch[2] : int / list of int
                    Indices, if relevant, of the toroidal / linear unit
                    Only relevant when the element has nLim>1
            In this case only log='not' has an effect
        out :   str
            Flag indicating whether to return:
                - bool : a (nRays,) boolean array of indices
                - int :  a (N,) array of int indices (N=number of matching rays)

        Returns
        -------
        ind :   np.ndarray
            The array of matching rays

        """
        assert out in [int,bool]
        assert log in ['any','all','not']
        C = [key is None,touch is None]
        assert np.sum(C)>=1
        if np.sum(C)==2:
            ind = np.ones((self.nRays,),dtype=bool)
        else:
            if key is not None:
                assert type(key) is str and key in self._dchans.keys()
                ltypes = [str,int,float,np.int64,np.float64]
                C0 = type(val) in ltypes
                C1 = type(val) in [list,tuple,np.ndarray]
                assert C0 or C1
                if C0:
                    val = [val]
                else:
                    assert all([type(vv) in ltypes for vv in val])
                ind = np.vstack([self._dchans[key]==ii for ii in val])
                if log=='any':
                    ind = np.any(ind,axis=0)
                elif log=='all':
                    ind = np.all(ind,axis=0)
                else:
                    ind = ~np.any(ind,axis=0)

            elif touch is not None:
                C0 = type(touch) is str and '_' in touch
                C1 = type(touch) in [int,np.int64]
                C2 = type(touch) in [list,tuple] and len(touch) in [2,3]
                assert C0 or C1 or C2
                if C0 or C1:
                    touch = [touch]
                else:
                    lint = [int,np.int64]
                    larr = [list,tuple,np.ndarray]
                    C0 = type(touch[0]) is str and '_' in touch[0]
                    C1a = type(touch[1]) in lint
                    C1b = (type(touch[1]) in larr
                           and all([type(t) in lint for t in touch[1]]))
                    assert C0 and (C1a or C1b)
                    if C1a:
                        touch[1] = [touch[1]]
                    if len(touch)==3:
                        C2a = type(touch[2]) in lint
                        C2b = (type(touch[2]) in larr
                               and all([type(t) in lint for t in touch[2]]))
                        assert C2a or C2b
                        if C2a:
                            touch[2] = [touch[2]]
                ntouch = len(touch)

                # Common part
                if type(touch[0]) is str:
                    lS = self.lStruct_compute
                    k0, k1 = touch[0].split('_')
                    ind = [ii for ii in range(0,len(lS))
                           if lS[ii].Id.Cls==k0 and lS[ii].Id.Name==k1]
                    assert len(ind)==1
                    touch[0] = ind[0]

                ind = np.zeros((ntouch,self.nRays),dtype=bool)
                for i in range(0,ntouch):
                    for n in len(touch[i]):
                        ind[i,:] = (ind[i,:]
                                    | self._dgeom['indout'][i,:]==touch[i][n])
                ind = np.all(ind,axis=0)
                ind = ~ind if log=='not' else ind
        if out is int:
            ind = ind.nonzero()[0]
        return ind

    def get_subset(self, indch=None):
        if indch is None:
            return self
        else:
            assert type(indch) is np.ndarray and indch.ndim==1
            assert indch.dtype in [np.int64,np.bool_]
            d = self._todict()
            d['Id']['Name'] = d['Id']['Name']+'-subset'
            d['dchans'] = dict([(vv,vv[indch]) for vv in d['chans'].keys()])

            # Geom
            for kk in d['geom']:
                C0 = type(d['geom'][kk]) is np.ndarray
                C1 = d['geom'][kk].ndim==1 and d['geom'][kk].size==self.nRays
                C2 = d['geom'][kk].ndim==2 and d['geom'][kk].shape[1]==self.nRays
                C3 = kk in ['C','nIn','e1','e2']
                if C0 and C1 and not C3:
                    d['geom'][kk] = d['geom'][kk][indch]
                elif C0 and C2 and not C3:
                    d['geom'][kk] = d['geom'][kk][:,indch]

            # Sino
            for kk in d['sino'].keys():
                if d['sino'][kk].ndim==2:
                    d['sino'][kk] = d['sino'][kk][:,indch]
                elif d['sino'][kk].ndim==1:
                    d['sino'][kk] = d['sino'][kk][indch]

            if 'Rays' in self.Id.Cls:
                c = tfg.Rays(fromdict=d)
            elif 'LOSCam1D' in self.Id.Cls:
                c = tfg.LOSCam1D(fromdict=d)
            elif 'LOSCam2D' in self.Id.Cls:
                c = tfg.LOSCam2D(fromdict=d)
            elif 'Cam1D' in self.Id.Cls:
                c = tfg.Cam1D(fromdict=d)
            elif 'Cam2D' in self.Id.Cls:
                c = tfg.Cam2D(fromdict=d)

        return c

    def _get_plotL(self, Lplot='Tot', Proj='All', ind=None, multi=False):
        self._check_inputs(ind=ind)
        if ind is not None:
            ind = np.asarray(ind)
            if ind.dtype in [bool,np.bool_]:
                ind = ind.nonzero()[0]
        else:
            ind = np.arange(0,self.nRays)
        if len(ind)>0:
            Ds, us = self.D[:,ind], self.u[:,ind]
            if len(ind)==1:
                Ds, us = Ds.reshape((3,1)), us.reshape((3,1))
            kPIn, kPOut = self.geom['kPIn'][ind], self.geom['kPOut'][ind]
            kRMin = self.geom['kRMin'][ind]
            pts = _comp.LOS_CrossProj(self.Ves.Type, Ds, us, kPIn, kPOut,
                                      kRMin, Proj=Proj,Lplot=Lplot,multi=multi)
        else:
            pts = None
        return pts

    def get_sample(self, dl, dlMode='abs', DL=None, method='sum', ind=None):
        """ Return a linear sampling of the LOS

        The LOS is sampled into a series a points and segments lengths
        The resolution (segments length) is <= dl
        The sampling can be done according to different methods
        It is possible to sample only a subset of the LOS

        Parameters
        ----------
        dl:     float
            Desired resolution
        dlMode: str
            Flag indicating dl should be understood as:
                - 'abs':    an absolute distance in meters
                - 'rel':    a relative distance (fraction of the LOS length)
        DL:     None / iterable
            The fraction [L1;L2] of the LOS that should be sampled, where
            L1 and L2 are distances from the starting point of the LOS (LOS.D)
        method: str
            Flag indicating which to use for sampling:
                - 'sum':    the LOS is sampled into N segments of equal length,
                            where N is the smallest int such that:
                                * segment length <= resolution(dl,dlMode)
                            The points returned are the center of each segment
                - 'simps':  the LOS is sampled into N segments of equal length,
                            where N is the smallest int such that:
                                * segment length <= resolution(dl,dlMode)
                                * N is even
                            The points returned are the egdes of each segment
                - 'romb':   the LOS is sampled into N segments of equal length,
                            where N is the smallest int such that:
                                * segment length <= resolution(dl,dlMode)
                                * N = 2^k + 1
                            The points returned are the egdes of each segment

        Returns
        -------
        Pts:    np.ndarray
            A (3,NP) array of NP points along the LOS in (X,Y,Z) coordinates
        kPts:   np.ndarray
            A (NP,) array of the points distances from the LOS starting point
        dl:     float
            The effective resolution (<= dl input), as an absolute distance

        """
        self._check_inputs(ind=ind)
        # Preformat ind
        if ind is None:
            ind = np.arange(0,self.nRays)
        if np.asarray(ind).dtype is bool:
            ind = ind.nonzero()[0]
        # Preformat DL
        if DL is None:
            DL = np.array([self.geom['kPIn'][ind],self.geom['kPOut'][ind]])
        elif np.asarray(DL).size==2:
            DL = np.tile(np.asarray(DL).ravel(),(len(ind),1)).T
        DL = np.ascontiguousarray(DL).astype(float)
        assert type(DL) is np.ndarray and DL.ndim==2
        assert DL.shape==(2,len(ind)), "Arg DL has wrong shape !"
        ii = DL[0,:]<self.geom['kPIn'][ind]
        DL[0,ii] = self.geom['kPIn'][ind][ii]
        ii = DL[0,:]>=self.geom['kPOut'][ind]
        DL[0,ii] = self.geom['kPOut'][ind][ii]
        ii = DL[1,:]>self.geom['kPOut'][ind]
        DL[1,ii] = self.geom['kPOut'][ind][ii]
        ii = DL[1,:]<=self.geom['kPIn'][ind]
        DL[1,ii] = self.geom['kPIn'][ind][ii]
        # Preformat Ds, us
        Ds, us = self.D[:,ind], self.u[:,ind]
        if len(ind)==1:
            Ds, us = Ds.reshape((3,1)), us.reshape((3,1))
        Ds, us = np.ascontiguousarray(Ds), np.ascontiguousarray(us)
        # Launch    # NB : find a way to exclude cases with DL[0,:]>=DL[1,:] !!
        Pts, kPts, dlr = _GG.LOS_get_sample(Ds, us, dl, DL,
                                            dLMode=dlMode, method=method)
        return Pts, kPts, dlr


    def get_kInkOut(self, lPoly, Lim=None):
        msg = "Arg lPoly must be a list or np.ndarray !"
        assert type(lPoly) in [list, np.ndarray], msg

        # Preformat input
        if type(lPoly) is np.ndarray:
            lPoly = [lPoly]
        lPoly = [np.ascontiguousarray(pp) for pp in lPoly]
        msg = "Arg lPoly must be a list of (2,N) or (N,2) np.ndarrays !"
        assert all([pp.ndim==2 and 2 in pp.shape for pp in lPoly]), msg
        nPoly = len(lPoly)
        for ii in range(0,nPoly):
            if lPoly[ii].shape[0]!=2:
                lPoly[ii] = lPoly[ii].T

        if Lim is None and self.Ves is not None and self.Ves.Type=='Lin':
            Lim = self.Ves.Lim

        # Prepare output
        kIn = np.full((self.nRays,nPoly), np.nan)
        kOut = np.full((self.nRays,nPoly), np.nan)

        # Compute intersections
        for ii in range(0,nPoly):
            VIn = np.diff(lPoly[ii],axis=1)
            VIn = VIn/(np.sqrt(np.sum(VIn**2,axis=0))[np.newaxis,:])
            VIn = np.ascontiguousarray([-VIn[1,:],VIn[0,:]])
            sca = VIn[0,0]*(isoR[0,0]-VP[0,0]) + VIn[1,0]*(isoZ[0,0]-VP[1,0])
            if sca<0:
                VIn = -VIn
            Out = tf.geom._GG.LOS_Calc_PInOut_VesStruct(self.D, self.u,
                                                        lPoly[ii], VIn, Lim=Lim)
            kPIn[:,ii], kPOut[:,ii] = Out[2:4]

        return kIn, kOut


    def calc_signal(self, ff, t=None, Ani=None, fkwdargs={}, Brightness=True,
                    dl=0.005, DL=None, dlMode='abs', method='sum',
                    ind=None, out=object, plot=True, plotmethod='imshow',
                    fs=None, dmargin=None, wintit='tofu', invert=True,
                    units=None, draw=True, connect=True):
        """ Return the line-integrated emissivity

        Beware, by default, Brightness=True and it is only a line-integral !

        Indeed, to get the received power, you need an estimate of the Etendue
        (previously set using self.set_Etendues()) and use Brightness=False.

        Hence, if Brightness=True and if
        the emissivity is provided in W/m3 (resp. W/m3/sr),
        => the method returns W/m2 (resp. W/m2/sr)
        The line is sampled using :meth:`~tofu.geom.LOS.get_sample`,

        The integral can be computed using three different methods:
            - 'sum':    A numpy.sum() on the local values (x segments lengths)
            - 'simps':  using :meth:`scipy.integrate.simps`
            - 'romb':   using :meth:`scipy.integrate.romb`

        Except ff, arguments common to :meth:`~tofu.geom.LOS.get_sample`

        Parameters
        ----------
        ff :    callable
            The user-provided

        Returns
        -------
        sig :   np.ndarray
            The computed signal, a 1d or 2d array depending on whether a time
            vector was provided.
        units:  str
            Units of the result

        """
        self._check_inputs(ind=ind)
        assert type(Brightness) is bool, "Arg Brightness must be a bool !"
        if Brightness is False:
            msg = "Etendue must be set if Brightness is False !"
            assert self.Etendues is not None, msg

        # Preformat ind
        if ind is None:
            ind = np.arange(0,self.nRays)
        if np.asarray(ind).dtype is bool:
            ind = ind.nonzero()[0]
        # Preformat DL
        if DL is None:
            DL = np.array([self.geom['kPIn'][ind],self.geom['kPOut'][ind]])
        elif np.asarray(DL).size==2:
            DL = np.tile(np.asarray(DL).ravel(),(len(ind),1)).T
        DL = np.ascontiguousarray(DL).astype(float)
        assert type(DL) is np.ndarray and DL.ndim==2
        assert DL.shape==(2,len(ind)), "Arg DL has wrong shape !"
        ii = DL[0,:]<self.geom['kPIn'][ind]
        DL[0,ii] = self.geom['kPIn'][ind][ii]
        ii = DL[0,:]>=self.geom['kPOut'][ind]
        DL[0,ii] = self.geom['kPOut'][ind][ii]
        ii = DL[1,:]>self.geom['kPOut'][ind]
        DL[1,ii] = self.geom['kPOut'][ind][ii]
        ii = DL[1,:]<=self.geom['kPIn'][ind]
        DL[1,ii] = self.geom['kPIn'][ind][ii]
        # Preformat Ds, us and Etendue
        Ds, us = self.D[:,ind], self.u[:,ind]
        if Brightness is False:
            E = self.Etendues
            if self.Etendues.size==self.nRays:
                E = E[ind]
        if len(ind)==1:
            Ds, us = Ds.reshape((3,1)), us.reshape((3,1))
        if t is None or len(t)==1:
            sig = np.full((Ds.shape[1],),np.nan)
        else:
            sig = np.full((len(t),Ds.shape[1]),np.nan)
        indok = ~(np.any(np.isnan(DL),axis=0) | np.any(np.isinf(DL),axis=0)
                  | ((DL[1,:]-DL[0,:])<=0.))
        if np.any(indok):
            Ds, us, DL = Ds[:,indok], us[:,indok], DL[:,indok]
            if indok.sum()==1:
                Ds, us = Ds.reshape((3,1)), us.reshape((3,1))
                DL = DL.reshape((2,1))
            Ds, us = np.ascontiguousarray(Ds), np.ascontiguousarray(us)
            DL = np.ascontiguousarray(DL)
            # Launch    # NB : find a way to exclude cases with DL[0,:]>=DL[1,:] !!
            # Exclude Rays not seeing the plasma
            s = _GG.LOS_calc_signal(ff, Ds, us, dl, DL,
                                    dLMode=dlMode, method=method,
                                    t=t, Ani=Ani, fkwdargs=fkwdargs, Test=True)
            if t is None or len(t)==1:
                sig[indok] = s
            else:
                sig[:,indok] = s
        if Brightness is False:
            if t is None or len(t)==1 or E.size==1:
                sig = sig*E
            else:
                sig = sig*E[np.newaxis,:]
            if units is None:
                units = r"origin x $m^3.sr$"
        elif units is None:
            units = r"origin x m"

        if plot or out is object:
            assert '1D' in self.Id.Cls or '2D' in self.Id.Cls, "Set Cam type!!"
            import tofu.data as tfd
            if '1D' in self.Id.Cls:
                osig = tfd.Data1D(data=sig, t=t, LCam=self,
                                  Id=self.Id.Name, dunits={'data':units},
                                  Exp=self.Id.Exp, Diag=self.Id.Diag)
            else:
                osig = tfd.Data2D(data=sig, t=t, LCam=self,
                                  Id=self.Id.Name, dunits={'data':units},
                                  Exp=self.Id.Exp, Diag=self.Id.Diag)
            if plot:
                KH = osig.plot(fs=fs, dmargin=dmargin, wintit=wintit,
                               plotmethod=plotmethod, invert=invert,
                               draw=draw, connect=connect)
            if out is object:
                sig = osig
        return sig, units

    def plot(self, Lax=None, Proj='All', Lplot=_def.LOSLplot, Elt='LDIORP',
             EltVes='', EltStruct='', Leg='', dL=None, dPtD=_def.LOSMd,
             dPtI=_def.LOSMd, dPtO=_def.LOSMd, dPtR=_def.LOSMd,
             dPtP=_def.LOSMd, dLeg=_def.TorLegd, dVes=_def.Vesdict,
             dStruct=_def.Structdict, multi=False, ind=None,
             fs=None, wintit='tofu', draw=True, Test=True):
        """ Plot the Rays / LOS, in the chosen projection(s)

        Optionnally also plot associated :class:`~tofu.geom.Ves` and Struct
        The plot can also include:
            - special points
            - the unit directing vector

        Parameters
        ----------
        Lax :       list / plt.Axes
            The axes for plotting (list of 2 axes if Proj='All')
            If None a new figure with new axes is created
        Proj :      str
            Flag specifying the kind of projection:
                - 'Cross' : cross-section
                - 'Hor' : horizontal
                - 'All' : both cross-section and horizontal (on 2 axes)
                - '3d' : a (matplotlib) 3d plot
        Elt :       str
            Flag specifying which elements to plot
            Each capital letter corresponds to an element:
                * 'L': LOS
                * 'D': Starting point of the LOS
                * 'I': Input point (i.e.: where the LOS enters the Vessel)
                * 'O': Output point (i.e.: where the LOS exits the Vessel)
                * 'R': Point of minimal major radius R (only if Ves.Type='Tor')
                * 'P': Point of used for impact parameter (i.e.: with minimal
                        distance to reference point Sino_RefPt)
        Lplot :     str
            Flag specifying the length to plot:
                - 'Tot': total length, from starting point (D) to output point
                - 'In' : only the in-vessel fraction (from input to output)
        EltVes :    str
            Flag for Ves elements to plot (:meth:`~tofu.geom.Ves.plot`)
        EltStruct : str
            Flag for Struct elements to plot (:meth:`~tofu.geom.Struct.plot`)
        Leg :       str
            Legend, if Leg='' the LOS name is used
        dL :     dict / None
            Dictionary of properties for plotting the lines
            Fed to plt.Axes.plot(), set to default if None
        dPtD :      dict
            Dictionary of properties for plotting point 'D'
        dPtI :      dict
            Dictionary of properties for plotting point 'I'
        dPtO :      dict
            Dictionary of properties for plotting point 'O'
        dPtR :      dict
            Dictionary of properties for plotting point 'R'
        dPtP :      dict
            Dictionary of properties for plotting point 'P'
        dLeg :      dict or None
            Dictionary of properties for plotting the legend
            Fed to plt.legend(), the legend is not plotted if None
        dVes :      dict
            Dictionary of kwdargs to fed to :meth:`~tofu.geom.Ves.plot`
            And 'EltVes' is used instead of 'Elt'
        dStruct:    dict
            Dictionary of kwdargs to fed to :meth:`~tofu.geom.Struct.plot`
            And 'EltStruct' is used instead of 'Elt'
        draw :      bool
            Flag indicating whether fig.canvas.draw() shall be called
        a4 :        bool
            Flag indicating whether to plot the figure in a4 dimensions
        Test :      bool
        a4 :        bool
            Flag indicating whether to plot the figure in a4 dimensions
        Test :      bool
        a4 :        bool
            Flag indicating whether to plot the figure in a4 dimensions
        Test :      bool
        a4 :        bool
            Flag indicating whether to plot the figure in a4 dimensions
        Test :      bool
        Test :      bool
            Flag indicating whether the inputs should be tested for conformity

        Returns
        -------
        La :        list / plt.Axes
            Handles of the axes used for plotting (list if Proj='All')

        """

        return _plot.Rays_plot(self, Lax=Lax, Proj=Proj, Lplot=Lplot, Elt=Elt,
                               EltVes=EltVes, EltStruct=EltStruct, Leg=Leg,
                               dL=dL, dPtD=dPtD, dPtI=dPtI, dPtO=dPtO, dPtR=dPtR,
                               dPtP=dPtP, dLeg=dLeg, dVes=dVes, dStruct=dStruct,
                               multi=multi, ind=ind,
                               fs=fs, wintit=wintit, draw=draw, Test=Test)


    def plot_sino(self, Proj='Cross', ax=None, Elt=_def.LOSImpElt, Sketch=True,
                  Ang=_def.LOSImpAng, AngUnit=_def.LOSImpAngUnit, Leg=None,
                  dL=_def.LOSMImpd, dVes=_def.TorPFilld, dLeg=_def.TorLegd,
                  ind=None, multi=False,
                  fs=None, wintit='tofu', draw=True, Test=True):
        """ Plot the LOS in projection space (sinogram)

        Plot the Rays in projection space (cf. sinograms) as points.
        Can also optionnally plot the associated :class:`~tofu.geom.Ves`

        Can plot the conventional projection-space (in 2D in a cross-section),
        or a 3D extrapolation of it, where the third coordinate is provided by
        the angle that the LOS makes with the cross-section plane
        (useful in case of multiple LOS with a partially tangential view)

        Parameters
        ----------
        Proj :      str
            Flag indicating whether to plot:
                - 'Cross':  a classic sinogram (vessel cross-section)
                - '3d': an extended 3D version ('3d'), with an additional angle
        ax :        None / plt.Axes
            The axes on which to plot, if None a new figure is created
        Elt :       str
            Flag indicating which elements to plot (one per capital letter):
                * 'L': LOS
                * 'V': Vessel
        Ang  :      str
            Flag indicating which angle to use for the impact parameter:
                - 'xi': the angle of the line itself
                - 'theta': its impact parameter (theta)
        AngUnit :   str
            Flag for the angle units to be displayed:
                - 'rad': for radians
                - 'deg': for degrees
        Sketch :    bool
            Flag indicating whether to plot a skecth with angles definitions
        dL :        dict
            Dictionary of properties for plotting the Rays points
        dV :        dict
            Dictionary of properties for plotting the vessel envelopp
        dLeg :      None / dict
            Dictionary of properties for plotting the legend
            The legend is not plotted if None
        draw :      bool
            Flag indicating whether to draw the figure
        a4 :        bool
            Flag indicating whether the figure should be a4
        Test :      bool
            Flag indicating whether the inputs shall be tested for conformity

        Returns
        -------
        ax :        plt.Axes
            The axes used to plot

        """
        assert self.sino is not None, "The sinogram ref. point is not set !"
        return _plot.GLOS_plot_Sino(self, Proj=Proj, ax=ax, Elt=Elt, Leg=Leg,
                                    Sketch=Sketch, Ang=Ang, AngUnit=AngUnit,
                                    dL=dL, dVes=dVes, dLeg=dLeg,
                                    ind=ind, fs=fs, wintit=wintit,
                                    draw=draw, Test=Test)

    def plot_touch(self, key=None, invert=None, plotmethod='imshow',
                   lcol=['k','r','b','g','y','m','c'],
                   fs=None, wintit='tofu', draw=True):
        assert self.Id.Cls in ['LOSCam1D','LOSCam2D'], "Specify camera type !"
        assert self.Ves is not None, "self.Ves should not be None !"
        out = _plot.Rays_plot_touch(self, key=key, invert=invert,
                                    lcol=lcol, plotmethod=plotmethod,
                                    fs=fs, wintit=wintit, draw=draw)
        return out









def _Rays_check_fromdict(fd):
    assert type(fd) is dict, "Arg from dict must be a dict !"
    k0 = {'Id':dict,'geom':dict,'sino':dict,
          'dchans':[None,dict],
          'Ves':[None,dict], 'LStruct':[None,list]}
    keys = list(fd.keys())
    for kk in k0:
        assert kk in keys, "%s must be a key of fromdict"%kk
        typ = type(fd[kk])
        C = typ is k0[kk] or typ in k0[kk] or fd[kk] in k0[kk]
        assert C, "Wrong type of fromdict[%s]: %s"%(kk,str(typ))







class LOSCam1D(Rays):
    def __init__(self, Id=None, Du=None, Ves=None, LStruct=None,
                 Sino_RefPt=None, fromdict=None,
                 Exp=None, Diag=None, shot=0, Etendues=None,
                 dchans=None, SavePath=os.path.abspath('./'),
                 plotdebug=True):
        Rays.__init__(self, Id=Id, Du=Du, Ves=Ves, LStruct=LStruct,
                 Sino_RefPt=Sino_RefPt, fromdict=fromdict, Etendues=Etendues,
                 Exp=Exp, Diag=Diag, shot=shot, plotdebug=plotdebug,
                 dchans=dchans, SavePath=SavePath)

class LOSCam2D(Rays):
    def __init__(self, Id=None, Du=None, Ves=None, LStruct=None,
                 Sino_RefPt=None, fromdict=None, Etendues=None,
                 Exp=None, Diag=None, shot=0, X12=None,
                 dchans=None, SavePath=os.path.abspath('./'),
                 plotdebug=True):
        Rays.__init__(self, Id=Id, Du=Du, Ves=Ves, LStruct=LStruct,
                 Sino_RefPt=Sino_RefPt, fromdict=fromdict, Etendues=Etendues,
                 Exp=Exp, Diag=Diag, shot=shot, plotdebug=plotdebug,
                 dchans=dchans, SavePath=SavePath)
        self.set_X12(X12)

    def set_e12(self, e1=None, e2=None):
        assert e1 is None or (hasattr(e1,'__iter__') and len(e1)==3)
        assert e2 is None or (hasattr(e2,'__iter__') and len(e2)==3)
        if e1 is None:
            e1 = self._geom['e1']
        else:
            e1 = np.asarray(e1).astype(float).ravel()
        e1 = e1 / np.linalg.norm(e1)
        if e2 is None:
            e2 = self._geom['e2']
        else:
            e2 = np.asarray(e1).astype(float).ravel()
        e2 = e2 / np.linalg.norm(e2)
        assert np.abs(np.sum(e1*self._geom['nIn']))<1.e-12
        assert np.abs(np.sum(e2*self._geom['nIn']))<1.e-12
        assert np.abs(np.sum(e1*e2))<1.e-12
        self._geom['e1'] = e1
        self._geom['e2'] = e2

    def set_X12(self, X12=None):
        if X12 is not None:
            X12 = np.asarray(X12)
            assert X12.shape==(2,self.Ref['nch'])
        self._X12 = X12

    def get_X12(self, out='1d'):
        if self._X12 is None:
            Ds = self.D
            C = np.mean(Ds,axis=1)
            X12 = Ds-C[:,np.newaxis]
            X12 = np.array([np.sum(X12*self.geom['e1'][:,np.newaxis],axis=0),
                            np.sum(X12*self.geom['e2'][:,np.newaxis],axis=0)])
        else:
            X12 = self._X12
        if X12 is None or out.lower()=='1d':
            DX12 = None
        else:
            x1u, x2u, ind, DX12 = utils.get_X12fromflat(X12)
            if out.lower()=='2d':
                X12 = [x1u, x2u, ind]
        return X12, DX12







    """ Return the indices or instances of all LOS matching criteria

    The selection can be done according to 2 different mechanisms

    Mechanism (1): provide the value (Val) a criterion (Crit) should match
    The criteria are typically attributes of :class:`~tofu.pathfile.ID`
    (i.e.: name, or user-defined attributes like the camera head...)

    Mechanism (2): (used if Val=None)
    Provide a str expression (or a list of such) to be fed to eval()
    Used to check on quantitative criteria.
        - PreExp: placed before the criterion value (e.g.: 'not ' or '<=')
        - PostExp: placed after the criterion value
        - you can use both

    Other parameters are used to specify logical operators for the selection
    (match any or all the criterion...) and the type of output.

    Parameters
    ----------
    Crit :      str
        Flag indicating which criterion to use for discrimination
        Can be set to:
            - any attribute of :class:`~tofu.pathfile.ID`
        A str (or list of such) expression to be fed to eval()
        Placed after the criterion value
        Used for selection mechanism (2)
    Log :       str
        Flag indicating whether the criterion shall match:
            - 'all': all provided values
            - 'any': at least one of them
    InOut :     str
        Flag indicating whether the returned indices are:
            - 'In': the ones matching the criterion
            - 'Out': the ones not matching it
    Out :       type / str
        Flag indicating in which form to return the result:
            - int: as an array of integer indices
            - bool: as an array of boolean indices
            - 'Name': as a list of names
            - 'LOS': as a list of :class:`~tofu.geom.LOS` instances

    Returns
    -------
    ind :       list / np.ndarray
        The computed output, of nature defined by parameter Out

    Examples
    --------
    >>> import tofu.geom as tfg
    >>> VPoly, VLim = [[0.,1.,1.,0.],[0.,0.,1.,1.]], [-1.,1.]
    >>> V = tfg.Ves('ves', VPoly, Lim=VLim, Type='Lin', Exp='Misc', shot=0)
    >>> Du1 = ([0.,-0.1,-0.1],[0.,1.,1.])
    >>> Du2 = ([0.,-0.1,-0.1],[0.,0.5,1.])
    >>> Du3 = ([0.,-0.1,-0.1],[0.,1.,0.5])
    >>> l1 = tfg.LOS('l1', Du1, Ves=V, Exp='Misc', Diag='A', shot=0)
    >>> l2 = tfg.LOS('l2', Du2, Ves=V, Exp='Misc', Diag='A', shot=1)
    >>> l3 = tfg.LOS('l3', Du3, Ves=V, Exp='Misc', Diag='B', shot=1)
    >>> gl = tfg.GLOS('gl', [l1,l2,l3])
    >>> Arg1 = dict(Val=['l1','l3'],Log='any',Out='LOS')
    >>> Arg2 = dict(Val=['l1','l3'],Log='any',InOut='Out',Out=int)
    >>> Arg3 = dict(Crit='Diag', Val='A', Out='Name')
    >>> Arg4 = dict(Crit='shot', PostExp='>=1')
    >>> gl.select(**Arg1)
    [l1,l3]
    >>> gl.select(**Arg2)
    array([1])
    >>> gl.select(**Arg3)
    ['l1','l2']
    >>> gl.select(**Arg4)
    array([False, True, True], dtype=bool)

    """
