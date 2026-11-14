# Experimental Blender-window RFB: private-tailnet qualification

**State:** local tested prototype only. RFB 3.8 raw, 960 × 540, view-only. This source is not a consumer-grade remote access service and not qualified from a separate physical host. No public interface or Funnel exposure is authorized.

## Security model and limitations

- `python -m blender_controller.rfb_server --session-id <verified-local-Blender-session> --port <unused-port>` binds **127.0.0.1 only**. A valid session ID comes from the local MCP `list_blender_sessions`, not from arbitrary hostnames.
- The RFB handshake advertises **SecurityType None**. On loopback the host operator must approve an explicit **Yes/No, 20-second timeout** prompt before the framebuffer security-result success and any pixel data. The server rejects a denied or expired prompt.
- SecurityType None provides **no transport encryption or peer identity** by itself. The only intended off-host transport is separately configured **Tailscale Serve TCP forwarding** on an authenticated, encrypted, ACL-restricted tailnet. Do **not** expose this RFB listener on LAN/public IP, forward a router port, or enable Tailscale Funnel. Tailnet membership alone is not sufficient operator consent.
- Remote input events (key, pointer) are ignored; clipboard writes are discarded; there is no file transfer, arbitrary script/command interface, image persistence, recording or unattended desktop takeover.
- Each connection is limited to one active client, at most 120 seconds, at most 150 frames, at most 2 FPS. The first tests are synthetic raw-frame and policy tests; a stock viewer from a second host has not yet been qualified.
- Visible consent boxes and window capture can have same-user/compositor attack paths. Neither same-user hostile manipulation nor lock/UAC/secure desktop behaviour is qualified.

## Host-neutral local workflow

The controller is designed for any independently authorized machine with a tested Blender-window capture adapter, not a named permanent host. The current capture backend requires a visible `blender.exe` Win32 window, Python and Pillow. Other OS backends are unsupported until separately implemented and tested.

1. In a local terminal, enumerate Blender windows with the controller's `list_blender_sessions` MCP tool and confirm the selected process belongs to the intended Blender project.
2. Start the loopback RFB process for that session using an available private port (the local program default is 15909). The process must run in the actual interactive desktop user session.
3. After confirming no existing route or listener collision, optionally use Tailscale Serve TCP proxy to forward the chosen tailnet port to `tcp://127.0.0.1:<port>`. Preserve all pre-existing Tailscale configurations. Verify `tailscale serve status` explicitly identifies **tailnet only**.
4. From an independently authorized tailnet client, connect with a VNC viewer that supports RFB 3.8 and `None` security selection. The operator at the host must explicitly allow the prompt. A second-host full-frame capture is required before claiming interoperability.
5. When finished, terminate the local RFB process. Remove only the route this controller created with `tailscale serve --tcp=<port> off`; do not reset unrelated routes.

These commands are illustrative for a privately administered host. An actual port, device identity, secure access policy and approval must be verified locally. Do not hard-code private Tailscale addresses, user identifiers, session handles, credentials or project paths in this **public** repository.

## Evidence (2026-11-14)

- Actual Win32 Blender window-capture path returned a 960 × 540 synthetic-render-ready pixel frame from a running Blender process; no private screenshot committed.
- `python -m unittest discover -s tests -q`: 17/17 PASS on the first Windows test host after the protocol code was added. Actual local socket returned `RFB 003.008\n`; host-self-connect through a tailnet route returned the same banner.
- The first Windows host installed the local **Codex** plugin; this is not an installed or discoverable ChatGPT-web plugin. The local stdio tools operate independently of the view-only RFB process.
- No unattended capture, cross-machine interactive VNC frame, remote input, third-party viewer interoperability, canon master promotion or systemwide installation is claimed.

## Revision boundary

The legacy Selfimage master and private Blender working artifacts remain off-repository. The controller does not mutate Blender files. Modeling successors are created through separately authorized, versioned local Blender scripts, not RFB key input or an unrestricted Blender Python socket.
