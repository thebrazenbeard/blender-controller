import json
import unittest
from unittest import mock
from blender_controller import host, mcp_stdio


class ControllerTests(unittest.TestCase):
    def setUp(self):
        mcp_stdio.GRANTS = mcp_stdio.ViewGrants(
            now=lambda: 100.0, minimum_interval=0.5)

    def test_host_neutral_api_and_no_linux_fallback(self):
        with mock.patch.object(host.sys, "platform", "linux"):
            caps = host.capabilities()
            self.assertFalse(caps["view"])
            self.assertFalse(caps["control"])
            with self.assertRaises(RuntimeError):
                host.list_sessions()

    def test_status_and_mcp_tool_listing(self):
        result = mcp_stdio.dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        names = [x["name"] for x in result["result"]["tools"]]
        self.assertEqual(len(names), len(set(names)))
        self.assertNotIn("execute_python", names)
        status = mcp_stdio.tool("controller_status", {})
        self.assertFalse(json.loads(status["content"][0]["text"])["remote_vnc"])

    def test_unapproved_capture_is_denied(self):
        session = {"session_id": "win32:321", "handle": 321, "pid": 77, "title": "Blender"}
        with mock.patch.object(host, "resolve_session", return_value=session):
            with mock.patch.object(host, "capture") as capture:
                response = mcp_stdio.dispatch({"jsonrpc": "2.0", "id": 4,
                     "method": "tools/call", "params": {"name": "capture_blender_view",
                     "arguments": {"session_id": "win32:321", "view_token": "ungranted"}}})
                self.assertTrue(response["result"]["isError"])
                capture.assert_not_called()

    def test_denied_host_consent_never_issues_token(self):
        session = {"session_id": "win32:321", "handle": 321, "pid": 77, "title": "Blender"}
        with mock.patch.object(host, "resolve_session", return_value=session), \
             mock.patch.object(host, "request_local_consent", return_value=False):
            result = mcp_stdio.dispatch({"jsonrpc": "2.0", "id": 3,
                 "method": "tools/call", "params": {"name": "request_attended_view",
                 "arguments": {"session_id": "win32:321"}}})
            self.assertTrue(result["result"]["isError"])

    def test_synthetic_approved_view_and_revoke(self):
        session = {"session_id": "win32:321", "handle": 321, "pid": 77, "title": "Blender"}
        with mock.patch.object(host, "resolve_session", return_value=session), \
             mock.patch.object(host, "request_local_consent", return_value=True), \
             mock.patch.object(host, "capture", return_value=(b"PNG-test-bytes", (20, 12))):
            grant = mcp_stdio.tool("request_attended_view", {"session_id": "win32:321"})
            token = json.loads(grant["content"][0]["text"])["view_token"]
            shown = mcp_stdio.tool("capture_blender_view", {"session_id": "win32:321", "view_token": token})
            self.assertEqual(shown["content"][1]["mimeType"], "image/png")
            mcp_stdio.tool("revoke_attended_view", {"view_token": token})
            with self.assertRaises(PermissionError):
                mcp_stdio.tool("capture_blender_view", {"session_id": "win32:321", "view_token": token})

    def test_session_listing_does_not_leak_blender_paths(self):
        fake = [{"hwnd": 123, "pid": 77,
                 "title": r"SecretProject [D:\\private\\project.blend] - Blender"}]
        with (
            mock.patch.object(host.sys, "platform", "win32"),
            mock.patch("blender_controller.windows.list_blender_windows", return_value=fake),
        ):
            sessions = host.list_sessions()
            self.assertEqual(sessions, [{"session_id": "win32:123", "pid": 77,
                                         "title": "Blender window"}])

    def test_malformed_tool_params_fail_closed(self):
        response = mcp_stdio.dispatch({"jsonrpc": "2.0", "id": 12,
              "method": "tools/call", "params": ["bad"]})
        self.assertTrue(response["result"]["isError"])

    def test_strict_arguments_and_invalid_session_id(self):
        with self.assertRaises(ValueError):
            mcp_stdio.tool("controller_status", {"shell": "powershell"})
        for malformed in ("", "win32:0", "win32:1;rm -rf", "Linux:123"):
            with self.assertRaises(ValueError):
                host._hwnd(malformed)


if __name__ == "__main__":
    unittest.main()
