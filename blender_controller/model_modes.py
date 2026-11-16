"""Explicitly scoped Blender modeling operations for private ModeLab candidates.

No network, UI injection, arbitrary Python dispatch, file writes or canonical edits.
Native Edit/SCULPT mode switching is real. Sculpt falloff is a guarded mesh
deformation, NOT Blender's native brush-stroke operator (unqualified in headless).
"""
from __future__ import annotations
import math
from pathlib import Path
from collections import defaultdict

MODES = {"OBJECT": "OBJECT", "EDIT": "EDIT_MESH", "SCULPT": "SCULPT"}
OPS = {"status", "set_mode", "select_vertices", "edit_displace",
       "sculpt_falloff", "undo"}
MAX_EDIT_VERTS = 64
MAX_SCULPT_VERTS = 3500
MAX_TOTAL_VERTS = 25000
MAX_EDIT_DELTA_M = 0.025
MAX_SCULPT_DELTA_M = 0.035
MAX_CUMULATIVE_M = 0.10


def _vec(value, *, bound=4.0, name="vector"):
    if type(value) not in (list, tuple) or len(value) != 3:
        raise ValueError(f"{name} must be a 3-element vector")
    if any(type(x) not in (float, int) or type(x) is bool
           or not math.isfinite(x) or abs(x) > bound for x in value):
        raise ValueError(f"{name} out of bounds")
    return tuple(float(x) for x in value)


def _float(value, low, high, name):
    if type(value) not in (float, int) or type(value) is bool:
        raise ValueError(f"{name} must be numeric")
    if not math.isfinite(value) or not low <= value <= high:
        raise ValueError(f"{name} out of bounds")
    return float(value)


def validate(action, payload):
    """Reject extra keys before Blender-side effects."""
    keys = {
        "status": set(),
        "set_mode": {"mode"},
        "select_vertices": {"indices"},
        "edit_displace": {"delta"},
        "sculpt_falloff": {"center", "radius", "strength", "effect"},
        "undo": set(),
    }
    if action not in OPS or type(payload) is not dict or set(payload) != keys[action]:
        raise ValueError("Unrecognized modeling command or payload")
    if action == "set_mode":
        if type(payload["mode"]) is not str or payload["mode"] not in MODES:
            raise ValueError("Mode must be OBJECT, EDIT or SCULPT")
    elif action == "select_vertices":
        ids = payload["indices"]
        if (type(ids) not in (tuple, list) or not 1 <= len(ids) <= MAX_EDIT_VERTS
                or any(type(i) is not int or i < 0 for i in ids)
                or len(set(ids)) != len(ids)):
            raise ValueError("Invalid vertex selection")
    elif action == "edit_displace":
        d = _vec(payload["delta"], bound=MAX_EDIT_DELTA_M, name="delta")
        if math.sqrt(sum(q*q for q in d)) > MAX_EDIT_DELTA_M:
            raise ValueError("Edit step exceeds distance budget")
    elif action == "sculpt_falloff":
        _vec(payload["center"], name="center")
        _float(payload["radius"], .025, .80, "radius")
        _float(payload["strength"], -.035, .035, "strength")
        if payload["effect"] not in ("inflate", "smooth"):
            raise ValueError("Unsupported sculpt-like effect")
    return True


class ModeLab:
    def __init__(self, bpy_module, bmesh_module):
        self.bpy = bpy_module
        self.bmesh = bmesh_module
        self.baselines = {}
        self.undo_stack = []
        self.calls = 0

    def target(self):
        bpy = self.bpy
        scene = bpy.context.scene
        obj = bpy.context.view_layer.objects.active
        path = Path(bpy.data.filepath)
        if (scene is None or not scene.get("candidate_not_canon")
                or not scene.get("mode_lab_research")
                or not path.name.startswith("Vera_ModeLab_")
                or not path.name.endswith("_RESEARCH_NOT_CANON.blend")
                or obj is None or obj.type != "MESH"
                or not obj.name.startswith("Vera_ModeLab_")
                or not obj.get("mode_lab_research")
                or len(obj.data.vertices) > MAX_TOTAL_VERTS):
            raise PermissionError("Not an approved disposable ModeLab mesh")
        if obj.name not in self.baselines:
            # Created only on first authorized operation in current process.
            self.baselines[obj.name] = [tuple(v.co) for v in obj.data.vertices]
        return obj

    def apply(self, action, **kwargs):
        validate(action, kwargs)
        self.calls += 1
        if self.calls > 150:
            raise PermissionError("Modeling action budget exceeded")
        obj = self.target()
        bpy = self.bpy
        if action == "status":
            return {"mode": bpy.context.mode, "mesh": obj.name,
                    "vertices": len(obj.data.vertices),
                    "undo_depth": len(self.undo_stack),
                    "native_sculpt_brush_qualified": False}
        if action == "set_mode":
            target = kwargs["mode"]
            if bpy.context.mode != MODES[target]:
                bpy.ops.object.mode_set(mode="OBJECT")
                if target != "OBJECT":
                    bpy.ops.object.mode_set(mode=target)
            if bpy.context.mode != MODES[target]:
                raise RuntimeError("Blender refused mode")
            return {"mode": bpy.context.mode, "mesh": obj.name}
        if action == "select_vertices":
            if bpy.context.mode != "EDIT_MESH":
                raise PermissionError("Vertex selection requires Edit Mode")
            bm = self.bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            ids = kwargs["indices"]
            if any(i >= len(bm.verts) for i in ids):
                raise ValueError("Vertex index out of range")
            for v in bm.verts:
                v.select_set(False)
            for i in ids:
                bm.verts[i].select_set(True)
            self.bmesh.update_edit_mesh(obj.data, loop_triangles=False)
            return {"selected": list(ids), "mode": bpy.context.mode}
        if action == "edit_displace":
            if bpy.context.mode != "EDIT_MESH":
                raise PermissionError("Edit translation requires Edit Mode")
            bm = self.bmesh.from_edit_mesh(obj.data)
            bm.verts.ensure_lookup_table()
            selected = [v for v in bm.verts if v.select]
            if not 1 <= len(selected) <= MAX_EDIT_VERTS:
                raise ValueError("Select between 1 and 64 vertices")
            d = kwargs["delta"]
            prior = [(v.index, tuple(v.co)) for v in selected]
            from mathutils import Vector
            for v in selected:
                dest = v.co + Vector(d)
                origin = Vector(self.baselines[obj.name][v.index])
                if (dest-origin).length > MAX_CUMULATIVE_M:
                    raise PermissionError("Cumulative displacement budget")
            for v in selected: v.co += Vector(d)
            self.bmesh.update_edit_mesh(obj.data, loop_triangles=True)
            self.undo_stack.append((obj.name, prior))
            return {"moved_vertices": len(selected),
                    "delta": list(d), "mode": bpy.context.mode}
        if action == "sculpt_falloff":
            if bpy.context.mode != "SCULPT":
                raise PermissionError("Falloff requires Sculpt Mode")
            from mathutils import Vector
            center = Vector(kwargs["center"])
            radius = kwargs["radius"]
            strength = kwargs["strength"]
            effect = kwargs["effect"]
            old = [v.co.copy() for v in obj.data.vertices]
            positions = [v.co.copy() for v in obj.data.vertices]
            neighbors = defaultdict(set)
            if effect == "smooth":
                for edge in obj.data.edges:
                    u, v = edge.vertices
                    neighbors[u].add(v)
                    neighbors[v].add(u)
            moves = []
            for v in obj.data.vertices:
                r = (positions[v.index]-center).length
                if r >= radius: continue
                fall = (1-r/radius)**2
                if effect == "inflate":
                    outward = positions[v.index]-center
                    if outward.length < 1.e-8: continue
                    move = outward.normalized()*strength*fall
                else:
                    ns=neighbors[v.index]
                    if not ns:continue
                    mean=sum((positions[i] for i in ns), Vector((0,0,0)))/len(ns)
                    delta=mean-positions[v.index]
                    if delta.length < 1.e-8:continue
                    move=delta.normalized()*min(abs(strength),delta.length)*fall
                    if strength<0: move=-move
                origin = Vector(self.baselines[obj.name][v.index])
                if (positions[v.index]+move-origin).length > MAX_CUMULATIVE_M:
                    raise PermissionError("Cumulative displacement budget")
                moves.append((v.index,tuple(positions[v.index]),move))
            if not 1 <= len(moves) <= MAX_SCULPT_VERTS:
                raise ValueError("Affected vertex count outside allowed range")
            # Native headless sculpt.mesh_filter caused Blender access violation
            # in 5.2.1; use deterministic bounded object-data editing only.
            bpy.ops.object.mode_set(mode="OBJECT")
            try:
                for idx,_,displace in moves:
                    obj.data.vertices[idx].co += displace
                obj.data.update()
            finally:
                bpy.ops.object.mode_set(mode="SCULPT")
            self.undo_stack.append((obj.name,[(i,xyz) for i,xyz,_ in moves]))
            return {"affected_vertices":len(moves),"mode":bpy.context.mode,
                    "effect":effect,"native_brush":False}
        if action == "undo":
            if not self.undo_stack:
                return {"undone":False}
            name, previous=self.undo_stack[-1]
            if name!=obj.name:raise PermissionError("Undo object mismatch")
            was=bpy.context.mode
            bpy.ops.object.mode_set(mode="OBJECT")
            try:
                for idx,coords in previous:
                    obj.data.vertices[idx].co=coords
                obj.data.update()
            finally:
                if was=="EDIT_MESH":bpy.ops.object.mode_set(mode="EDIT")
                elif was=="SCULPT":bpy.ops.object.mode_set(mode="SCULPT")
            self.undo_stack.pop()
            return {"undone":True,"mode":bpy.context.mode,
                    "vertices_restored":len(previous)}
        raise ValueError("Unknown mode operation")
