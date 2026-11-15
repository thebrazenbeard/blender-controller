"""Attended, loopback-only RFB 3.8 framebuffer for one Blender window.

Experimental: 960x540 raw frames; scoped interactivity requires separate local consent.
Never binds to a public or tailnet interface; optional Tailscale Serve handles
private transport. Every connection requires the current local user's consent.
"""
from __future__ import annotations
import argparse
import ctypes
import io
import json
import socket
import socketserver
import struct
import sys
import time
from ctypes import wintypes

from . import host

FRAME_WIDTH = 960
FRAME_HEIGHT = 540
DEFAULT_PORT = 15909
MAX_SESSION_SECONDS = 120
MAX_FRAME_REQUESTS = 150
PIXEL_FORMAT = struct.pack(">BBBBHHHBBBxxx", 32, 24, 0, 1, 255, 255, 255, 16, 8, 0)
NAME = b"Attended Blender Window - View Only"
CONTROL_NAME = b"Attended Blender - Scoped Interactive"
CONTROL_SESSION_SECONDS = 600
CONTROL_FRAME_REQUESTS = 1100
RFB_VERSION = b"RFB 003.008\n"


def receive_exact(sock, size):
    if size < 0 or size > 4096:
        raise ValueError("Unbounded network request")
    parts = bytearray()
    while len(parts) < size:
        block = sock.recv(size - len(parts))
        if not block:
            raise ConnectionError("Peer disconnected")
        parts.extend(block)
    return bytes(parts)


def operator_consents(session):
    """Time-bounded host-local consent; unsupported prompts fail closed."""
    if sys.platform != "win32":
        return False
    user = ctypes.WinDLL("user32", use_last_error=True)
    try:
        prompt = user.MessageBoxTimeoutW
    except AttributeError:
        return False
    prompt.argtypes = (
        wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
        wintypes.UINT, wintypes.WORD, wintypes.DWORD)
    prompt.restype = ctypes.c_int
    message = (
        "Share pixels from the selected Blender window via VNC for up to 2 minutes?\n"
        "Only a VIEW stream; mouse, keyboard, clipboard and files stay disabled.\n"
        "This is for an authenticated PRIVATE tailnet session, never public internet.\n"
        f"Blender PID: {session['pid']}\n\n"
        "Deny unexpected requests.")
    # MB_YESNO | MB_ICONWARNING | MB_SETFOREGROUND, 20 second deadline.
    return prompt(None, message, "Vera Blender VNC - Host Approval",
                  0x0004 | 0x0030 | 0x10000, 0, 20000) == 6


def operator_consents_control(session):
    """Explicit host-local consent to a scoped, interactive Blender session."""
    if sys.platform != "win32":
        return False
    user = ctypes.WinDLL("user32", use_last_error=True)
    try:
        prompt = user.MessageBoxTimeoutW
    except AttributeError:
        return False
    prompt.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR,
                       wintypes.UINT, wintypes.WORD, wintypes.DWORD)
    prompt.restype = ctypes.c_int
    message = (
        "Allow a PRIVATE VNC viewer to CONTROL only the currently selected "
        "Blender candidate for up to 10 minutes?\n\n"
        "Allowed: Blender orbit, pan, zoom, object selection, bounded "
        "candidate edits and shape-key changes.\n"
        "NOT allowed: OS desktop control, arbitrary typing, shell execution, "
        "clipboard, files or destructive edits.\n\n"
        f"Blender PID: {session['pid']}\n"
        "The viewer can disconnect and this grant will immediately expire.\n"
        "Deny unexpected requests.")
    return prompt(None, message, "Vera Blender Scoped VNC - LOCAL CONTROL APPROVAL",
                  0x0004 | 0x0030 | 0x10000, 0, 20000) == 6


def frame_pixels(session, width=FRAME_WIDTH, height=FRAME_HEIGHT):
    """Fresh real Blender-window capture; avoids unrelated desktop fallback."""
    from PIL import Image, ImageOps
    current = host.resolve_session(session["session_id"])
    if current["pid"] != session["pid"] or current["handle"] != session["handle"]:
        raise PermissionError("Blender window process changed")
    png, _size = host.capture(current)
    source = Image.open(io.BytesIO(png)).convert("RGB")
    fitted = ImageOps.contain(source, (width, height), method=Image.Resampling.BILINEAR)
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    canvas.paste(fitted, ((width-fitted.width)//2, (height-fitted.height)//2))
    return canvas.tobytes("raw", "BGRX")
class BlenderRFB(socketserver.TCPServer):
    allow_reuse_address = False
    request_queue_size = 2

    def __init__(self, port, session_id, *, consent=operator_consents,
                 grab=frame_pixels, control_root=None,
                 control_consent=operator_consents_control):
        if not (0 <= int(port) <= 65535):  # port 0 permits OS-assigned loopback test ports
            raise ValueError("Port out of range")
        self.session_id = session_id
        self.consent = consent
        self.grab = grab
        self.control_root = control_root
        self.control_consent = control_consent
        self.last_connection = 0.0
        # Unmodifiable loopback binding: even a malicious CLI argument cannot
        # expose the unauthenticated (before-host-consent) RFB handshake.
        super().__init__(("127.0.0.1", int(port)), BlenderRFBHandler)

    def verify_request(self, request, client_address):
        if client_address[0] != "127.0.0.1":
            return False
        return super().verify_request(request, client_address)


class BlenderRFBHandler(socketserver.BaseRequestHandler):
    def handle(self):
        sock = self.request
        sock.settimeout(15)
        try:
            self._serve(sock)
        except (OSError, ConnectionError, ValueError, PermissionError,
                TimeoutError, RuntimeError, KeyError, json.JSONDecodeError):
            return

    def _serve(self, sock):
        session = host.resolve_session(self.server.session_id)
        sock.sendall(RFB_VERSION)
        version = receive_exact(sock, 12)
        if version != RFB_VERSION:
            return  # deliberately only RFB 3.8, no silent downgrade
        sock.sendall(b"\x01\x01")  # One RFB security choice: None, only after host consent
        if receive_exact(sock, 1) != b"\x01":
            return
        requires_control = self.server.control_root is not None
        approval = self.server.control_consent if requires_control else self.server.consent
        if not approval(session):
            reason = b"Denied by Blender host operator"
            sock.sendall(struct.pack(">II", 1, len(reason)) + reason)
            return
        fresh = host.resolve_session(self.server.session_id)
        if (fresh["pid"], fresh["handle"]) != (session["pid"], session["handle"]):
            return
        sock.sendall(struct.pack(">I", 0))
        receive_exact(sock, 1)  # ClientInit Shared flag, ignored: server is one-client
        if requires_control:
            from .rfb_input import BlenderInputBridge, BlenderInputMapper
            bridge = BlenderInputBridge(self.server.control_root, fresh)
            mapper = BlenderInputMapper(bridge)
            name = CONTROL_NAME
        else:
            mapper = None
            name = NAME
        sock.sendall(struct.pack(">HH", FRAME_WIDTH, FRAME_HEIGHT) +
                     PIXEL_FORMAT + struct.pack(">I", len(name)) + name)
        started = time.monotonic()
        last_frame = -100.0
        sent_frames = 0
        sock.settimeout(6)
        session_limit = CONTROL_SESSION_SECONDS if requires_control else MAX_SESSION_SECONDS
        frame_limit = CONTROL_FRAME_REQUESTS if requires_control else MAX_FRAME_REQUESTS
        while time.monotonic() - started < session_limit:
            kind = receive_exact(sock, 1)[0]
            if kind == 0:  # SetPixelFormat
                packet = receive_exact(sock, 19)
                if packet[3:] != PIXEL_FORMAT:
                    return
            elif kind == 2:  # SetEncodings
                pkt = receive_exact(sock, 3)
                count = struct.unpack(">H", pkt[1:])[0]
                if count > 128:
                    return
                for _ in range(count):
                    receive_exact(sock, 4)
            elif kind == 3:  # FramebufferUpdateRequest
                receive_exact(sock, 9)
                if sent_frames >= frame_limit:
                    return
                now = time.monotonic()
                if now - last_frame < 0.5:
                    time.sleep(0.5 - (now - last_frame))
                last_frame = time.monotonic()
                pixels = self.server.grab(session)
                if len(pixels) != FRAME_WIDTH * FRAME_HEIGHT * 4:
                    return
                header = struct.pack(">BBH", 0, 0, 1)
                rectangle = struct.pack(">HHHHi", 0, 0, FRAME_WIDTH, FRAME_HEIGHT, 0)
                sock.sendall(header + rectangle + pixels)
                sent_frames += 1
            elif kind == 4:  # KeyEvent: only Blender-scoped allowlisted bindings
                data = receive_exact(sock, 7)
                if mapper is not None:
                    mapper.key(bool(data[0]), struct.unpack(">I", data[3:])[0])
            elif kind == 5:  # PointerEvent: only Blender-scoped navigation/edit
                data = receive_exact(sock, 5)
                if mapper is not None:
                    mask, x, y = struct.unpack(">BHH", data)
                    mapper.pointer(mask, x, y)
            elif kind == 6:  # ClientCutText: discard, never copy to clipboard
                packet = receive_exact(sock, 7)
                length = struct.unpack(">I", packet[3:])[0]
                if length > 4096:
                    return
                receive_exact(sock, length)
            else:
                return

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", required=True,
                        help="Local Blender session returned by list_blender_sessions")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--control-root", default=None,
                        help="Host-selected, local-only bounded Blender GUI gate; "
                             "requires distinct local control consent")
    args = parser.parse_args(argv)
    session = host.resolve_session(args.session_id)
    with BlenderRFB(args.port, session["session_id"],
                    control_root=args.control_root) as server:
        # This startup output is metadata only. Never log images or tokens.
        print(f"RFB_READY loopback=127.0.0.1 port={args.port} "
              f"pid={session['pid']} view_only={args.control_root is None} "
              f"scoped_blender_control={args.control_root is not None} "
              "consent=required", flush=True)
        server.serve_forever(poll_interval=0.25)


if __name__ == "__main__":
    main()
