"""Windows Blender-window capture. Never captures an arbitrary desktop rectangle."""
from __future__ import annotations
import ctypes
import io
import os
import sys
from ctypes import wintypes

MAX_FRAME_WIDTH = 2400
MAX_FRAME_HEIGHT = 1800
MAX_PNG_BYTES = 4_000_000


def _api():
    if sys.platform != "win32":
        raise RuntimeError("Windows-only host; no alternate desktop fallback")
    return ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)


def _exe_name(kernel, pid):
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    kernel.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        buf = ctypes.create_unicode_buffer(32768)
        count = wintypes.DWORD(len(buf))
        if not kernel.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(count)):
            return None
        return os.path.basename(buf.value).lower()
    finally:
        kernel.CloseHandle(handle)


def list_blender_windows():
    user, kernel = _api()
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = (callback_type, wintypes.LPARAM)
    user.EnumWindows.restype = wintypes.BOOL
    user.GetWindowThreadProcessId.argtypes = (wintypes.HWND, ctypes.POINTER(wintypes.DWORD))
    user.GetWindowThreadProcessId.restype = wintypes.DWORD
    user.GetWindowTextLengthW.argtypes = (wintypes.HWND,)
    user.GetWindowTextLengthW.restype = ctypes.c_int
    user.GetWindowTextW.argtypes = (wintypes.HWND, wintypes.LPWSTR, ctypes.c_int)
    user.GetWindowTextW.restype = ctypes.c_int
    user.IsWindowVisible.argtypes = (wintypes.HWND,)
    user.IsWindowVisible.restype = wintypes.BOOL
    result = []

    @callback_type
    def visit(hwnd, _):
        if not user.IsWindowVisible(hwnd):
            return True
        n = user.GetWindowTextLengthW(hwnd)
        if n <= 0 or n > 1024:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        user.GetWindowTextW(hwnd, buf, n + 1)
        if not buf.value:
            return True
        pid = wintypes.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value and _exe_name(kernel, pid.value) == "blender.exe":
            result.append({"hwnd": int(hwnd), "pid": int(pid.value), "title": buf.value[:160]})
        return True

    if not user.EnumWindows(visit, 0):
        raise RuntimeError("Blender window enumeration failed")
    return result


def target_window(hwnd):
    if isinstance(hwnd, bool) or not isinstance(hwnd, int):
        raise ValueError("Window handle must be an integer")
    match = next((w for w in list_blender_windows() if w["hwnd"] == hwnd), None)
    if match is None:
        raise PermissionError("Blender window not found or executable identity changed")
    return match


def attended_approval(window):
    user, _ = _api()
    user.MessageBoxW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
    user.MessageBoxW.restype = ctypes.c_int
    caption = "Vera Blender Controller - local approval"
    message = ("Allow this controller to VIEW pixels from Blender only for up to 2 minutes?\n"
               "No keyboard, mouse, desktop, clipboard, recording, or file privileges.\n\n"
               f"Blender process: {window['pid']}\n"
               "Deny unless this request was expected. You can disconnect via the controller.")
    result = user.MessageBoxW(None, message, caption, 0x00000004 | 0x00000020 | 0x00040000)
    return result == 6  # IDYES; denial and dismissal fail closed


def capture_png(hwnd):
    target_window(hwnd)  # recheck real executable + window before capture
    from PIL import ImageGrab
    im = ImageGrab.grab(window=hwnd)
    if not im or im.width < 1 or im.height < 1:
        raise RuntimeError("No Blender window pixels available")
    if im.width > MAX_FRAME_WIDTH or im.height > MAX_FRAME_HEIGHT:
        raise RuntimeError("Blender window exceeds bounded frame dimensions")
    output = io.BytesIO()
    im.convert("RGB").save(output, format="PNG")
    if output.tell() > MAX_PNG_BYTES:
        raise RuntimeError("Blender window frame exceeds payload limit")
    return output.getvalue(), (im.width, im.height)
