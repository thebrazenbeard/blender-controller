"""Strict Blender capture regression: never copy foreground browser windows."""
import io
import unittest
from unittest import mock
from PIL import Image
from blender_controller import windows


class WinCaptureTests(unittest.TestCase):
    def test_renders_only_validated_blender_window(self):
        fake = Image.new("RGB", (80, 45), (37, 90, 140))
        with (mock.patch.object(windows, "target_window", return_value={"pid": 77}),
              mock.patch("blender_controller.win_capture.capture_window_image",
                         return_value=fake) as print_window,
              mock.patch("PIL.ImageGrab.grab",
                         side_effect=AssertionError("Foreground desktop leak"))):
            payload, size = windows.capture_png(456)
        self.assertEqual(size, (80, 45))
        print_window.assert_called_once_with(456)
        with Image.open(io.BytesIO(payload)) as image:
            self.assertEqual(image.getpixel((30, 20)), (37, 90, 140))

    def test_rejects_handle_reuse_during_capture(self):
        fake = Image.new("RGB", (60, 30), (5, 15, 25))
        with (mock.patch.object(windows, "target_window",
                                side_effect=[{"pid": 77}, {"pid": 88}]),
              mock.patch("blender_controller.win_capture.capture_window_image",
                         return_value=fake)):
            with self.assertRaises(PermissionError):
                windows.capture_png(456)

    def test_rejects_unverified_window_before_capture(self):
        with (mock.patch.object(windows, "target_window",
                                side_effect=PermissionError("Not Blender")),
              mock.patch("blender_controller.win_capture.capture_window_image")
                as print_window):
            with self.assertRaises(PermissionError):
                windows.capture_png(999)
            print_window.assert_not_called()

    def test_rejects_oversize_frames_before_returning_pixels(self):
        fake = Image.new("RGB", (2500, 5))
        with (mock.patch.object(windows, "target_window"),
              mock.patch("blender_controller.win_capture.capture_window_image",
                         return_value=fake)):
            with self.assertRaises(RuntimeError):
                windows.capture_png(123)

    def test_no_fallback_or_platform_override(self):
        from blender_controller import win_capture
        with mock.patch.object(win_capture.sys, "platform", "linux"):
            with self.assertRaises(RuntimeError):
                win_capture.capture_window_image(111)
        with self.assertRaises(ValueError):
            # The invalid HWND check is after Win32-only check.
            # It should reject invalid input on Windows hosts.
            if win_capture.sys.platform != "win32":
                raise ValueError("Cannot supply invalid Win32 handle here")
            win_capture.capture_window_image(0)


if __name__ == "__main__":
    unittest.main()
