import json
import unittest

from PySide6.QtCore import QCoreApplication
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from core.runtime.single_instance_guard import IpcAction, IpcRequest, SingleInstanceGuard


app = None


class TestIpcProtocol(unittest.TestCase):
    def test_tc101_whitelisted_actions_parse(self):
        self.assertEqual(IpcRequest.from_dict({"action": "ACTIVATE_WINDOW"}).action, IpcAction.ACTIVATE_WINDOW)
        self.assertEqual(IpcRequest.from_dict({"action": "OPEN_PROJECT", "path": "C:/proj"}).path, "C:/proj")
        self.assertEqual(IpcRequest.from_dict({"action": "OPEN_MEDIA", "path": "C:/video.mp4"}).action, IpcAction.OPEN_MEDIA)
        for payload in ({"action": "RUN_COMMAND", "path": "calc.exe"}, {"path": "x"}, {"action": "OPEN_PROJECT"}):
            with self.assertRaises(ValueError):
                IpcRequest.from_dict(payload)


class TestSingleInstanceGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global app
        app = QCoreApplication.instance() or QCoreApplication([])

    def setUp(self):
        self.server_name = "AI_Subtitle_Studio_Test_IPC_Guard"
        QLocalServer.removeServer(self.server_name)

    def tearDown(self):
        QLocalServer.removeServer(self.server_name)

    def test_tc100_secondary_relay_and_ack(self):
        primary = SingleInstanceGuard(self.server_name)
        self.assertTrue(primary.try_acquire_primary())
        emitted = []
        primary.request_received.connect(emitted.append)
        secondary = SingleInstanceGuard(self.server_name)
        self.assertFalse(secondary.try_acquire_primary())
        self.assertTrue(secondary.relay_to_primary(IpcRequest(IpcAction.ACTIVATE_WINDOW)))
        app.processEvents()
        self.assertEqual(len(emitted), 1)
        secondary.close()
        primary.close()

    def test_tc102_stale_endpoint_takeover(self):
        dummy = QLocalServer()
        self.assertTrue(dummy.listen(self.server_name))
        dummy.close()
        guard = SingleInstanceGuard(self.server_name)
        self.assertTrue(guard.try_acquire_primary())
        guard.close()

    def test_edge_case_payload_too_large(self):
        primary = SingleInstanceGuard(self.server_name)
        self.assertTrue(primary.try_acquire_primary())
        emitted = []
        primary.request_received.connect(emitted.append)
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        self.assertTrue(socket.waitForConnected(1000))
        socket.write(b'{"action":"ACTIVATE_WINDOW","pad":"' + b"A" * 70000 + b'"}')
        socket.flush()
        app.processEvents()
        self.assertEqual(emitted, [])
        socket.close()
        primary.close()

    def test_edge_case_malformed_json_and_unknown_action(self):
        primary = SingleInstanceGuard(self.server_name)
        self.assertTrue(primary.try_acquire_primary())
        emitted = []
        primary.request_received.connect(emitted.append)
        for payload in (b"{bad json", b'{"action":"HACK"}'):
            socket = QLocalSocket()
            socket.connectToServer(self.server_name)
            self.assertTrue(socket.waitForConnected(1000))
            socket.write(payload)
            socket.flush()
            app.processEvents()
            self.assertFalse(socket.waitForReadyRead(200))
            socket.close()
        self.assertEqual(emitted, [])
        primary.close()


if __name__ == "__main__":
    unittest.main()
