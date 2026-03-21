"""Tests for Offline Queue Service — v3.9.7"""
import json
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Use a temp dir for test data
import tempfile
_test_dir = tempfile.mkdtemp()
_test_queue_file = Path(_test_dir) / "offline_queue.json"

# Patch the file paths before importing the module
import backend.services.offline_queue as oq_module
oq_module._DATA_DIR = Path(_test_dir)
oq_module._QUEUE_FILE = _test_queue_file

from backend.services.offline_queue import OfflineQueue


def new_queue():
    """Create a fresh queue instance for each test."""
    q = OfflineQueue()
    q._central_url = "http://fake-central:8002"
    q._api_key = "test_key_123"
    # Clean file
    if _test_queue_file.exists():
        _test_queue_file.unlink()
    q._queue = []
    q._seen_keys = set()
    return q


def test_enqueue_basic():
    q = new_queue()
    q.enqueue("action_ack", "POST", "/api/ack", {"id": "a1"}, "ack_a1")
    assert len(q._queue) == 1
    assert q._queue[0]["idempotency_key"] == "ack_a1"
    assert q._queue[0]["msg_type"] == "action_ack"
    assert q._enqueued_total == 1
    print("PASS: test_enqueue_basic")


def test_persistence():
    q = new_queue()
    q.enqueue("telemetry", "POST", "/api/telem", {"data": "x"}, "telem_1")
    q.enqueue("action_ack", "POST", "/api/ack", {"id": "a2"}, "ack_a2")
    assert _test_queue_file.exists()

    # Create a new queue instance and load from disk
    q2 = OfflineQueue()
    oq_module._QUEUE_FILE = _test_queue_file  # ensure same path
    q2._load()
    assert len(q2._queue) == 2
    assert q2._queue[0]["idempotency_key"] == "telem_1"
    assert q2._queue[1]["idempotency_key"] == "ack_a2"
    print("PASS: test_persistence")


def test_idempotency():
    q = new_queue()
    q.enqueue("ack", "POST", "/api/ack", {"id": "x"}, "ack_x")
    q.enqueue("ack", "POST", "/api/ack", {"id": "x"}, "ack_x")  # duplicate
    q.enqueue("ack", "POST", "/api/ack", {"id": "x"}, "ack_x")  # duplicate
    assert len(q._queue) == 1
    assert q._enqueued_total == 1
    print("PASS: test_idempotency")


def test_overflow():
    q = new_queue()
    # Fill beyond max
    original_max = oq_module._MAX_ENTRIES
    oq_module._MAX_ENTRIES = 5  # Lower for testing
    try:
        for i in range(8):
            q.enqueue("test", "POST", "/api/test", {"i": i}, f"key_{i}")
        assert len(q._queue) == 5
        # Oldest 3 should have been dropped
        assert q._queue[0]["idempotency_key"] == "key_3"
        assert q._queue[4]["idempotency_key"] == "key_7"
        assert q._dropped_total == 3
    finally:
        oq_module._MAX_ENTRIES = original_max
    print("PASS: test_overflow")


def test_fifo_order():
    q = new_queue()
    for i in range(5):
        q.enqueue("test", "POST", "/api/test", {"i": i}, f"fifo_{i}")
    keys = [e["idempotency_key"] for e in q._queue]
    assert keys == ["fifo_0", "fifo_1", "fifo_2", "fifo_3", "fifo_4"]
    print("PASS: test_fifo_order")


def test_status_report():
    q = new_queue()
    q.enqueue("ack", "POST", "/api/ack", {"id": "1"}, "s1")
    q.enqueue("ack", "POST", "/api/ack", {"id": "2"}, "s2")
    s = q.status
    assert s["pending"] == 2
    assert s["configured"] is True
    assert s["enqueued_total"] == 2
    assert s["drained_total"] == 0
    print("PASS: test_status_report")


def test_drain_success():
    """Test that drain sends queued items and removes them on success."""
    q = new_queue()
    q.enqueue("ack", "POST", "/api/ack", {"id": "d1"}, "drain_1")
    q.enqueue("ack", "POST", "/api/ack", {"id": "d2"}, "drain_2")

    # Mock httpx to return success
    mock_response = MagicMock()
    mock_response.status_code = 200

    async def mock_post(*args, **kwargs):
        return mock_response

    async def mock_put(*args, **kwargs):
        return mock_response

    async def run_drain():
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.put = mock_put
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client
            await q.drain()

    asyncio.get_event_loop().run_until_complete(run_drain())
    assert len(q._queue) == 0
    assert q._drained_total == 2
    print("PASS: test_drain_success")


def test_drain_failure_keeps_entries():
    """Test that failed drain keeps entries in queue with incremented retry."""
    q = new_queue()
    q.enqueue("ack", "POST", "/api/ack", {"id": "f1"}, "fail_1")

    async def run_drain():
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client
            await q.drain()

    asyncio.get_event_loop().run_until_complete(run_drain())
    assert len(q._queue) == 1
    assert q._queue[0]["retries"] == 1
    assert q._drain_errors == 1
    print("PASS: test_drain_failure_keeps_entries")


def test_drain_client_error_removes():
    """Test that 4xx responses remove entries (don't retry)."""
    q = new_queue()
    q.enqueue("ack", "POST", "/api/ack", {"id": "c1"}, "client_err_1")

    mock_response = MagicMock()
    mock_response.status_code = 404

    async def run_drain():
        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client
            await q.drain()

    asyncio.get_event_loop().run_until_complete(run_drain())
    # 4xx should be treated as "accepted, don't retry"
    assert len(q._queue) == 0
    print("PASS: test_drain_client_error_removes")


def test_never_crashes():
    """Test that enqueue NEVER raises, even with broken persistence."""
    q = new_queue()
    # Break persistence
    oq_module._QUEUE_FILE = Path("/nonexistent/dir/queue.json")
    try:
        q.enqueue("test", "POST", "/api/test", {"x": 1}, "crash_test")
        # Should not crash, item still in memory
        assert len(q._queue) == 1
    finally:
        oq_module._QUEUE_FILE = _test_queue_file
    print("PASS: test_never_crashes")


if __name__ == "__main__":
    test_enqueue_basic()
    test_persistence()
    test_idempotency()
    test_overflow()
    test_fifo_order()
    test_status_report()
    test_drain_success()
    test_drain_failure_keeps_entries()
    test_drain_client_error_removes()
    test_never_crashes()
    print("\n=== ALL TESTS PASSED ===")
