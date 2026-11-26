"""Blender process entry for pinned, private ModeLab candidate operations.

Usage (host-executor only):
 blender -b Vera_ModeLab_Source_RESEARCH_NOT_CANON.blend --disable-autoexec \
 --python model_modes_batch_blender.py -- --request req.json
Never run this script on or name outputs after the protected Selfimage master.
"""
import bpy, bmesh, json, hashlib, re, sys, os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from blender_controller.model_modes import ModeLab

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    argv=sys.argv
    if "--" not in argv:
        raise ValueError("Missing explicit request")
    extra=argv[argv.index("--")+1:]
    if len(extra)!=2 or extra[0]!="--request":
        raise ValueError("Only --request <json> allowed")
    req=Path(extra[1])
    root=req.parent.resolve(strict=True)
    if not req.is_file() or req.is_symlink():
        raise PermissionError("Request must be a regular local file")
    data=json.loads(req.read_text(encoding="utf-8"))
    if (type(data) is not dict or set(data)!=
        {"schema","source_sha256","output_name","actions"}):
        raise ValueError("Invalid batch schema")
    if data["schema"]!="blender_controller_candidate_modes_v1":
        raise ValueError("Unknown command grammar")
    if not re.fullmatch(r"[0-9a-f]{64}",data["source_sha256"]):
        raise ValueError("Invalid source hash")
    name=data["output_name"]
    if (type(name) is not str or
        not re.fullmatch(r"Vera_ModeLab_[A-Za-z0-9_]{1,70}_RESEARCH_NOT_CANON\.blend",name)):
        raise ValueError("Output not an isolated Modelab candidate filename")
    source=Path(bpy.data.filepath)
    if (not source.is_file() or source.is_symlink()
        or source.parent.resolve(strict=True)!=root):
        raise PermissionError("Blender source does not match request directory")
    if sha(source)!=data["source_sha256"]:
        raise PermissionError("Source digest mismatch")
    actions=data["actions"]
    if type(actions) is not list or not 1<=len(actions)<=20:
        raise ValueError("Invalid bounded action batch")
    target=root/name
    if target.exists() or target.is_symlink():
        raise FileExistsError("Candidate already exists")
    bpy.context.preferences.filepaths.use_scripts_auto_execute=False
    modeling=ModeLab(bpy,bmesh)
    results=[]
    for step in actions:
        if type(step) is not dict or set(step)!={"action","args"}:
            raise ValueError("Invalid action step")
        result=modeling.apply(step["action"],**step["args"])
        results.append({"action":step["action"],"result":result})
    if bpy.context.mode!="OBJECT":
        modeling.apply("set_mode",mode="OBJECT")
    assert sha(source)==data["source_sha256"]
    bpy.context.scene["candidate_not_canon"]=True
    bpy.context.scene["mode_lab_research"]=True
    bpy.context.scene["mode_lab_parent_sha256"]=data["source_sha256"]
    bpy.context.preferences.filepaths.save_version=0
    assert {"FINISHED"}==bpy.ops.wm.save_as_mainfile(filepath=str(target),check_existing=False)
    assert sha(source)==data["source_sha256"]
    response={"output":target.name,"output_sha256":sha(target),
              "source_sha256":data["source_sha256"],"actions":results,
              "model_lab_candidate_only":True,"native_sculpt_brush":False}
    print("MODELAB_BATCH_VERIFIED="+json.dumps(response,separators=(",",":")),flush=True)

if __name__=="__main__":
    main()
