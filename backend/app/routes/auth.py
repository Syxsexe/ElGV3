import uuid
from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

_oauth2_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    client_id: str
    client_secret: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


CLIENTS: dict[str, str] = {}


def configure_clients(clients: dict[str, str]):
    CLIENTS.clear()
    CLIENTS.update(clients)


def create_access_token(client_id: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
    payload = {
        "sub": client_id,
        "jti": str(uuid.uuid4()),
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    expected = CLIENTS.get(req.client_id)
    if not expected or expected != req.client_secret:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(req.client_id)
    return LoginResponse(
        access_token=token,
        expires_in=settings.jwt_expiration_hours * 3600,
    )


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_oauth2_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return verify_token(credentials.credentials)
