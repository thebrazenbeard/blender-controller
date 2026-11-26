# Candidate-only GUI ModeLab gate — isolated research

Status: source-only experimental GUI gate. NOT deployed to live Blender Controller, installed as a new ChatGPT MCP tool, or qualified for VNC/RFB input. This is stacked on the tested Edit/Sculpt batch-mode Draft PR #2.

## Scope and design

The generic Blender 5.2.1 module blender_controller/model_modes_gui_gate_v2.py accepts an explicitly verified disposable Vera_ModeLab_*_RESEARCH_NOT_CANON.blend file. Authorized local host configuration supplies candidate root, exact file SHA-256, fresh gate directory, and protected master path/SHA-256. Source contains no private host paths.

The gate refuses Windows Session 0 and unverified/ambiguous GUI windows; it must see one Blender window matching the running process and research candidate title. When verified, it binds PID, window handle, source SHA and a per-session nonce in a new local ready receipt. Only strict single-use JSON requests, checked by gui_mode_policy.py, can trigger candidate-only status, Object/Edit/Sculpt mode switching, vertex selection/translation, bounded sculpt-like falloff, undo or one approved new disposable save. It never enables arbitrary Python, OS input, clipboard, public VNC or original master modification. After successful save it locks further effects. Session lifetime is bounded at 240 seconds and 80 actions.

## Actual test evidence, Lappy on 2026-11-16

The source compiled. The complete controller Python suite passed 37 tests, including 5 new tests covering forged sessions, stale/replayed IDs, malformed actions, path escape/saves, and invalid window bindings.

A fresh Blender 5.2.1 GUI launch through the current remote host executor landed in Windows Session 0. The gate correctly wrote blocked.json with reason=session_not_interactive and created NO ready.json. It therefore denied all interactive editing. The isolated process was stopped after confirming its command, process ID and Session 0 identity. The separately running user Blender process and the protected Selfimage master were left untouched. The master SHA-256 was rechecked unchanged.

> Hostile review: Successful denial of Session 0 is security evidence, not evidence of successful live GUI modeling. No interactive user-window control, native Sculpt brush, GUI vertex edit, host-local VNC consent or GUI candidate save is qualified. A previous headless native sculpt.mesh_filter crashed in Blender 5.2.1; it remains excluded.

## Next qualifying test

Use a genuine separately authorized interactive desktop session, disposable verified source candidate, matching Blender HWND/PID and source hash. Observe ready receipt, run each guarded operation with exact effect receipt, save a NEW research candidate and independently reopen/check SHA/geometry. Preserve host-local VNC consent boundaries and never reuse historical V7 session data. Do not merge or install before evidence supports it.

The currently installed private plugin v0.1.1 supports the separately verified authenticated host-backed Edit/Sculpt batch path, NOT this unqualified GUI route.
