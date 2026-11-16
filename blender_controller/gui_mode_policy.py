"""Pure host-local mode-lab GUI request policy. No Blender or OS input."""
from __future__ import annotations
import re
from .model_modes import validate

OPERATIONS=frozenset(("status","set_mode","select_vertices","edit_displace",
    "sculpt_falloff","undo","save_candidate"))
OUTPUT_NAME="Vera_ModeLab_GUI_InteractiveTrial_RESEARCH_NOT_CANON.blend"

def check_request(request, request_id, session_id):
    if (type(request) is not dict
            or set(request)!={"id","session","action","args"}
            or type(request["id"]) is not str
            or not re.fullmatch(r"[0-9a-f]{32}",request["id"])
            or request["id"]!=request_id
            or type(request["session"]) is not str
            or request["session"]!=session_id
            or type(request["args"]) is not dict):
        raise ValueError("Bad request schema or session")
    action=request["action"]
    if type(action) is not str or action not in OPERATIONS:
        raise ValueError("Unapproved Blender GUI mode action")
    args=request["args"]
    if action=="save_candidate":
        if args!={"output_name":OUTPUT_NAME}:
            raise ValueError("Unapproved output destination")
    else:
        validate(action,args)
    return action,args

def require_window_binding(meta,pid,hwnd,source_hash):
    """Enforce an observed GUI rather than stale ready.json or session 0."""
    if (type(meta) is not dict
            or not {"version","pid","hwnd","session_id","source_sha256"}.issubset(meta)
            or meta["version"]!="mode-lab-gui-1"
            or type(pid) is not int or type(hwnd) is not int
            or pid<=0 or hwnd<=0
            or meta["pid"]!=pid or meta["hwnd"]!=hwnd
            or meta["source_sha256"]!=source_hash
            or type(meta["session_id"]) is not str
            or not re.fullmatch(r"[0-9a-f]{32}",meta["session_id"])):
        raise PermissionError("Unverified GUI window/source binding")
    return True
