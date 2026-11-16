"""Private host-local, single-session GUI gate for disposable Blender ModeLab only.
No RFB listener, OS input, raw Python dispatch, master writes, or unattended VNC.
Requires an exact source SHA; all operations carry a one-time session nonce.
"""
import bpy, bmesh, ctypes, hashlib, json, os, re, sys, time, uuid
from ctypes import wintypes
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from blender_controller.model_modes import ModeLab, validate
from blender_controller.gui_mode_policy import check_request, OUTPUT_NAME

ROOT = Path(os.environ["MODELAB_ROOT"]).resolve(strict=True)
SOURCE = ROOT / os.environ["MODELAB_SOURCE_NAME"]
EXPECTED_SHA = os.environ["MODELAB_SOURCE_SHA256"].lower()
GATE = ROOT / os.environ["MODELAB_GATE_NAME"]
MASTER = Path(os.environ["MODELAB_PROTECTED_MASTER"]).resolve(strict=True)
MASTER_SHA = os.environ["MODELAB_MASTER_SHA256"].lower()
TITLE_FRAGMENT = SOURCE.stem
POLL_LIMIT = 80
RUN_LIMIT_SECONDS = 240
def digest(p):
    h = hashlib.sha256()
    with p.open("rb") as s:
        while True:
            b = s.read(1048576)
            if not b: break
            h.update(b)
    return h.hexdigest()
assert ROOT.is_dir() and SOURCE.is_file()
assert re.fullmatch(r"Vera_ModeLab_[A-Za-z0-9_]{1,70}_RESEARCH_NOT_CANON\.blend",SOURCE.name)
assert re.fullmatch(r"gui-modelab-session-[a-z0-9_-]{1,36}",GATE.name)
assert SOURCE.parent == ROOT
assert GATE.parent == ROOT
assert re.fullmatch(r"[0-9a-f]{64}",EXPECTED_SHA)
assert re.fullmatch(r"[0-9a-f]{64}",MASTER_SHA)
assert GATE.is_dir() and not GATE.is_symlink()
assert not (GATE/"ready.json").exists() and not (GATE/"blocked.json").exists()
assert Path(bpy.data.filepath) == SOURCE, (bpy.data.filepath, str(SOURCE))
assert digest(SOURCE) == EXPECTED_SHA
assert digest(MASTER) == MASTER_SHA
assert bpy.context.scene["candidate_not_canon"] is True
assert bpy.context.scene["mode_lab_research"] is True
controller = ModeLab(bpy, bmesh)
session_id = uuid.uuid4().hex
start = time.monotonic()
handled = set()
count = 0
saved = False
done = False
bound_hwnd = [None]
last_integrity_check = [0.0]
def hwnd_for_pid():
    user = ctypes.WinDLL("user32", use_last_error=True)
    cbtype=ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    user.GetWindowThreadProcessId.argtypes=(wintypes.HWND,ctypes.POINTER(wintypes.DWORD))
    user.IsWindowVisible.argtypes=(wintypes.HWND,)
    user.GetWindowTextLengthW.argtypes=(wintypes.HWND,)
    user.GetWindowTextW.argtypes=(wintypes.HWND,wintypes.LPWSTR,ctypes.c_int)
    found=[]
    @cbtype
    def cb(h,_):
        pid=wintypes.DWORD()
        user.GetWindowThreadProcessId(h,ctypes.byref(pid))
        if pid.value != os.getpid() or not user.IsWindowVisible(h):return True
        n=user.GetWindowTextLengthW(h)
        if not 0<n<500:return True
        buf=ctypes.create_unicode_buffer(n+1)
        user.GetWindowTextW(h,buf,n+1)
        if TITLE_FRAGMENT in buf.value:found.append(int(h))
        return True
    user.EnumWindows(cb,0)
    return found[0] if len(found)==1 else None
def write_once(path,payload):
    with path.open("x",encoding="utf-8") as f:
        json.dump(payload,f,separators=(",",":"),sort_keys=True)
def guarded_action(request):
    global saved
    if digest(SOURCE)!=EXPECTED_SHA or digest(MASTER)!=MASTER_SHA:
        raise PermissionError("Source/master integrity lost")
    action=request["action"]
    args=request["args"]
    if action == "save_candidate":
        if saved:raise PermissionError("Session already saved")
        if args != {"output_name":OUTPUT_NAME}:
            raise PermissionError("Not approved output name")
        output=ROOT/args["output_name"]
        if output.exists() or output.is_symlink():raise FileExistsError("Output exists")
        if bpy.context.mode != "OBJECT": raise PermissionError("Must switch to Object Mode first")
        if digest(SOURCE) != EXPECTED_SHA or digest(MASTER) != MASTER_SHA:
            raise PermissionError("Source or master changed")
        bpy.context.scene["gui_mode_lab_research"] = True
        bpy.context.scene["gui_mode_lab_parent_sha256"] = EXPECTED_SHA
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(output),check_existing=False)
        if digest(SOURCE) != EXPECTED_SHA or digest(MASTER) != MASTER_SHA:
            raise RuntimeError("Source or master moved during save")
        saved=True
        return {"saved":True,"candidate":output.name,"sha256":digest(output)}
    validate(action,args)
    if saved:raise PermissionError("Session locked after save")
    if Path(bpy.data.filepath)!=SOURCE:raise PermissionError("Blender scene changed")
    return controller.apply(action,**args)
def poll():
    global count, done
    if done:return None
    if time.monotonic()-start > RUN_LIMIT_SECONDS:
        done=True;print("MODELAB_GUI_EXPIRED",flush=True);return None
    if bound_hwnd[0] is None or hwnd_for_pid()!=bound_hwnd[0]:
        done=True;print("MODELAB_GUI_WINDOW_BINDING_LOST",flush=True);return None
    now=time.monotonic()
    if now-last_integrity_check[0]>=1.0:
        last_integrity_check[0]=now
        if digest(MASTER)!=MASTER_SHA or digest(SOURCE)!=EXPECTED_SHA:
            done=True;print("MODELAB_GUI_SOURCE_DRIFT",flush=True);return None
    for request in sorted(GATE.glob("request_*.json"))[:2]:
        ident=request.stem.removeprefix("request_")
        if not re.fullmatch("[0-9a-f]{32}",ident):continue
        if ident in handled:continue
        inflight=GATE/("inflight_"+ident+".json")
        receipt=GATE/("response_"+ident+".json")
        if receipt.exists() or inflight.exists():continue
        try:request.rename(inflight)
        except OSError:continue
        handled.add(ident)
        count+=1
        result={"id":ident,"ok":False}
        try:
            req=json.loads(inflight.read_text(encoding="utf-8"))
            action,args=check_request(req,ident,session_id)
            result["result"]=guarded_action({"action":action,"args":args})
            result["ok"]=True
        except Exception as err:
            result["error"]=type(err).__name__
        try:write_once(receipt,result)
        except FileExistsError:pass
        print("MODELAB_GUI_EFFECT="+json.dumps({"id":ident,"action":req.get("action") if 'req' in locals() and type(req) is dict else None,"ok":result["ok"]},separators=(",",":")),flush=True)
        if saved or count>=POLL_LIMIT:
            done=True
            return None
    return 0.08
def interactive_session():
    sid=wintypes.DWORD()
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    if not kernel.ProcessIdToSessionId(os.getpid(),ctypes.byref(sid)):
        return False
    return sid.value!=0
def bootstrap():
    if not interactive_session():
        write_once(GATE/"blocked.json",{"reason":"session_not_interactive","pid":os.getpid()})
        print("MODELAB_GUI_BLOCKED=session_not_interactive",flush=True)
        return None
    window=hwnd_for_pid()
    if not window:
        if time.monotonic()-start>12:
            write_once(GATE/"blocked.json",{"reason":"no_verified_window","pid":os.getpid()})
            print("MODELAB_GUI_BLOCKED=no_verified_window",flush=True)
            return None
        return 0.3
    bound_hwnd[0]=window
    ready=GATE/"ready.json"
    write_once(ready,{"version":"mode-lab-gui-1","pid":os.getpid(),"hwnd":window,
        "source_sha256":EXPECTED_SHA,"session_id":session_id,
        "title_fragment":TITLE_FRAGMENT,"max_seconds":RUN_LIMIT_SECONDS,
        "allowed":["status","set_mode","select_vertices","edit_displace",
                   "sculpt_falloff","undo","save_candidate"],"remote_vnc":False})
    print("MODELAB_GUI_READY="+json.dumps({"pid":os.getpid(),"hwnd":window,
        "session_id":session_id},separators=(",",":")),flush=True)
    bpy.app.timers.register(poll,first_interval=0.05)
    return None
bpy.app.timers.register(bootstrap,first_interval=1.0)
