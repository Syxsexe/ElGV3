"""
modules/dian_client.py — El G POS
HTTP client to communicate with the cloud backend for DIAN electronic invoicing.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any

import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "dian_config.json"

_DEFAULT_CONFIG = {
    "backend_url": "http://localhost:8000",
    "client_id": "",
    "client_secret": "",
}

_config: dict | None = None
_token: str | None = None
_token_expires: datetime | None = None


# ── Config ───────────────────────────────────────────────────────────────────

def load_config() -> dict:
    global _config
    if _config is not None:
        return _config
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            _config = json.load(f)
    else:
        _config = dict(_DEFAULT_CONFIG)
        save_config()
    return _config


def save_config():
    global _config
    if _config is None:
        _config = dict(_DEFAULT_CONFIG)
    with open(CONFIG_FILE, "w") as f:
        json.dump(_config, f, indent=2)


def get_backend_url() -> str:
    return load_config().get("backend_url", _DEFAULT_CONFIG["backend_url"])


def set_backend_url(url: str):
    cfg = load_config()
    cfg["backend_url"] = url.rstrip("/")
    save_config()


def set_credentials(client_id: str, client_secret: str):
    cfg = load_config()
    cfg["client_id"] = client_id
    cfg["client_secret"] = client_secret
    save_config()


def is_configured() -> bool:
    cfg = load_config()
    return bool(cfg.get("client_id") and cfg.get("client_secret"))


# ── Authentication ───────────────────────────────────────────────────────────

async def _login() -> str | None:
    global _token, _token_expires
    cfg = load_config()
    if not cfg["client_id"] or not cfg["client_secret"]:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{get_backend_url()}/api/v1/auth/login",
                json={
                    "client_id": cfg["client_id"],
                    "client_secret": cfg["client_secret"],
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                _token = data["access_token"]
                return _token
    except httpx.RequestError:
        pass
    return None


async def _ensure_token() -> str | None:
    if _token is None:
        return await _login()
    return _token


def _get_headers() -> dict:
    token = _token
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


# ── Sync Operations ──────────────────────────────────────────────────────────

async def sync_venta(
    venta_data: dict,
    uuid_operacion: str,
) -> dict:
    """
    Sends a sale to the backend for DIAN electronic invoicing.
    Returns the backend response (CUFE, QR, status).
    """
    token = await _ensure_token()
    if not token:
        return {"error": "No authentication configured", "codigo": "AUTH_ERROR"}

    payload = {
        "uuid_operacion": uuid_operacion,
        **venta_data,
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{get_backend_url()}/api/v1/sync/venta",
                json=payload,
                headers=_get_headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 401:
                _token = None
                return await sync_venta(venta_data, uuid_operacion)
            else:
                return {
                    "error": f"Backend error: {resp.status_code}",
                    "detalle": resp.text,
                    "codigo": "BACKEND_ERROR",
                }
    except httpx.RequestError as e:
        return {
            "error": f"Connection error: {e}",
            "codigo": "CONNECTION_ERROR",
        }


async def sync_cierre_caja(sesion_data: dict, uuid_operacion: str) -> dict:
    """Sends cash session closure and triggers DEE POS batch transmission."""
    token = await _ensure_token()
    if not token:
        return {"error": "No authentication configured", "codigo": "AUTH_ERROR"}

    payload = {
        "uuid_operacion": uuid_operacion,
        **sesion_data,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{get_backend_url()}/api/v1/sync/caja/cierre",
                json=payload,
                headers=_get_headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Backend error: {resp.status_code}", "codigo": "BACKEND_ERROR"}
    except httpx.RequestError as e:
        return {"error": f"Connection error: {e}", "codigo": "CONNECTION_ERROR"}


async def consultar_estado(uuid_operacion: str) -> dict:
    """Checks the status of a previously synced operation."""
    token = await _ensure_token()
    if not token:
        return {"error": "Not authenticated"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{get_backend_url()}/api/v1/sync/estado/{uuid_operacion}",
                headers=_get_headers(),
            )
            if resp.status_code == 200:
                return resp.json()
            return {"estado": "desconocido"}
    except httpx.RequestError:
        return {"estado": "sin_conexion"}


async def health_check() -> dict:
    """Checks if the backend is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{get_backend_url()}/health")
            if resp.status_code == 200:
                return resp.json()
            return {"status": "error"}
    except httpx.RequestError:
        return {"status": "unreachable"}


# ── Synchronous helpers for UI integration ───────────────────────────────────

def sync_sync_venta(venta_data: dict, uuid_operacion: str) -> dict:
    """Synchronous wrapper for sync_venta (for use in Tkinter event loop)."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, sync_venta(venta_data, uuid_operacion))
            return future.result()
    else:
        return loop.run_until_complete(sync_venta(venta_data, uuid_operacion))


def sync_health_check() -> dict:
    """Synchronous wrapper for health_check."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(health_check())
