"""Independent Blender reopen/geometry QA for two private ModeLab candidates.

Example:
 blender -b --disable-autoexec --python tests/qa_model_modes_reopen.py -- \
   --source <absolute-source.blend> --candidate <absolute-candidate.blend> \
   --source-sha <64hex> --candidate-sha <64hex>
No save, network, Blender GUI, or canonical path inference.
"""
import bpy, hashlib, json, re, sys
from pathlib import Path
from mathutils import Vector
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
assert len(args)==8
def flag(n):return args[args.index(n)+1]
source=Path(flag("--source"))
candidate=Path(flag("--candidate"))
s_sha=flag("--source-sha");c_sha=flag("--candidate-sha")
assert re.fullmatch("[a-f0-9]{64}",s_sha)
assert re.fullmatch("[a-f0-9]{64}",c_sha)
assert source.is_file() and candidate.is_file()
assert source.parent.resolve()==candidate.parent.resolve()
assert sha(source)==s_sha and sha(candidate)==c_sha
def inspect(path):
    bpy.context.preferences.filepaths.use_scripts_auto_execute=False
    bpy.ops.wm.open_mainfile(filepath=str(path),load_ui=False)
    assert bpy.context.scene.get("mode_lab_research") is True
    assert bpy.context.scene.get("candidate_not_canon") is True
    ob=bpy.data.objects.get("Vera_ModeLab_Disposable")
    assert ob and ob.type=="MESH" and ob.get("mode_lab_research") is True
    return {"verts":[tuple(v.co) for v in ob.data.vertices],
            "faces":[tuple(poly.vertices) for poly in ob.data.polygons],
            "edges":len(ob.data.edges),
            "name":ob.name}
a=inspect(source);b=inspect(candidate)
assert len(a["verts"])==len(b["verts"])
assert a["faces"]==b["faces"] and a["edges"]==b["edges"]
maxd=max((Vector(v)-Vector(w)).length for v,w in zip(a["verts"],b["verts"]))
num=sum((Vector(v)-Vector(w)).length>1e-6 for v,w in zip(a["verts"],b["verts"]))
assert 0<num<=3500 and 0<maxd<.1
assert sha(source)==s_sha and sha(candidate)==c_sha
print("MODELAB_REOPEN_PASS="+json.dumps({
 "source_sha256":s_sha,"candidate_sha256":c_sha,
 "vertices":len(b["verts"]),"faces":len(b["faces"]),
 "changed_vertices":num,"max_vertex_delta_m":round(maxd,6),
 "source_unchanged":True,"candidate_not_canon":True},separators=(",",":")),flush=True)
