"""
Layer A: Central Read-Only Visibility

Setup and teardown for Layer A integration.
- Starts the heartbeat client (non-blocking background task)
- Registers the central proxy router (read-only portal access)

This module is imported from server.py with a single line.
It does NOT modify any frozen core behavior.
"""
import logging

logger = logging.getLogger("layer_a")


async def start_layer_a():
    """Start Layer A services. Called from server.py lifespan."""
    from backend.services.central_heartbeat_client import heartbeat_client
    await heartbeat_client.start()
    logger.info("[LAYER-A] Started (read-only visibility)")


async def stop_layer_a():
    """Stop Layer A services. Called from server.py lifespan shutdown."""
    from backend.services.central_heartbeat_client import heartbeat_client
    await heartbeat_client.stop()
    logger.info("[LAYER-A] Stopped")
