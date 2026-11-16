"""RFB 3.8 real loopback protocol tests, all using synthetic pixels."""
import socket
import struct
import threading
import unittest
from unittest import mock

from blender_controller import rfb_server

SESSION = {"session_id": "win32:321", "pid": 77, "handle": 321, "title": "Blender window"}
PIXELS = (b"\x09\x13\x27\x00" * (rfb_server.FRAME_WIDTH * rfb_server.FRAME_HEIGHT))


def recv_all(sock, size):
    b = bytearray()
    while len(b) < size:
        block = sock.recv(min(65536, size - len(b)))
        if not block:
            raise EOFError("Early EOF")
        b.extend(block)
    return bytes(b)


class RFBProtocolTests(unittest.TestCase):
    def setUp(self):
        self.resolve = mock.patch.object(rfb_server.host, "resolve_session", return_value=SESSION)
        self.resolve.start()
        self.addCleanup(self.resolve.stop)
        self.seen_consent = []
        self.server = rfb_server.BlenderRFB(
            0, SESSION["session_id"], consent=lambda s: self.seen_consent.append(s) or True,
            grab=lambda s: PIXELS)
        self.addCleanup(self.server.server_close)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.05}, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.shutdown)

    def connect(self):
        sock = socket.create_connection(self.server.server_address, timeout=4)
        sock.settimeout(4)
        self.assertEqual(recv_all(sock, 12), rfb_server.RFB_VERSION)
        return sock

    def init_client(self, sock):
        sock.sendall(rfb_server.RFB_VERSION)
        self.assertEqual(recv_all(sock, 2), b"\x01\x01")
        sock.sendall(b"\x01")
        self.assertEqual(recv_all(sock, 4), b"\x00\x00\x00\x00")
        sock.sendall(b"\x01")
        width, height = struct.unpack(">HH", recv_all(sock, 4))
        self.assertEqual((width, height), (rfb_server.FRAME_WIDTH, rfb_server.FRAME_HEIGHT))
        self.assertEqual(recv_all(sock, 16), rfb_server.PIXEL_FORMAT)
        name_len, = struct.unpack(">I", recv_all(sock, 4))
        self.assertEqual(recv_all(sock, name_len), rfb_server.NAME)

    def test_real_socket_handshake_full_raw_frame_and_input_ignored(self):
        with self.connect() as sock:
            self.init_client(sock)
            # Key and Pointer events may be sent but must have no host effect.
            sock.sendall(b"\x04\x01\x00\x00" + struct.pack(">I", 0x61))
            sock.sendall(b"\x05\x01" + struct.pack(">HH", 11, 12))
            sock.sendall(b"\x03\x00" + struct.pack(">HHHH", 0, 0,
                    rfb_server.FRAME_WIDTH, rfb_server.FRAME_HEIGHT))
            self.assertEqual(recv_all(sock, 4), b"\x00\x00\x00\x01")
            self.assertEqual(recv_all(sock, 12),
                             struct.pack(">HHHHi", 0, 0,
                                 rfb_server.FRAME_WIDTH, rfb_server.FRAME_HEIGHT, 0))
            self.assertEqual(recv_all(sock, len(PIXELS)), PIXELS)
        self.assertEqual(len(self.seen_consent), 1)

    def test_no_frame_before_host_consent_and_denial(self):
        self.server.consent = lambda _session: False
        with self.connect() as sock:
            sock.sendall(rfb_server.RFB_VERSION)
            self.assertEqual(recv_all(sock, 2), b"\x01\x01")
            sock.sendall(b"\x01")
            error, length = struct.unpack(">II", recv_all(sock, 8))
            self.assertEqual(error, 1)
            self.assertIn(b"Denied", recv_all(sock, length))

    def test_wrong_protocol_rejected_without_consent(self):
        with self.connect() as sock:
            sock.sendall(b"RFB 003.007\n")
            self.assertEqual(sock.recv(1), b"")
        self.assertEqual(self.seen_consent, [])

    def test_reject_non_loopback_target(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
