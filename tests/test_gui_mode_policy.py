"""Negative security tests for host-local GUI ModeLab command grammar."""
import unittest
from blender_controller.gui_mode_policy import check_request,require_window_binding,OUTPUT_NAME

ID="a"*32
SESSION="b"*32
SOURCE="c"*64
class GatePolicy(unittest.TestCase):
    def valid(self,action="status",args=None):
        return {"id":ID,"session":SESSION,"action":action,"args":{} if args is None else args}
    def test_allows_only_bounded_mode_requests(self):
        self.assertEqual(check_request(self.valid(),ID,SESSION),("status",{}))
        self.assertEqual(check_request(self.valid("set_mode",{"mode":"SCULPT"}),ID,SESSION),
                         ("set_mode",{"mode":"SCULPT"}))
        self.assertEqual(check_request(self.valid("save_candidate",{"output_name":OUTPUT_NAME}),
                         ID,SESSION)[0],"save_candidate")
    def test_denies_stale_replay_or_forged_action(self):
        examples=[(self.valid(),"d"*32,SESSION),
                  (self.valid(),ID,"c"*32),
                  ({**self.valid(),"id":"../bad"},ID,SESSION),
                  ({**self.valid(),"exec":"a"},ID,SESSION),
                  (self.valid("python",{"code":"print(1)"}),ID,SESSION),
                  (self.valid("set_mode",{"mode":"POSE"}),ID,SESSION),
                  (self.valid("sculpt_falloff",{"center":[0,0,0],"radius":1.5,
                    "strength":.4,"effect":"inflate"}),ID,SESSION)]
        for request,id_,session in examples:
            with self.subTest(request=request,id=id_):
                with self.assertRaises(ValueError):
                    check_request(request,id_,session)
    def test_denies_arbitrary_saves(self):
        cases=[{},{"output_name":"master.blend"},{"output_name":"../master.blend"},
               {"output_name":OUTPUT_NAME,"extra":"bad"},
               {"output_name":"Vera_ModeLab_Fake_RESEARCH_NOT_CANON.blend"}]
        for args in cases:
            with self.subTest(args=args),self.assertRaises(ValueError):
                check_request(self.valid("save_candidate",args),ID,SESSION)
    def test_exact_window_binding(self):
        info={"version":"mode-lab-gui-1","pid":111,"hwnd":222,"session_id":SESSION,
              "source_sha256":SOURCE,"allowed":["status"]}
        self.assertTrue(require_window_binding(info,111,222,SOURCE))
        for pid,hwnd,source in ((1,222,SOURCE),(111,0,SOURCE),
                                (111,221,SOURCE),(111,222,"d"*64)):
            with self.subTest(pid=pid,hwnd=hwnd):
                with self.assertRaises(PermissionError):
                    require_window_binding(info,pid,hwnd,source)
        for x in ({"version":"mode-lab-gui-1","pid":111,"hwnd":222},
                  {"version":"mode-lab-gui-1","pid":111,"hwnd":222,"session_id":"INVALID","source_sha256":SOURCE}):
            with self.assertRaises(PermissionError):
                require_window_binding(x,111,222,SOURCE)
    def test_denies_scalar_type_spoofing(self):
        for bad in [None,[],{"id":ID,"session":SESSION,"action":"status","args":[]}]:
            with self.assertRaises(ValueError):check_request(bad,ID,SESSION)
        with self.assertRaises(PermissionError):
            require_window_binding({"version":"mode-lab-gui-1","pid":True,"hwnd":222,
               "session_id":SESSION,"source_sha256":SOURCE},111,222,SOURCE)
if __name__=="__main__":unittest.main()
