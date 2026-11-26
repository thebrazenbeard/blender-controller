# Scoped Blender Edit and Sculpt ModeLab

Status: private source candidate, NOT live controller installation or canonical Selfimage editing.

The controller previously exposed navigation, object transforms and shape keys through a guarded V7 GUI gate, not mesh Edit Mode or native Sculpt Mode controls. This new candidate-only module allows actual Blender 5.2.1 mode switching, vertex selection/translation and bounded sculpt-like mesh falloff on disposable model files, with JSON schema and SHA guards. It does not change the running V7 GUI session.

## Capabilities and safety
- Source module: blender_controller/model_modes.py.
- Guard: saved candidate name Vera_ModeLab_*_RESEARCH_NOT_CANON.blend, custom scene and target mesh properties candidate_not_canon and mode_lab_research, object name Vera_ModeLab_*, at most 25,000 vertices.
- Operations: status, set_mode (OBJECT/EDIT/SCULPT), select_vertices (1-64), edit_displace (at most 25 mm per step; 100 mm cumulative), sculpt_falloff (inflate or smooth on at most 3,500 vertices, at most 35 mm per call), and undo.
- Sculpt falloff is performed via guarded vertex-data operations after temporarily leaving Sculpt Mode, then returning to it. It is NOT Blender's native sculpt brush.
- Batch: blender_controller/model_modes_batch_blender.py loads a verified existing disposable candidate, requires matching source SHA256 and same-folder new output name, accepts only 1-20 strict allowlisted JSON steps, refuses an existing destination, saves a new research candidate and emits an effect receipt. No arbitrary code, shell, clipboard, network, production file, merge or GUI takeover.
- Active V7 RFB/private-gui-gate-2 is unchanged and does not expose new mode commands; a fresh verified GUI gate and separate host approval are still required for live Sculpt brush control. Do not forge or reuse prior consent.

## Real Lappy qualification (2026-11-16)
Blender 5.2.1 switched to EDIT_MESH, selected and displaced two vertices, returned and undid, entered SCULPT, applied bounded falloff on 178 research-sphere vertices, restored via undo, and saved a new disposable candidate. Source candidate SHA256 a1c55d0f00021c1c75e4d8945d92406615db1ec393d3d45ffbd8c3cee8b8a854 remained unchanged. An independent Blender process reopened saved result SHA256 493c816a424bebf2e8a49868ae45c66edfbaa95567be99ffd6ecdcfd965f73b4, verified 178 vertices/192 faces, unchanged topology, 178 changed vertices and max displacement 0.007866m. Protected master SHA256 245508c46a500789a1a680a9e26d40b1f8f3ad3a43fce8ab0b68f20ff6b19853 unchanged. Full Python test suite: 32 PASS.

A separate native Blender sculpt.mesh_filter invocation in a headless process exited EXCEPTION_ACCESS_VIOLATION (-1073741819). Therefore native Blender Sculpt brush/filter is NOT qualified. Do not introduce this unsafe operator in host-backed tool actions or claim it works.

## Next
Create and test a fresh GUI candidate with guarded mode actions, verify live HWND/PID and Blender scene hashes, separately qualify brush-stroke input with desktop privacy protections, and require actual host-local VNC consent. Never run unsafe selfimage folder-open startup or trust stale V7 gate files. Keep all private bodies, screenshots and donor assets out of this public source repository.

Relevant tests: tests/test_model_modes.py (pure policy), tests/qa_model_modes_reopen.py (independent Blender candidate check). Full integration used temporary private Lappy source and candidate only.
