import math

import gmsh

from .bspline import BSpline
from .circle_arc import CircleArc
from .curve_loop import CurveLoop
from .dummy import Dummy
from .ellipse_arc import EllipseArc
from .line import Line
from .plane_surface import PlaneSurface
from .point import Point
from .spline import Spline
from .surface import Surface
from .surface_loop import SurfaceLoop
from .volume import Volume


class CommonGeometry:
    """Geometry base class containing all methods that can be shared between built-in
    and opencascade.
    """

    def __init__(self, env):
        self.env = env
        self._BOOLEAN_ID = 0
        self._ARRAY_ID = 0
        self._FIELD_ID = 0
        self._TAKEN_PHYSICALGROUP_IDS = []
        self._COMPOUND_ENTITIES = []
        self._RECOMBINE_ENTITIES = []
        self._EMBED_QUEUE = []
        self._TRANSFINITE_CURVE_QUEUE = []
        self._TRANSFINITE_SURFACE_QUEUE = []
        self._AFTER_SYNC_QUEUE = []
        self._SIZE_QUEUE = []

    def __enter__(self):
        gmsh.initialize()
        gmsh.model.add("pygmsh model")
        return self

    def __exit__(self, *a):
        gmsh.finalize()

    def synchronize(self):
        self.env.synchronize()

    def __repr__(self):
        return "<pygmsh Geometry object>"

    def add_bspline(self, *args, **kwargs):
        return BSpline(self.env, *args, **kwargs)

    def add_circle_arc(self, *args, **kwargs):
        return CircleArc(self.env, *args, **kwargs)

    def add_ellipse_arc(self, *args, **kwargs):
        return EllipseArc(self.env, *args, **kwargs)

    def add_line(self, *args, **kwargs):
        return Line(self.env, *args, **kwargs)

    def add_curve_loop(self, *args, **kwargs):
        return CurveLoop(self.env, *args, **kwargs)

    def add_plane_surface(self, *args, **kwargs):
        return PlaneSurface(self.env, *args, **kwargs)

    def add_point(self, *args, **kwargs):
        return Point(self.env, *args, **kwargs)

    def add_spline(self, *args, **kwargs):
        return Spline(self.env, *args, **kwargs)

    def add_surface(self, *args, **kwargs):
        return Surface(self.env, *args, **kwargs)

    def add_surface_loop(self, *args, **kwargs):
        return SurfaceLoop(self.env, *args, **kwargs)

    def add_volume(self, *args, **kwargs):
        return Volume(self.env, *args, **kwargs)

    def _new_physical_group(self, label=None):
        # See
        # https://github.com/nschloe/pygmsh/issues/46#issuecomment-286684321
        # for context.
        max_id = (
            0
            if not self._TAKEN_PHYSICALGROUP_IDS
            else max(self._TAKEN_PHYSICALGROUP_IDS)
        )

        if label is None:
            label = max_id + 1

        if isinstance(label, int):
            assert (
                label not in self._TAKEN_PHYSICALGROUP_IDS
            ), f"Physical group label {label} already taken."
            self._TAKEN_PHYSICALGROUP_IDS += [label]
            return str(label)

        assert isinstance(label, str)
        self._TAKEN_PHYSICALGROUP_IDS += [max_id + 1]
        return f'"{label}"'

    def add_physical(self, entities, label=None):
        if not isinstance(entities, list):
            entities = [entities]

        dim = entities[0].dimension
        for e in entities:
            assert e.dimension == dim

        label = self._new_physical_group(label)
        tag = gmsh.model.addPhysicalGroup(dim, [e._ID for e in entities])
        if label is not None:
            gmsh.model.setPhysicalName(dim, tag, label)

    def set_transfinite_curve(self, curve, num_nodes, mesh_type, coeff):
        assert mesh_type in ["Progression", "Bulk"]
        self._TRANSFINITE_CURVE_QUEUE.append((curve._ID, num_nodes, mesh_type, coeff))

    def set_transfinite_surface(self, surface, arrangement, corner_tags):
        self._TRANSFINITE_SURFACE_QUEUE.append((surface._ID, arrangement, corner_tags))

    def set_recombined_surfaces(self, surfaces):
        for i, surface in enumerate(surfaces):
            assert isinstance(
                surface, (PlaneSurface, Surface)
            ), f"item {i} is not a surface"
        self._RECOMBINE_ENTITIES += [s.dim_tags[0] for s in surfaces]

    def extrude(
        self,
        input_entity,
        translation_axis,
        num_layers=None,
        heights=None,
        recombine=False,
    ):
        """Extrusion of any entity along a given translation_axis."""
        if isinstance(num_layers, int):
            num_layers = [num_layers]
        if num_layers is None:
            num_layers = []
            heights = []
        else:
            if heights is None:
                heights = []
            else:
                assert len(num_layers) == len(heights)

        out_dim_tags = self.env.extrude(
            input_entity.dim_tags,
            translation_axis[0],
            translation_axis[1],
            translation_axis[2],
            numElements=num_layers,
            heights=heights,
            recombine=recombine,
        )
        top = Dummy(*out_dim_tags[0])
        extruded = Dummy(*out_dim_tags[1])
        lateral = [Dummy(*e) for e in out_dim_tags[2:]]
        return top, extruded, lateral

    def revolve(
        self,
        input_entity,
        rotation_axis,
        point_on_axis,
        angle,
        num_layers=None,
        heights=None,
        recombine=False,
    ):
        """Rotation of any entity around a given rotation_axis, about a given angle."""
        if isinstance(num_layers, int):
            num_layers = [num_layers]
        if num_layers is None:
            num_layers = []
            heights = []
        else:
            if heights is None:
                heights = []
            else:
                assert len(num_layers) == len(heights)

        assert angle < math.pi
        out_dim_tags = self.env.revolve(
            input_entity.dim_tags,
            *point_on_axis,
            *rotation_axis,
            angle,
            numElements=num_layers,
            heights=heights,
            recombine=recombine,
        )

        top = Dummy(*out_dim_tags[0])
        extruded = Dummy(*out_dim_tags[1])
        lateral = [Dummy(*e) for e in out_dim_tags[2:]]
        return top, extruded, lateral

    def twist(
        self,
        input_entity,
        translation_axis,
        rotation_axis,
        point_on_axis,
        angle,
        num_layers=None,
        heights=None,
        recombine=False,
    ):
        """Twist (translation + rotation) of any entity along a given translation_axis,
        around a given rotation_axis, about a given angle.
        """
        if isinstance(num_layers, int):
            num_layers = [num_layers]
        if num_layers is None:
            num_layers = []
            heights = []
        else:
            if heights is None:
                heights = []
            else:
                assert len(num_layers) == len(heights)

        assert angle < math.pi
        out_dim_tags = self.env.twist(
            input_entity.dim_tags,
            point_on_axis[0],
            point_on_axis[1],
            point_on_axis[2],
            translation_axis[0],
            translation_axis[1],
            translation_axis[2],
            rotation_axis[0],
            rotation_axis[1],
            rotation_axis[2],
            angle,
            numElements=num_layers,
            heights=heights,
            recombine=recombine,
        )
        top = Dummy(*out_dim_tags[0])
        extruded = Dummy(*out_dim_tags[1])
        lateral = [Dummy(*e) for e in out_dim_tags[2:]]
        return top, extruded, lateral

    def translate(self, obj, vector):
        """Translates input_entity itself by vector.

        Changes the input object.
        """
        self.env.translate(obj.dim_tags, *vector)

    def rotate(self, obj, point, angle, axis):
        """Rotate input_entity around a given point with a give angle.
           Rotation axis has to be specified.

        Changes the input object.
        """
        self.env.rotate(obj.dim_tags, *point, *axis, angle)

    def copy(self, obj):
        dim_tag = self.env.copy(obj.dim_tags)
        assert len(dim_tag) == 1
        return Dummy(*dim_tag[0])

    def symmetrize(self, obj, coefficients):
        """Transforms all elementary entities symmetrically to a plane. The vector
        should contain four expressions giving the coefficients of the plane's equation.
        """
        self.env.symmetrize(obj.dim_tags, *coefficients)

    def dilate(self, obj, x0, abc):
        self.env.dilate(obj.dim_tags, *x0, *abc)

    def mirror(self, obj, abcd):
        self.env.mirror(obj.dim_tags, *abcd)

    def in_surface(self, input_entity, surface):
        """Embed the point(s) or curve(s) in the given surface. The surface mesh will
        conform to the mesh of the point(s) or curves(s).
        """
        self._EMBED_QUEUE.append((input_entity, surface))

    def in_volume(self, input_entity, volume):
        """Embed the point(s)/curve(s)/surface(s) in the given volume. The volume mesh
        will conform to the mesh of the input entities.
        """
        self._EMBED_QUEUE.append((input_entity, volume))

    def add_polygon(self, X, mesh_size=None, holes=None, make_surface=True):
        class Polygon:
            def __init__(self, points, lines, curve_loop, surface, mesh_size=None):
                self.points = points
                self.lines = lines
                self.num_edges = len(lines)
                self.curve_loop = curve_loop
                self.surface = surface
                self.mesh_size = mesh_size
                if surface is not None:
                    self._ID = self.surface._ID
                self.dimension = 2
                self.dim_tags = [(2, surface)]

        if holes is None:
            holes = []
        else:
            assert make_surface

        if isinstance(mesh_size, list):
            assert len(X) == len(mesh_size)
        else:
            mesh_size = len(X) * [mesh_size]

        # Create points.
        p = [self.add_point(x, mesh_size=l) for x, l in zip(X, mesh_size)]
        # Create lines
        lines = [self.add_line(p[k], p[k + 1]) for k in range(len(p) - 1)]
        lines.append(self.add_line(p[-1], p[0]))
        ll = self.add_curve_loop(lines)
        surface = self.add_plane_surface(ll, holes) if make_surface else None
        return Polygon(p, lines, ll, surface, mesh_size=mesh_size)