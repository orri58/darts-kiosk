"""
Discovery & Pairing Routes
- Master: discover agents, initiate pairing
- Agent: show pairing code, handle pair/verify/challenge
"""
import os
import logging
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend.models import User, TrustedPeer
from backend.dependencies import require_admin, get_current_user, log_audit
from backend.services.mdns_service import mdns_service
from backend.services.pairing_service import pairing_service

logger = logging.getLogger(__name__)
MODE = os.environ.get('MODE', 'MASTER')

router = APIRouter()


# ===== Pydantic models =====

class PairInitiateRequest(BaseModel):
    board_id: str
    code: str

class ChallengeResponseRequest(BaseModel):
    nonce: str
    signature: str
    master_fingerprint: str
    master_board_id: str

class PairVerifyRequest(BaseModel):
    code: str
    master_fingerprint: str
    master_ip: str
    master_board_id: str


# ===== Master endpoints =====

@router.get("/discovery/agents")
async def list_discovered_agents(admin: User = Depends(require_admin)):
    """List agents discovered via mDNS on the LAN."""
    mdns_service.remove_stale(max_age_seconds=300)
    agents = mdns_service.get_discovered_agents()

    return {
        "agents": agents,
        "count": len(agents),
        "discovery_active": mdns_service.is_running,
    }


@router.get("/discovery/peers")
async def list_paired_peers(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """List all trusted/paired peers."""
    result = await db.execute(
        select(TrustedPeer).where(TrustedPeer.is_active == True).order_by(TrustedPeer.paired_at.desc())
    )
    peers = result.scalars().all()
    return {
        "peers": [
            {
                "id": p.id,
                "board_id": p.board_id,
                "role": p.role,
                "ip": p.ip,
                "port": p.port,
                "version": p.version,
                "fingerprint": p.fingerprint,
                "paired_at": p.paired_at.isoformat() if p.paired_at else None,
                "last_seen": p.last_seen.isoformat() if p.last_seen else None,
                "is_active": p.is_active,
            }
            for p in peers
        ]
    }


@router.post("/discovery/pair")
async def initiate_pairing(
    data: PairInitiateRequest,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Master initiates pairing with a discovered agent.
    1. Sends code to agent for verification
    2. Agent returns challenge nonce
    3. Master signs and sends back
    4. Agent issues paired token
    """
    agent = mdns_service.get_agent(data.board_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {data.board_id} not found via mDNS")

    agent_url = f"http://{agent.ip}:{agent.port}/api/agent"
    master_fp = pairing_service.compute_fingerprint("MASTER")
    local_board = os.environ.get('LOCAL_BOARD_ID', 'MASTER')

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Step 1: send code to agent for verification -> get challenge
            verify_resp = await client.post(f"{agent_url}/pair/verify", json={
                "code": data.code,
                "master_fingerprint": master_fp,
                "master_ip": str(client._base_url) or "0.0.0.0",
                "master_board_id": local_board,
            })

            if verify_resp.status_code != 200:
                detail = verify_resp.json().get("detail", "Pairing code rejected")
                raise HTTPException(status_code=400, detail=detail)

            nonce = verify_resp.json()["nonce"]

            # Step 2: sign challenge
            signature = pairing_service.compute_hmac(master_fp, nonce)

            # Step 3: send signed response -> get paired token
            challenge_resp = await client.post(f"{agent_url}/pair/complete", json={
                "nonce": nonce,
                "signature": signature,
                "master_fingerprint": master_fp,
                "master_board_id": local_board,
            })

            if challenge_resp.status_code != 200:
                detail = challenge_resp.json().get("detail", "Challenge verification failed")
                raise HTTPException(status_code=400, detail=detail)

            result = challenge_resp.json()
            paired_token = result["paired_token"]

            # Step 4: store trust relationship
            # Check for existing peer with same board_id
            existing = await db.execute(
                select(TrustedPeer).where(
                    TrustedPeer.board_id == data.board_id,
                    TrustedPeer.role == "agent"
                )
            )
            peer = existing.scalar_one_or_none()
            if peer:
                peer.ip = agent.ip
                peer.port = agent.port
                peer.version = agent.version
                peer.fingerprint = agent.fingerprint
                peer.paired_token_hash = pairing_service.hash_token(paired_token)
                peer.paired_at = datetime.now(timezone.utc)
                peer.last_seen = datetime.now(timezone.utc)
                peer.is_active = True
            else:
                peer = TrustedPeer(
                    board_id=data.board_id,
                    role="agent",
                    ip=agent.ip,
                    port=agent.port,
                    version=agent.version,
                    fingerprint=agent.fingerprint,
                    paired_token_hash=pairing_service.hash_token(paired_token),
                    is_active=True,
                )
                db.add(peer)

            await db.flush()
            mdns_service.mark_paired(data.board_id)
            await log_audit(db, admin, "pair_agent", "board", data.board_id, {
                "agent_ip": agent.ip, "fingerprint": agent.fingerprint
            })

            return {
                "success": True,
                "board_id": data.board_id,
                "agent_ip": agent.ip,
                "fingerprint": agent.fingerprint,
                "message": f"Agent {data.board_id} paired successfully",
            }

    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Cannot reach agent: {exc}")


@router.delete("/discovery/peers/{peer_id}")
async def unpair_peer(peer_id: str, admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    """Revoke trust for a paired peer."""
    result = await db.execute(select(TrustedPeer).where(TrustedPeer.id == peer_id))
    peer = result.scalar_one_or_none()
    if not peer:
        raise HTTPException(status_code=404, detail="Peer not found")

    peer.is_active = False
    await db.flush()
    await log_audit(db, admin, "unpair_agent", "board", peer.board_id)
    return {"success": True, "message": f"Peer {peer.board_id} unpaired"}


# ===== Agent endpoints (called by master during pairing) =====

@router.get("/agent/pair/code")
async def get_agent_pairing_code():
    """Get the current rotating pairing code (shown on agent kiosk screen)."""
    code, remaining = pairing_service.get_pairing_code()
    return {"code": code, "expires_in": remaining}


@router.post("/agent/pair/verify")
async def verify_pairing_code(data: PairVerifyRequest, request: Request):
    """Agent verifies the master's submitted pairing code and returns a challenge."""
    if not pairing_service.verify_code(data.code):
        raise HTTPException(status_code=403, detail="Invalid or expired pairing code")

    client_ip = request.client.host if request.client else data.master_ip
    nonce = pairing_service.create_challenge(data.master_board_id, client_ip)

    return {"nonce": nonce, "message": "Code verified. Complete the challenge."}


@router.post("/agent/pair/complete")
async def complete_pairing(
    data: ChallengeResponseRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Agent verifies the challenge response and issues a paired token."""
    client_ip = request.client.host if request.client else "0.0.0.0"

    if not pairing_service.verify_challenge_response(
        nonce=data.nonce,
        signature=data.signature,
        master_fingerprint=data.master_fingerprint,
        master_ip=client_ip,
    ):
        raise HTTPException(status_code=403, detail="Challenge verification failed")

    # Issue paired token
    paired_token = pairing_service.generate_paired_token()

    # Store trusted master
    existing = await db.execute(
        select(TrustedPeer).where(
            TrustedPeer.board_id == data.master_board_id,
            TrustedPeer.role == "master"
        )
    )
    peer = existing.scalar_one_or_none()
    if peer:
        peer.ip = client_ip
        peer.fingerprint = data.master_fingerprint
        peer.paired_token_hash = pairing_service.hash_token(paired_token)
        peer.paired_at = datetime.now(timezone.utc)
        peer.last_seen = datetime.now(timezone.utc)
        peer.is_active = True
    else:
        peer = TrustedPeer(
            board_id=data.master_board_id,
            role="master",
            ip=client_ip,
            fingerprint=data.master_fingerprint,
            paired_token_hash=pairing_service.hash_token(paired_token),
            is_active=True,
        )
        db.add(peer)

    await db.flush()

    logger.info(f"Pairing complete: master {data.master_board_id} from {client_ip}")

    return {
        "paired_token": paired_token,
        "message": "Pairing successful",
    }
