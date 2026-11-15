# Host-neutral Blender Controller: design and qualification (2026-11-14)

**State:** experimental source plus local runtime probe on Lappy: a Codex plugin is installed and a loopback RFB 3.8 view listener is forwarded through Tailscale as tailnet-only. No public screen endpoint, remote mouse/keyboard access, second-host verification or ChatGPT web plugin connection is qualified. This is a portable foundation for an attended visual feedback loop, not a complete UnboundVNC host, consumer remote desktop, or active ChatGPT connection.

## Why it is host-neutral

The controller targets a **Blender session on whichever authorized host runs it**, not a hard-coded machine. A host can be Windows, Linux/X11, or another platform provided an independently validated adapter exists. Session identifiers and process identity are local to that host. An optional name (Lappy, VN1, VN2) is descriptive metadata, not authentication, access rights, or a routing authority.

- `blender_controller/host.py`: stable operations `capabilities`, `list_sessions`, `resolve_session`, `request_local_consent`, `capture`; deliberately disallows unsupported platforms.
- `blender_controller/windows.py`: currently the **only implemented** capture backend; verifies the actual `blender.exe` executable, scopes frames to the selected window, and asks for host-local approval.
- `blender_controller/policy.py`: one current random view-only grant tied to process + window handle; maximum 120 seconds, minimum 500 ms between captures, revocable, non-replayable upon replacement.
- `blender_controller/mcp_stdio.py`: local stdio MCP, no listening socket. Pre-consent listings redact Blender project titles and filesystem paths. Host-denied, expired, wrong-window and malformed requests fail closed.
- `mcp.json`: **prototype local plugin** configuration; requires a separately supported local plugin runtime and Python + Pillow on the machine. It does not make ChatGPT web magically reach a remote PC. No credential or host IP is embedded.

## Target machines

| Machine | Status | Host pathway |
| --- | --- | --- |
| Lappy | Actual Win32 capture proof and current local MCP/status tests | Windows capture adapter; no installed plugin or authorized attended view grant yet |
| VN1 | **Unverified** for this controller | Qualify OS, Python, interactive desktop, Blender process and attended consent separately |
| VN2 | **Unverified** for this controller | If Linux/X11, add an explicit window-only capture adapter; Wayland requires compositor-approved capture; no generic desktop screenshot fallback |
| Other host | **Unsupported until qualified** | Separate local instance with its own consent, OS adapter, independent identity and session custody |

Do not infer current OS, Blender installation, reachable desktop, ports or remote-control rights from historical inventory. Current `Windows` support does not imply compatibility with Windows secure desktop, UAC, lock screen, service session or other logged-on users.

## Security and privacy

No public VNC, HTTP, RFB, or proxy port. No mouse, keyboard, clipboard, file transfer, arbitrary commands, scripting, original .blend mutation, recording or unattended access. A tool request may display a local consent prompt; it is not remote authority. Frame capture is scoped to an identified Blender process/window **but can still contain private project content, paths or unrelated UI overlays inside that window**; consent is therefore required for each short session, and frames must not be logged or published. Model output and repo presence are not consent or qualification. Same-user process interference with local dialogs and hostile desktop attacks remain unevaluated.

The existing Vera Blender Studio tunnel is separate. Its raw Python socket must remain unexposed. UnboundVNC's open draft host/viewer/consent code is **not** production-qualified and is not embedded or installed by this project. If future network control is necessary, it needs authenticated encrypted transport, explicit host identity, per-controller revocation, a real attended host probe, a defined capture boundary and separately approved input privileges. A host alias is NEVER the security boundary.

## Current test scope and next proof

Local Python unit tests exercise grant expiry, reissue/revocation, scoped identity, rate limits, malformed request denial, consent denial, and pre-consent redaction. The local MCP process was queried for status/session listing and denied an unapproved frame. Prior independent Windows `Pillow.ImageGrab.grab(window=...)` captured a real Blender window; this does not establish a usable **ChatGPT-connected live stream**.

Before any native plugin install or remote access claim: run a supervised real attended view consent/capture/revoke test on a non-sensitive Blender candidate window, test process/window reuse and denial/replay, then qualify VN1 and VN2 individually with minimal host capability probes. Only after that evaluate optional **bounded** viewport input and candidate-only Undo/Save As through a separately authorized, recoverable action path. Do not shortcut by exposing desktop control.

## Local source-only test

```powershell
py -3 -m unittest discover -s tests -v
```

Local developer probe (reads no screen pixels or prompts):

```powershell
@'
{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"controller_status","arguments":{}}}
'@ | py -3 -m blender_controller.mcp_stdio
```

**Custody:** repository is PUBLIC. Do not commit screenshots, personal hostnames, host keys/tokens, private .blend sources, credentials, model assets, or intimate data. Keep changes in a draft PR until testing and owner authority permit additional effects.
