# Security repair: Blender HWND capture leakage (2026-11-14)

## What was wrong

A real TigerVNC connection to the experimental 15909 viewer showed **Firefox/ChatGPT windows**, not the claimed Blender window. This directly falsified the previous capture-boundary claim. The old `PIL.ImageGrab.grab(window=hwnd)` implementation, with a genuine HWND of a running `blender.exe` process, returned pixels from the foreground browser when Blender was behind it. A correct HWND and process-title check were **not sufficient** to protect screen contents.

The old RFB/Tailscale route was immediately disabled, the exact server child process stopped, and the 15909 listener was verified absent. Unrelated private Tailscale routes and Funnel configuration were preserved.

## Repair

`blender_controller.win_capture.capture_window_image` uses Windows `PrintWindow(hwnd, HDC, PW_RENDERFULLCONTENT)` into an offscreen compatible bitmap followed by `GetDIBits`. There is **no fallback** to a desktop grab, monitor rectangle, Pillow ImageGrab, or a different window. The caller `windows.capture_png` verifies the target HWND belongs to a visible `blender.exe` process **before and after** capture, rejects process replacement or invalid dimensions, and caps PNG payload size. The Win32 backend requires a visible, non-minimized window and fails closed on capture errors.

## Grounded evidence

On the first verified Windows test host, the validated Blender 5.2.1 window was independently bound to its live process. The read-only comparison while Firefox was foreground showed:
- PIL window grab: 1920 × 1009, **the unrelated browser** (privacy failure).
- PrintWindow: 1936 × 1048, **Blender's original V25 viewport** (correct target).
- Fixed `windows.capture_png` re-test with a different foreground HWND: 1936 × 1048 Blender PNG, strict non-Blender HWND rejection and 960 × 540, 2,073,600-byte VNC pixel buffer.
- The private screenshots stay in an isolated host experiment folder; none is committed or uploaded to this public repository.

Unit regression tests cover fail-closed target validation, rejected HWND/PID reuse, fixed image encoding and no Pillow desktop fallback. These are **local tests**, not an independent hostile review or complete compositor/window-overlap security certification.

## Separate input frontier

Windows refused the supervised attempt to foreground the Blender window, so **no global mouse action was delivered**. Background-scoped WM_MBUTTON messages were accepted into the Blender window queue but caused no meaningful viewport orbit (under 0.02% viewport pixel change). Neither route qualifies actual interactive Blender UI control. The private RFB server remains view-only; the Codex-local plugin and Vera Blender Studio's guarded candidate-edit MCP are distinct capabilities. Do not claim ChatGPT can take over the desktop, click or drag Blender, or edit the canonical master from VNC.

The 15909 tailnet route may be restored only with the corrected source loaded, 21+ passing tests, a verified Blender-only frame and explicit local attended consent. This repair does not authorize public Funnel, arbitrary desktop input, cloud screen publication, or source merges.
