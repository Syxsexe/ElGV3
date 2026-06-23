"""
tests/conftest.py — Shared fixtures for QA tests.
"""
import sys
import os
from pathlib import Path

# Add project root and backend to path so imports work
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(BACKEND))

# Disable PostgreSQL connection and set test environment before any backend imports
os.environ["DIAN_ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test.db"  # won't be used but avoids crash
os.environ["JWT_SECRET"] = "test-secret"

# Mock the PostgreSQL database for route tests
from unittest.mock import MagicMock, AsyncMock


# ── Sample test data ──────────────────────────────────────────────────────

SAMPLE_NIT_EMISOR = "9001234567"
SAMPLE_RAZON_EMISOR = "EL G TIENDA TCG SAS"
SAMPLE_NIT_ADQUIRIENTE = "8009876543"
SAMPLE_RAZON_ADQUIRIENTE = "COMPRADOR EJEMPLO SAS"
SAMPLE_CLAVE_TECNICA = "6a7b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d"
SAMPLE_PREFIJO = "SETP"
SAMPLE_CONSECUTIVO = 1
SAMPLE_TOTAL_BASE = 84033.61
SAMPLE_IVA = 15966.39
SAMPLE_TOTAL = 100000.00

SAMPLE_ITEMS = [
    {"nombre": "PRODUCTO A", "cantidad": 2, "precio_unit": 25000.00,
     "subtotal": 50000.00, "codigo": "P001"},
    {"nombre": "PRODUCTO B", "cantidad": 1, "precio_unit": 34033.61,
     "subtotal": 34033.61, "codigo": "P002"},
]
