# Vera Blender Controller

See Blender’s viewport, manipulate a candidate, inspect the result, and undo or save **when each capability has been independently qualified and authorized**.

**Current phase:** host-neutral attended **view-only prototype**. A local stdio MCP server can list Blender windows, obtain local host approval for a 120-second window-only capture grant, display up to 2 PNG frames per second and revoke access. A separate loopback-only RFB 3.8 view server now has a tailnet-only Tailscale route on the first tested Windows host, with local consent required for framebuffer access. Mouse/keyboard control, plugin-based Blender saves, a ChatGPT web connection, and VN1/VN2 qualification remain unavailable or unverified.

The project is **not tied to Lappy**. It can run on an authorized machine with a qualified platform adapter and consent path; currently only a Windows Win32 capture adapter exists. VN1 and VN2 are candidates for future qualification, not pre-approved or assumed reachable targets. See [architecture and release holds](docs/ARCHITECTURE.md).

## Source layout

- `blender_controller/host.py` — host-neutral Blender-session interface, explicit unsupported-platform failure
- `blender_controller/windows.py` — window-only Win32 capture and local approval
- `blender_controller/policy.py` — short-lived, scoped, revocable capability grant
- `blender_controller/mcp_stdio.py` — local MCP tools without any network listener
- `tests/` — synthetic unit and negative-security tests
- `plugin.json`, `mcp.json` — proposed **local-only plugin package**, not installed or published

## Safety

The source repo is public. Never commit host screenshots, credentials, private Blender files or private paths. No unattended desktop access, PUBLIC VNC endpoint, clipboard, arbitrary Python execution or canonical asset mutation. The private loopback RFB service uses a separate host-local consent gate and does not take keyboard or mouse input. UnboundVNC remains a separate, unqualified network-transport candidate; see its [release gates](https://github.com/thebrazenbeard/UnboundVNC/blob/main/docs/RELEASE_GATES.md).

## Local tests

Python 3.10+ is recommended; Windows captures also need Pillow. Run `python -m unittest discover -s tests -v`. Test success is not a remote deployment or interactive desktop-control claim.
