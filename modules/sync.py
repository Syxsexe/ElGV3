"""
modules/sync.py — El G POS
Synchronization manager: queues local operations and syncs with cloud backend.
Supports offline mode with automatic retry when connection is restored.
"""

import json
import uuid as uuid_lib
from pathlib import Path
from datetime import datetime
from typing import Any

from modules.dian_client import (
    sync_venta, sync_cierre_caja, health_check, is_configured,
)

from paths import ruta_datos
SYNC_QUEUE_FILE = ruta_datos("sync_queue.json")


class SyncManager:
    """
    Manages the pending operations queue and coordinates sync with the cloud backend.
    Each operation has a unique UUID for idempotency.
    """

    def __init__(self):
        self._queue: list[dict] = []
        self._load_queue()

    # ── Queue persistence ─────────────────────────────────────────────────

    def _load_queue(self):
        if SYNC_QUEUE_FILE.exists():
            try:
                with open(SYNC_QUEUE_FILE) as f:
                    self._queue = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._queue = []
        else:
            self._queue = []

    def _save_queue(self):
        with open(SYNC_QUEUE_FILE, "w") as f:
            json.dump(self._queue, f, indent=2, default=str)

    # ── Queue management ──────────────────────────────────────────────────

    def enqueue(self, entidad_tipo: str, entidad_id_local: int,
                accion: str, payload: dict) -> str:
        """
        Adds an operation to the pending queue.
        Returns the operation UUID.
        """
        uuid_op = str(uuid_lib.uuid4())
        entry = {
            "uuid": uuid_op,
            "entidad_tipo": entidad_tipo,
            "entidad_id_local": entidad_id_local,
            "accion": accion,
            "payload": payload,
            "estado": "pendiente",
            "creado_en": datetime.now().isoformat(),
            "intentos": 0,
            "ultimo_error": None,
        }
        self._queue.append(entry)
        self._save_queue()
        return uuid_op

    def mark_synced(self, uuid_op: str, resultado: dict = None):
        for entry in self._queue:
            if entry["uuid"] == uuid_op:
                entry["estado"] = "sincronizado"
                entry["resultado"] = resultado
                entry["sincronizado_en"] = datetime.now().isoformat()
                break
        self._save_queue()

    def mark_error(self, uuid_op: str, error: str):
        for entry in self._queue:
            if entry["uuid"] == uuid_op:
                entry["estado"] = "error"
                entry["ultimo_error"] = error
                entry["intentos"] += 1
                break
        self._save_queue()

    def get_pending(self) -> list[dict]:
        return [e for e in self._queue if e["estado"] == "pendiente"]

    def get_failed(self) -> list[dict]:
        return [e for e in self._queue if e["estado"] == "error"]

    def get_all(self) -> list[dict]:
        return list(self._queue)

    def clear_synced(self):
        self._queue = [e for e in self._queue if e["estado"] != "sincronizado"]
        self._save_queue()

    def pending_count(self) -> int:
        return len(self.get_pending())

    # ── Sync execution ────────────────────────────────────────────────────

    async def process_venta(self, venta_data: dict) -> dict:
        """
        Enqueues a sale and attempts immediate sync.
        If the backend is unreachable, stays in queue for later retry.
        Returns the sync result.
        """
        uuid_op = self.enqueue(
            entidad_tipo="venta",
            entidad_id_local=venta_data.get("venta_id", 0),
            accion="crear",
            payload=venta_data,
        )

        if not is_configured():
            return {
                "uuid": uuid_op,
                "estado": "pendiente",
                "mensaje": "Backend no configurado. La operación quedó en cola.",
            }

        try:
            result = await sync_venta(venta_data, uuid_op)
            # Éxito de sincronización = el backend respondió sin error de
            # transporte. Puede no traer CUFE (factura local, o DIAN en proceso).
            if "error" in result:
                error_msg = result.get("error", "Error desconocido")
                self.mark_error(uuid_op, error_msg)
                return {"uuid": uuid_op, "estado": "error", "error": error_msg}
            self.mark_synced(uuid_op, result)
            return {"uuid": uuid_op, "estado": "sincronizado", **result}
        except Exception as e:
            self.mark_error(uuid_op, str(e))
            return {"uuid": uuid_op, "estado": "error", "error": str(e)}

    async def process_cierre_caja(self, sesion_data: dict) -> dict:
        """Enqueues cash session closure and syncs DEE POS batch."""
        uuid_op = self.enqueue(
            entidad_tipo="caja",
            entidad_id_local=sesion_data.get("sesion_id", 0),
            accion="cerrar",
            payload=sesion_data,
        )

        if not is_configured():
            return {"uuid": uuid_op, "estado": "pendiente"}

        try:
            result = await sync_cierre_caja(sesion_data, uuid_op)
            self.mark_synced(uuid_op, result)
            return {"uuid": uuid_op, "estado": "sincronizado", **result}
        except Exception as e:
            self.mark_error(uuid_op, str(e))
            return {"uuid": uuid_op, "estado": "error", "error": str(e)}

    def retry_failed(self) -> list[dict]:
        """Resets all failed operations back to pending for retry."""
        for entry in self._queue:
            if entry["estado"] == "error":
                entry["estado"] = "pendiente"
        self._save_queue()
        return self.get_pending()

    # ── Health ────────────────────────────────────────────────────────────

    async def check_connection(self) -> dict:
        return await health_check()


# Singleton instance
_sync_manager: SyncManager | None = None


def get_sync_manager() -> SyncManager:
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SyncManager()
    return _sync_manager
