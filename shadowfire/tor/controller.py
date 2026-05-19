import time
from stem import Signal
from stem.control import Controller
from .proxy import CONTROL_PORT

_NEWNYM_COOLDOWN = 10  # Tor enforces this minimum between NEWNYM signals


class TorController:
    def __init__(self):
        self._ctrl: Controller | None = None
        self._last_newnym: float = 0.0

    def connect(self):
        self._ctrl = Controller.from_port(port=CONTROL_PORT)
        self._ctrl.authenticate()

    def disconnect(self):
        if self._ctrl:
            self._ctrl.close()
            self._ctrl = None

    def version(self) -> str:
        return str(self._ctrl.get_version())

    def new_identity(self):
        elapsed = time.time() - self._last_newnym
        if elapsed < _NEWNYM_COOLDOWN:
            time.sleep(_NEWNYM_COOLDOWN - elapsed)
        self._ctrl.signal(Signal.NEWNYM)
        self._last_newnym = time.time()

    def active_circuit(self) -> tuple[str | None, str | None, str | None]:
        """Return (circuit_id, exit_fingerprint, exit_nickname) of the most recent BUILT circuit."""
        circuits = [c for c in self._ctrl.get_circuits() if c.status == 'BUILT' and c.path]
        if not circuits:
            return None, None, None
        latest = max(circuits, key=lambda c: c.created)
        exit_fp, exit_nick = latest.path[-1]
        return str(latest.id), exit_fp, exit_nick

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
