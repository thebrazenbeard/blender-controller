import json
import tempfile
import unittest
from pathlib import Path
from blender_controller.rfb_input import BlenderInputMapper, BlenderInputBridge

class Fake:
    def __init__(self): self.events=[]
    def action(self,name,**kwargs):
        self.events.append((name,kwargs))
        return {"accepted":True}

class InputTests(unittest.TestCase):
    def test_drag_orbit_and_pan_without_any_os_injection(self):
        b=Fake();m=BlenderInputMapper(b)
        m.pointer(2,480,270)
        m.pointer(2,520,292)
        m.pointer(0,520,292)
        m.pointer(4,520,292)
        m.pointer(4,535,302)
        self.assertEqual([a for a,p in b.events],["orbit","pan"])
        self.assertAlmostEqual(b.events[0][1]["yaw"],-8.8)
    def test_navigation_morph_keyboard_and_unknown_keys(self):
        b=Fake();m=BlenderInputMapper(b)
        for k in (ord("f"),ord("1"),ord("3"),ord("7"),ord("b"),ord("h"),ord("j"),ord("n"),ord("z")):
            m.key(True,k);m.key(False,k)
        m.key(True,0xffe3)  # ctrl
        m.key(True,ord("v"))  # never clipboard paste
        self.assertEqual([n for n,p in b.events],
          ["frame","view_axis","view_axis","view_axis",
           "shape_delta","shape_delta","shape_delta","shape_delta","undo"])
    def test_bounded_wheel_and_transform(self):
        b=Fake();m=BlenderInputMapper(b)
        m.pointer(8,480,270);m.pointer(0,480,270)
        m.key(True,ord("g"))
        m.pointer(1,490,270);m.pointer(1,510,284)
        m.pointer(0,510,284)
        self.assertEqual([a for a,p in b.events],["zoom","transform_drag","transform_drag"])
        self.assertLess(abs(b.events[-1][1]["dx"]),.09)
    def test_rejects_bad_pointer_and_replayed_keydown(self):
        m=BlenderInputMapper(Fake())
        for a in ((32,30,40),(2,-1,40),(2,960,0),(0,0,540)):
            with self.assertRaises(ValueError):m.pointer(*a)
        self.assertIsNone(m.key(True,ord("G")))
        self.assertIsNone(m.key(True,ord("G")))
        with self.assertRaises(ValueError):m.key(1,ord("f"))
    def test_bridge_checks_bound_process_and_scene(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            meta={"version":"private-gui-gate-2",
              "pid":777,"hwnd":12345,
              "window_title_fragment":"Vera_Selfimage_WorkingMaster_V7"}
            (root/"ready.json").write_text(json.dumps(meta),encoding="utf8")
            b=BlenderInputBridge(d,{"pid":777,"handle":12345},timeout=.25)
            self.assertEqual(b._validate(),meta)
            with self.assertRaises(PermissionError):
                BlenderInputBridge(d,{"pid":778,"handle":12345})
    def test_bridge_rejects_unqualified_and_unknown_action(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PermissionError):
                BlenderInputBridge(d,{"pid":1,"handle":2})
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            (root/"ready.json").write_text(json.dumps({
              "version":"private-gui-gate-2","pid":1,"hwnd":2,
              "window_title_fragment":"Vera_Selfimage_WorkingMaster_V7"}))
            b=BlenderInputBridge(d,{"pid":1,"handle":2})
            with self.assertRaises(ValueError):b.action("delete_files")
            self.assertEqual(list(root.glob("request_*.json")),[])
    def test_interactive_mode_denied_without_host_consent(self):
        import socket, struct, threading
        from unittest import mock
        from blender_controller import rfb_server
        session={"pid":42,"handle":99,"session_id":"win32:99"}
        with mock.patch.object(rfb_server.host,"resolve_session",return_value=session):
            svc=rfb_server.BlenderRFB(0,"win32:99",
                control_root="ignored-while-denied",
                control_consent=lambda s:False,
                grab=lambda s: self.fail("Frame captured without consent"))
            worker=threading.Thread(target=svc.serve_forever,daemon=True)
            worker.start()
            try:
                with socket.create_connection(("127.0.0.1",svc.server_address[1]),timeout=3) as sock:
                    sock.settimeout(3)
                    self.assertEqual(sock.recv(12),rfb_server.RFB_VERSION)
                    sock.sendall(rfb_server.RFB_VERSION)
                    self.assertEqual(sock.recv(2),b"\x01\x01")
                    sock.sendall(b"\x01")
                    response=sock.recv(8)
                    self.assertEqual(len(response),8)
                    self.assertEqual(struct.unpack(">I",response[:4])[0],1)
            finally:
                svc.shutdown()
                svc.server_close()
                worker.join(timeout=3)

if __name__=="__main__": unittest.main()
