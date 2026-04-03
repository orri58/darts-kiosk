"""
Pydantic Schemas for the Darts Kiosk API
"""
from datetime import datetime
from typing import List, Optional, Union, Any
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str

class PinLoginRequest(BaseModel):
    pin: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "staff"
    display_name: Optional[str] = None
    pin: Optional[str] = None

class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    pin: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    username: str
    role: str
    display_name: Optional[str]
    is_active: bool
    created_at: datetime

class BoardCreate(BaseModel):
    board_id: str
    name: str
    location: Optional[str] = None
    autodarts_target_url: Optional[str] = None
    agent_api_base_url: Optional[str] = None

class BoardUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    autodarts_target_url: Optional[str] = None
    agent_api_base_url: Optional[str] = None
    status: Optional[str] = None

class BoardResponse(BaseModel):
    id: str
    board_id: str
    name: str
    location: Optional[str]
    autodarts_target_url: Optional[str] = None
    agent_api_base_url: Optional[str] = None
    status: str
    last_heartbeat_at: Optional[datetime]
    is_master: bool
    created_at: datetime

class UnlockRequest(BaseModel):
    pricing_mode: str = "per_player"
    game_type: Optional[str] = None
    credits: Optional[int] = None
    minutes: Optional[int] = None
    players_count: int = 0
    price_total: float = 0.0

class ExtendRequest(BaseModel):
    credits: Optional[int] = None
    minutes: Optional[int] = None
    price_total: float = 0.0

class StartGameRequest(BaseModel):
    game_type: str
    players: List[str]

class EndGameRequest(BaseModel):
    winner: Optional[str] = None
    scores: Optional[dict] = None
    highest_throw: Optional[int] = None
    best_checkout: Optional[int] = None

class SessionResponse(BaseModel):
    id: str
    board_id: str
    pricing_mode: str
    game_type: Optional[str]
    credits_total: int
    credits_remaining: int
    minutes_total: int
    price_total: float
    started_at: datetime
    expires_at: Optional[datetime]
    ended_at: Optional[datetime]
    players_count: int
    players: List[str]
    status: str

class AgentStatusResponse(BaseModel):
    board_id: str
    status: str
    current_session: Optional[SessionResponse]
    mode: str

class SettingsUpdate(BaseModel):
    value: Union[dict, list]  # Allow both dict and list for flexible settings storage

class AuditLogResponse(BaseModel):
    id: str
    username: Optional[str]
    action: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    details: Optional[dict]
    created_at: datetime

class RevenueResponse(BaseModel):
    date: str
    total: float
    session_count: int
    by_board: dict
