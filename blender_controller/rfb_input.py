"""Allowlisted, GUI-scoped RFB control mapper; no OS input or arbitrary code."""
from __future__ import annotations
import json
import time
import uuid
from pathlib import Path

VIEW_W, VIEW_H = 960, 540

class BlenderInputBridge:
    def __init__(self, root, session, *, timeout=2.0):
        p = Path(root)
        if not p.is_absolute() or not p.is_dir() or p.is_symlink():
            raise PermissionError("Invalid GUI control directory")
        self.root = p.resolve(strict=True)
        self.session = session
        self.timeout = max(.25, min(float(timeout), 3.))
        self._validate()

    def _validate(self):
        ready = self.root/"ready.json"
        if not ready.is_file() or ready.is_symlink():
            raise PermissionError("No live Blender GUI controller")
        meta = json.loads(ready.read_text(encoding="utf8"))
        if (meta.get("version") != "private-gui-gate-2"
                or meta.get("pid") != self.session["pid"]
                or meta.get("hwnd") != self.session["handle"]):
            raise PermissionError("GUI controller identity changed")
        if meta.get("window_title_fragment") != "Vera_Selfimage_WorkingMaster_V7":
            raise PermissionError("Wrong experimental Blender scene")
        return meta

    def action(self, name, **kwargs):
        allowed = {"state", "orbit", "zoom", "pan", "frame", "view_axis",
                   "select_at", "transform_drag", "shape_delta", "undo"}
        if name not in allowed:
            raise ValueError("Action not allowlisted")
        self._validate()
        ident = uuid.uuid4().hex
        request = self.root/f"request_{ident}.json"
        receipt = self.root/f"response_{ident}.json"
        with request.open("x", encoding="utf8") as stream:
            json.dump({"id": ident, "action": name, **kwargs}, stream)
        deadline = time.monotonic()+self.timeout
        while time.monotonic()<deadline:
            if receipt.is_file():
                result = json.loads(receipt.read_text(encoding="utf8"))
                if result.get("id") != ident or not result.get("ok"):
                    raise RuntimeError("Blender rejected action")
                return result.get("result")
            time.sleep(.035)
        # Never automatically retry an ambiguously applied action.
        raise TimeoutError("Blender receipt pending")

class BlenderInputMapper:
    """MMB orbit, RMB pan, wheel zoom; LMB pick and G/R/S drag transforms.
    F frames, 1/3/7 orthographic views, B/H/J/N morph keys, Z undo.
    No text entry, file operations, OS hotkeys or clipboard."""
    def __init__(self, bridge):
        self.bridge = bridge
        self.buttons = 0
        self.point = (VIEW_W//2,VIEW_H//2)
        self.transform = None
        self.keys_down = set()
        self.events = 0
        self.left_anchor = None

    def _act(self, name, **kwargs):
        self.events += 1
        if self.events>650:
            raise ValueError("Control action budget exceeded")
        return self.bridge.action(name, **kwargs)

    def pointer(self, mask, x, y):
        if (type(x) is not int or type(y) is not int
                or not 0<=x<VIEW_W or not 0<=y<VIEW_H
                or type(mask) is not int or mask & ~31):
            raise ValueError("Malformed pointer event")
        old=self.buttons
        px,py=self.point
        dx,dy=x-px,y-py
        self.point=(x,y)
        self.buttons=mask&7
        if mask&8:
            return self._act("zoom",factor=.91)
        if mask&16:
            return self._act("zoom",factor=1.10)
        if mask&1 and not old&1:
            self.left_anchor=(x,y)
        if old&1 and not mask&1:
            anchor=self.left_anchor
            self.left_anchor=None
            if self.transform is None and anchor and abs(x-anchor[0])+abs(y-anchor[1])<15:
                return self._act("select_at",nx=x/VIEW_W,ny=y/VIEW_H)
            return None
        if abs(dx)>240 or abs(dy)>200 or (dx==0 and dy==0):
            return None
        if self.buttons&2:
            return self._act("orbit",yaw=max(-10.,min(10.,-dx*.22)),
                             pitch=max(-10.,min(10.,-dy*.20)))
        if self.buttons&4:
            return self._act("pan",x=max(-.09,min(.09,dx*.003)),
                             y=max(-.09,min(.09,-dy*.003)))
        if self.buttons&1 and self.transform:
            return self._act("transform_drag",mode=self.transform,
                             dx=max(-.09,min(.09,dx*.0018)),
                             dy=max(-.09,min(.09,-dy*.0018)))
        return None

    def key(self, down, keysym):
        if type(down) is not bool or type(keysym) is not int or not 0<=keysym<=0x10ffff:
            raise ValueError("Malformed key event")
        if not down:
            self.keys_down.discard(keysym)
            return None
        if keysym in self.keys_down:
            return None
        self.keys_down.add(keysym)
        if keysym==0xff1b:
            self.transform=None
        elif keysym in [ord(c) for c in "gGrRsS"]:
            self.transform=chr(keysym).lower()
        elif keysym in (ord("f"),ord("F"),0xff50):
            return self._act("frame")
        elif keysym in (ord("1"),0xffb1):
            return self._act("view_axis",axis="front")
        elif keysym in (ord("3"),0xffb3):
            return self._act("view_axis",axis="right")
        elif keysym in (ord("7"),0xffb7):
            return self._act("view_axis",axis="top")
        elif keysym in (ord("z"),ord("Z")):
            return self._act("undo")
        elif keysym in (0xffab,ord("+"),ord("=")):
            return self._act("zoom",factor=.92)
        elif keysym in (0xffad,ord("-")):
            return self._act("zoom",factor=1.09)
        elif keysym in (ord("b"),ord("B"),ord("j"),ord("J")):
            return self._act("shape_delta",shape="bust",
                             delta=.04 if chr(keysym).lower()=="b" else -.04)
        elif keysym in (ord("h"),ord("H"),ord("n"),ord("N")):
            return self._act("shape_delta",shape="hips",
                             delta=.04 if chr(keysym).lower()=="h" else -.04)
        return None
