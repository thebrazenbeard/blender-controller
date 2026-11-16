"""Pure negative policy tests for guarded candidate-only Edit/Sculpt mode controls."""
import unittest
from blender_controller.model_modes import validate, ModeLab, MODES

class Validation(unittest.TestCase):
    def test_allowed_commands(self):
        self.assertTrue(validate("status",{}))
        self.assertTrue(validate("set_mode",{"mode":"EDIT"}))
        self.assertTrue(validate("set_mode",{"mode":"SCULPT"}))
        self.assertTrue(validate("set_mode",{"mode":"OBJECT"}))
        self.assertTrue(validate("select_vertices",{"indices":[0,4,9]}))
        self.assertTrue(validate("edit_displace",{"delta":[0,.012,0]}))
        self.assertTrue(validate("sculpt_falloff",{"center":[0,0,.1],
            "radius":.5,"strength":.01,"effect":"smooth"}))
        self.assertTrue(validate("undo",{}))

    def test_denies_unrecognized_and_kwargs(self):
        cases=[
          ("exec",{}),("save",{}),("set_mode",{"mode":"POSE"}),
          ("set_mode",{"mode":"SCULPT","python":"bad"}),
          ("edit_displace",{"delta":[0,.001,0],"file":"other.blend"}),
          ("status",{"script":"run"}),("undo",{"target":"master"}),
          ("select_vertices",{"indices":[]}),
          ("select_vertices",{"indices":[0,0]}),
          ("select_vertices",{"indices":[-1]}),
          ("select_vertices",{"indices":[True]}),
          ("select_vertices",{"indices":list(range(65))}),
          ("sculpt_falloff",{"center":[0,0,0],"radius":1,
            "strength":.01,"effect":"inflate"}),
          ("sculpt_falloff",{"center":[0,0,0],"radius":.2,
            "strength":.4,"effect":"inflate"}),
          ("sculpt_falloff",{"center":[0,0,0],"radius":.2,
            "strength":.01,"effect":"delete"}),
          ("sculpt_falloff",{"center":[0,0,float("nan")],"radius":.2,
            "strength":.01,"effect":"smooth"}),
          ("edit_displace",{"delta":[float("inf"),0,0]}),
          ("edit_displace",{"delta":[.02,.02,.02]}),
          ("edit_displace",{"delta":[0,False,0]}),
        ]
        for action,payload in cases:
            with self.subTest(action=action,payload=str(payload)):
                with self.assertRaises(ValueError):validate(action,payload)

    def test_denies_any_target_without_private_scene_binding(self):
        class Context:scene=None
        class ViewLayer:objects=type("O",(),{"active":None})()
        class Data:filepath=""
        class Fake:context=Context();data=Data()
        Fake.context.view_layer=ViewLayer()
        o=ModeLab(Fake(),None)
        with self.assertRaises(PermissionError):
            o.apply("status")
        with self.assertRaises(ValueError):
            o.apply("set_mode",mode="POSE")

if __name__=="__main__":
    unittest.main()
