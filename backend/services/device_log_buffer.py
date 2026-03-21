"""
Device Log Buffer — v3.9.3

Structured ring buffer for observability events.
Captures config sync, action execution, and health events.
Transmitted via heartbeat to central server.

Thread-safe, fail-open, zero dependencies.
"""
import logging
import threading
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger("device_log_buffer")

_MAX_ENTRIES = 100
_HEARTBEAT_WINDOW = 30  # send last N entries per heartbeat


class LogEntry:
    __slots__ = ("timestamp", "level", "source", "event_type", "message", "context")

    def __init__(self, level: str, source: str, event_type: str, message: str, context: dict = None):
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.level = level
        self.source = source
        self.event_type = event_type
        self.message = message
        self.context = context

    def to_dict(self) -> dict:
        d = {
            "ts": self.timestamp,
            "level": self.level,
            "src": self.source,
            "evt": self.event_type,
            "msg": self.message,
        }
        if self.context:
            d["ctx"] = self.context
        return d


class DeviceLogBuffer:
    def __init__(self):
        self._buffer: deque = deque(maxlen=_MAX_ENTRIES)
        self._lock = threading.Lock()

    def add(self, level: str, source: str, event_type: str, message: str, context: dict = None):
        entry = LogEntry(level, source, event_type, message, context)
        with self._lock:
            self._buffer.append(entry)

    def info(self, source: str, event_type: str, message: str, context: dict = None):
        self.add("info", source, event_type, message, context)

    def warn(self, source: str, event_type: str, message: str, context: dict = None):
        self.add("warn", source, event_type, message, context)

    def error(self, source: str, event_type: str, message: str, context: dict = None):
        self.add("error", source, event_type, message, context)

    def get_all(self) -> list:
        with self._lock:
            return [e.to_dict() for e in self._buffer]

    def get_recent(self, n: int = _HEARTBEAT_WINDOW) -> list:
        with self._lock:
            items = list(self._buffer)
            return [e.to_dict() for e in items[-n:]]

    @property
    def size(self) -> int:
        return len(self._buffer)


# Singleton
device_logs = DeviceLogBuffer()
