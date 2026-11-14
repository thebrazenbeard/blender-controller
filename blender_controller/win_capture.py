"""Strict Win32 PrintWindow framebuffer. Never captures the foreground desktop.

Pillow ImageGrab.grab(window=hwnd) has been observed returning an occluding
Firefox window on Lappy even when hwnd names blender.exe. Do not use it.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from PIL import Image

MAX_WIDTH = 2400
MAX_HEIGHT = 1800


class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER),
                ("bmiColors", wintypes.DWORD * 3)]


def capture_window_image(hwnd: int) -> Image.Image:
    """Print the verified Blender HWND into an off-screen bitmap.

    Caller MUST first call windows.target_window(hwnd), which binds the
    HWND to a live blender.exe process. No fallback to desktop rectangles.
    """
    if sys.platform != "win32":
        raise RuntimeError("No qualified Win32 capture backend")
    if isinstance(hwnd, bool) or not isinstance(hwnd, int) or hwnd <= 0:
        raise ValueError("Invalid Blender window handle")
    user = ctypes.WinDLL("user32", use_last_error=True)
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    user.IsWindowVisible.argtypes = (wintypes.HWND,)
    user.IsWindowVisible.restype = wintypes.BOOL
    user.IsIconic.argtypes = (wintypes.HWND,)
    user.IsIconic.restype = wintypes.BOOL
    user.GetWindowRect.argtypes = (wintypes.HWND, ctypes.POINTER(_RECT))
    user.GetWindowRect.restype = wintypes.BOOL
    user.GetWindowDC.argtypes = (wintypes.HWND,)
    user.GetWindowDC.restype = wintypes.HDC
    user.ReleaseDC.argtypes = (wintypes.HWND, wintypes.HDC)
    gdi.CreateCompatibleDC.argtypes = (wintypes.HDC,)
    gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateCompatibleBitmap.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int)
    gdi.CreateCompatibleBitmap.restype = wintypes.HANDLE
    gdi.SelectObject.argtypes = (wintypes.HDC, wintypes.HANDLE)
    gdi.SelectObject.restype = wintypes.HANDLE
    gdi.GetDIBits.argtypes = (wintypes.HDC, wintypes.HANDLE, wintypes.UINT,
                            wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p,
                            wintypes.UINT)
    gdi.GetDIBits.restype = ctypes.c_int
    user.PrintWindow.argtypes = (wintypes.HWND, wintypes.HDC, wintypes.UINT)
    user.PrintWindow.restype = wintypes.BOOL
    gdi.DeleteObject.argtypes = (wintypes.HANDLE,)
    gdi.DeleteDC.argtypes = (wintypes.HDC,)

    if not user.IsWindowVisible(hwnd) or user.IsIconic(hwnd):
        raise RuntimeError("Blender must be visible and not minimized")
    rect = _RECT()
    if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("Cannot inspect Blender window bounds")
    width, height = rect.right - rect.left, rect.bottom - rect.top
    if not (1 <= width <= MAX_WIDTH and 1 <= height <= MAX_HEIGHT):
        raise RuntimeError("Blender window exceeds bounded frame size")
    dc = user.GetWindowDC(hwnd)
    if not dc:
        raise RuntimeError("Blender window device context unavailable")
    mem = None
    bmp = None
    old = None
    try:
        mem = gdi.CreateCompatibleDC(dc)
        if not mem:
            raise RuntimeError("Cannot allocate off-screen device context")
        bmp = gdi.CreateCompatibleBitmap(dc, width, height)
        if not bmp:
            raise RuntimeError("Cannot allocate off-screen bitmap")
        old = gdi.SelectObject(mem, bmp)
        if not old:
            raise RuntimeError("Cannot select off-screen bitmap")
        if not user.PrintWindow(hwnd, mem, 2):  # PW_RENDERFULLCONTENT
            raise RuntimeError("Blender PrintWindow failed; no desktop fallback")
        info = _BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # top-down bitmap
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        buffer = ctypes.create_string_buffer(width * height * 4)
        lines = gdi.GetDIBits(mem, bmp, 0, height, buffer,
                             ctypes.byref(info), 0)
        if lines != height:
            raise RuntimeError("Blender capture has incomplete bitmap lines")
        result = Image.frombytes("RGB", (width, height),
                                 buffer.raw, "raw", "BGRX")
        return result
    finally:
        if old and mem:
            gdi.SelectObject(mem, old)
        if bmp:
            gdi.DeleteObject(bmp)
        if mem:
            gdi.DeleteDC(mem)
        user.ReleaseDC(hwnd, dc)
