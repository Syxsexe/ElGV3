"""
DIAN Contingency Mode Manager
Handles invoice generation when DIAN services are unavailable.
"""

import uuid as uuid_lib
from datetime import datetime
from enum import Enum
from typing import Any


class ContingencyReason(Enum):
    UNAVAILABLE = "01"
    MAINTENANCE = "02"
    CONNECTIVITY = "03"
    OTHER = "04"


class ContingencyManager:
    """
    Manages contingency mode for DIAN electronic invoicing.
    In contingency mode, invoices are generated locally and stored
    for later transmission when DIAN services are restored.
    """

    def __init__(self, backend_url: str = ""):
        self._active: bool = False
        self._reason: ContingencyReason | None = None
        self._started_at: datetime | None = None
        self._pending: list[dict] = []
        self._backend_url = backend_url

    @property
    def is_active(self) -> bool:
        return self._active

    def start_contingency(self, reason: ContingencyReason = ContingencyReason.UNAVAILABLE):
        """Activates contingency mode."""
        if self._active:
            return
        self._active = True
        self._reason = reason
        self._started_at = datetime.now()
        print(f"⚠ Contingency STARTED: {reason.value} at {self._started_at.isoformat()}")

    def end_contingency(self) -> list[dict]:
        """Deactivates contingency mode and returns pending documents for transmission."""
        if not self._active:
            return []
        self._active = False
        pending = list(self._pending)
        print(f"✓ Contingency ENDED. {len(pending)} documents queued for transmission.")
        self._pending = []
        return pending

    def add_pending(self, document: dict):
        """Adds a document generated during contingency."""
        document["_contingency_id"] = str(uuid_lib.uuid4())
        document["_contingency_date"] = datetime.now().isoformat()
        document["_contingency_reason"] = self._reason.value if self._reason else "01"
        self._pending.append(document)

    def get_pending_count(self) -> int:
        return len(self._pending)

    def clear_pending(self, transmitted_ids: list[str]):
        """Removes successfully transmitted documents from pending list."""
        self._pending = [
            d for d in self._pending
            if d.get("_contingency_id") not in transmitted_ids
        ]


# Singleton
_contingency: ContingencyManager | None = None


def get_contingency_manager(backend_url: str = "") -> ContingencyManager:
    global _contingency
    if _contingency is None:
        _contingency = ContingencyManager(backend_url)
    return _contingency
