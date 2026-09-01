from dataclasses import dataclass
from enum import Enum
import json

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket


class IpcAction(Enum):
    ACTIVATE_WINDOW = "ACTIVATE_WINDOW"
    OPEN_PROJECT = "OPEN_PROJECT"
    OPEN_MEDIA = "OPEN_MEDIA"


@dataclass(frozen=True)
class IpcRequest:
    action: IpcAction
    path: str | None = None

    def __post_init__(self):
        if self.action is IpcAction.ACTIVATE_WINDOW and self.path is not None:
            raise ValueError("activation cannot include a path")
        if self.action is not IpcAction.ACTIVATE_WINDOW and not self.path:
            raise ValueError("path required")

    @classmethod
    def from_dict(cls, payload: dict):
        try:
            action = IpcAction(payload["action"])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("invalid IPC action") from error
        return cls(action, payload.get("path"))

    def to_dict(self) -> dict:
        payload = {"action": self.action.value}
        if self.path is not None:
            payload["path"] = self.path
        return payload


class SingleInstanceGuard(QObject):
    request_received = Signal(object)

    def __init__(self, server_name: str = "ai-subtitle-studio", parent=None):
        super().__init__(parent)
        self.server_name = server_name
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._accept)

    def try_acquire_primary(self) -> bool:
        probe = QLocalSocket()
        probe.connectToServer(self.server_name)
        if probe.waitForConnected(100):
            probe.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.server_name)
        if self.server.listen(self.server_name):
            return True
        QLocalServer.removeServer(self.server_name)
        return self.server.listen(self.server_name)

    def relay_to_primary(self, request: IpcRequest, timeout_ms: int = 1500) -> bool:
        socket = QLocalSocket()
        socket.connectToServer(self.server_name)
        if not socket.waitForConnected(timeout_ms):
            return False
        socket.write(json.dumps(request.to_dict()).encode("utf-8"))
        socket.flush()
        from PySide6.QtCore import QCoreApplication
        deadline = timeout_ms
        while not socket.bytesAvailable() and deadline > 0:
            QCoreApplication.processEvents()
            if socket.waitForReadyRead(20):
                break
            deadline -= 20
        if not socket.bytesAvailable():
            return False
        try:
            return json.loads(bytes(socket.readAll()).decode("utf-8")).get("ok") is True
        except (ValueError, UnicodeDecodeError):
            return False

    def start_listening(self) -> None:
        return None

    def close(self) -> None:
        self.server.close()

    def _accept(self) -> None:
        socket = self.server.nextPendingConnection()
        if socket is None:
            return
        socket.readyRead.connect(lambda: self._read(socket))

    def _read(self, socket: QLocalSocket) -> None:
        if socket.bytesAvailable() > 65536:
            socket.disconnectFromServer()
            return
        try:
            request = IpcRequest.from_dict(json.loads(bytes(socket.readAll()).decode("utf-8")))
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            socket.write(b'{"ok":false}')
            socket.flush()
            return
        self.request_received.emit(request)
        socket.write(b'{"ok":true}')
        socket.flush()
