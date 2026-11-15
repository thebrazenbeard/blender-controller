"""Small local stdio MCP server for attended Blender-window views.

No desktop/network VNC proxy; no input, clipboard, filesystem or canonical write.
"""
from __future__ import annotations
import base64
import json
import sys
from . import host
from .policy import ViewGrants

PROTOCOL = "2025-06-18"
GRANTS = ViewGrants()

SCHEMAS = [
    {"name": "controller_status",
     "description": "Report the local host's implemented capabilities.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "list_blender_sessions",
     "description": "List Blender windows in this controller's local desktop session.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "request_attended_view",
     "description": "Request host-local confirmation for 120 seconds of Blender-only view access.",
     "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"}},
                     "required": ["session_id"], "additionalProperties": False}},
    {"name": "capture_blender_view",
     "description": "Capture the approved Blender window at up to 2 frames per second.",
     "inputSchema": {"type": "object", "properties": {"session_id": {"type": "string"},
                      "view_token": {"type": "string"}},
                     "required": ["session_id", "view_token"], "additionalProperties": False}},
    {"name": "revoke_attended_view",
     "description": "Terminate a view grant without closing Blender.",
     "inputSchema": {"type": "object", "properties": {"view_token": {"type": "string"}},
                     "required": ["view_token"], "additionalProperties": False}},
]


def text_result(obj):
    return {"content": [{"type": "text", "text": json.dumps(obj, sort_keys=True)}],
            "isError": False}


def tool(name, args):
    if not isinstance(args, dict):
        raise ValueError("Arguments must be an object")
    schema = next((s["inputSchema"] for s in SCHEMAS if s["name"] == name), None)
    if schema is None:
        raise ValueError("Unknown controller tool")
    if not set(args).issubset(schema["properties"]) or not set(schema.get("required", ())).issubset(args):
        raise ValueError("Invalid controller arguments")
    if name == "controller_status":
        return text_result({"version": "0.1.3", **host.capabilities()})
    if name == "list_blender_sessions":
        return text_result({"sessions": host.list_sessions()})
    if name == "request_attended_view":
        session = host.resolve_session(args["session_id"])
        if not host.request_local_consent(session):
            raise PermissionError("Local operator denied Blender view access")
        current = host.resolve_session(args["session_id"])
        if current["pid"] != session["pid"]:
            raise PermissionError("Blender process changed during consent")
        grant = GRANTS.issue(current["handle"], current["pid"])
        return text_result({"view_token": grant.token, "expires_seconds": 120,
                            "session_id": current["session_id"]})
    if name == "capture_blender_view":
        session = host.resolve_session(args["session_id"])
        GRANTS.check(args["view_token"], session["handle"], session["pid"], capture=True)
        png, dims = host.capture(session)
        return {"isError": False, "content": [
            {"type": "text", "text": json.dumps({"width": dims[0], "height": dims[1],
                                                 "session_id": session["session_id"],
                                                 "view_only": True})},
            {"type": "image", "mimeType": "image/png",
             "data": base64.b64encode(png).decode("ascii")}]}
    if name == "revoke_attended_view":
        GRANTS.revoke(args["view_token"])
        return text_result({"revoked": True})
    raise ValueError("Unknown tool")


def dispatch(request):
    if not isinstance(request, dict):
        return None
    identifier = request.get("id")
    if identifier is None:
        return None
    method = request.get("method")
    try:
        if method == "initialize":
            result = {"protocolVersion": PROTOCOL,
                      "capabilities": {"tools": {"listChanged": False}},
                      "serverInfo": {"name": "vera-blender-controller", "version": "0.1.3"}}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": SCHEMAS}
        elif method == "tools/call":
            params = request.get("params")
            if not isinstance(params, dict):
                raise ValueError("Malformed tool parameters")
            result = tool(params.get("name"), params.get("arguments") or {})
        else:
            return {"jsonrpc": "2.0", "id": identifier,
                    "error": {"code": -32601, "message": "Unsupported method"}}
        return {"jsonrpc": "2.0", "id": identifier, "result": result}
    except (PermissionError, RuntimeError, ValueError, OSError, TypeError) as err:
        # No call args, token or screen contents included in errors.
        return {"jsonrpc": "2.0", "id": identifier, "result": {
            "isError": True,
            "content": [{"type": "text", "text": type(err).__name__ + ": denied or unavailable"}]}}


def main():
    for line in sys.stdin:
        try:
            response = dispatch(json.loads(line))
        except (json.JSONDecodeError, ValueError, TypeError):
            response = {"jsonrpc": "2.0", "id": None,
                        "error": {"code": -32700, "message": "Invalid JSON"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
