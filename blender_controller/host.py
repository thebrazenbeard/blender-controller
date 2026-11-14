"""Host-neutral Blender session API, backed by separately qualified OS adapters.

Do not treat a host alias, IP, or session identifier as authorization.
Each controller instance can only see its own local desktop session.
"""
from __future__ import annotations
import sys

BACKEND_NAME = "windows-win32" if sys.platform == "win32" else "unsupported"


def capabilities() -> dict:
    return {
        "backend": BACKEND_NAME,
        "platform": sys.platform,
        "local_session_only": True,
        "view": sys.platform == "win32",
        "control": False,
        "remote_vnc": False,
        "network_listener": False,
        "unattended": False,
        "save": False,
    }


def _require_windows():
    if sys.platform != "win32":
        raise RuntimeError("No qualified Blender window backend for this OS")
    from . import windows
    return windows


def _hwnd(session_id: str) -> int:
    if not isinstance(session_id, str) or not session_id.startswith("win32:"):
        raise ValueError("Unsupported session ID")
    suffix = session_id[6:]
    if not suffix.isdecimal() or not suffix or len(suffix) > 20:
        raise ValueError("Invalid Win32 Blender window identifier")
    hwnd = int(suffix)
    if hwnd <= 0:
        raise ValueError("Invalid Blender window identifier")
    return hwnd


def list_sessions() -> list[dict]:
    win = _require_windows()
    return [{"session_id": f"win32:{w['hwnd']}", "pid": w["pid"], "title": w["title"]}
            for w in win.list_blender_windows()]


def resolve_session(session_id: str) -> dict:
    win = _require_windows()
    target = win.target_window(_hwnd(session_id))
    return {"session_id": f"win32:{target['hwnd']}", "pid": target["pid"],
            "title": target["title"], "handle": target["hwnd"]}


def request_local_consent(session: dict) -> bool:
    return _require_windows().attended_approval(
        {"hwnd": session["handle"], "pid": session["pid"], "title": session["title"]})


def capture(session: dict):
    return _require_windows().capture_png(session["handle"])
