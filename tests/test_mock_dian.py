"""
QA Test: Mock DIAN server integration.
Tests that the backend client can transmit to the mock server and get valid responses.
"""
import os
import subprocess
import time
import signal
from pathlib import Path

import pytest

from tests.conftest import (
    SAMPLE_NIT_EMISOR, SAMPLE_RAZON_EMISOR, SAMPLE_NIT_ADQUIRIENTE,
    SAMPLE_RAZON_ADQUIRIENTE, SAMPLE_ITEMS, SAMPLE_TOTAL_BASE,
    SAMPLE_IVA, SAMPLE_TOTAL,
)


# ── Fixture: start/stop mock server ──────────────────────────────────────

MOCK_PORT = 8082  # different from default to avoid conflicts


@pytest.fixture(scope="module")
def mock_dian_server():
    """Start the mock DIAN server for the duration of the test module."""
    import subprocess
    import time
    import signal

    script = Path(__file__).resolve().parent.parent / "backend" / "run_mock_dian.py"
    proc = subprocess.Popen(
        ["python3", str(script), "--port", str(MOCK_PORT), "--delay", "0.1"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)
    yield
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=5)


# ── Tests ────────────────────────────────────────────────────────────────

def test_mock_server_health(mock_dian_server):
    """Mock server health endpoint responds."""
    import httpx
    resp = httpx.get(f"http://localhost:{MOCK_PORT}/health", timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_mock_transmit_factura_aceptada(mock_dian_server):
    """Transmit a valid invoice XML to mock server — expect aceptada."""
    import httpx
    import base64
    from datetime import datetime
    from decimal import Decimal
    from app.dian.xml_generator import generar_xml_factura

    # Generate a real UBL 2.1 invoice
    xml_bytes = generar_xml_factura(
        prefijo="TEST",
        consecutivo=1,
        fecha_emision=datetime(2026, 6, 23, 14, 30, 0),
        nit_emisor=SAMPLE_NIT_EMISOR,
        razon_social_emisor=SAMPLE_RAZON_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        razon_social_adquiriente=SAMPLE_RAZON_ADQUIRIENTE,
        items=SAMPLE_ITEMS,
        total_base=Decimal(str(SAMPLE_TOTAL_BASE)),
        iva=Decimal(str(SAMPLE_IVA)),
        total=Decimal(str(SAMPLE_TOTAL)),
        cufe="MOCK" + "A" * 92,
    )

    xml_b64 = base64.b64encode(xml_bytes).decode("utf-8")

    soap_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:wcf="http://wcf.dian.colombia">
  <soap:Body>
    <wcf:SendBillSync>
      <wcf:fileName>factura_test.xml</wcf:fileName>
      <wcf:contentFile>{xml_b64}</wcf:contentFile>
      <wcf:testSetId>123456</wcf:testSetId>
    </wcf:SendBillSync>
  </soap:Body>
</soap:Envelope>"""

    resp = httpx.post(
        f"http://localhost:{MOCK_PORT}/WcfDianCustomerServices.svc",
        content=soap_request,
        headers={"Content-Type": "text/xml; charset=utf-8"},
        timeout=10,
    )

    assert resp.status_code == 200

    # Parse response
    from xml.etree import ElementTree as ET
    root = ET.fromstring(resp.text)
    ns = {"wcf": "http://wcf.dian.colombia"}
    sc = root.find(".//wcf:StatusCode", ns)
    assert sc is not None
    assert sc.text.strip() == "00"

    cufe = root.find(".//wcf:UUID", ns)
    assert cufe is not None
    assert len(cufe.text.strip()) == 96


def test_mock_transmit_factura_rechazada(mock_dian_server):
    """Configure mock to reject — expect rechazada."""
    import httpx

    # Configure mock to reject
    resp = httpx.post(
        f"http://localhost:{MOCK_PORT}/admin/config",
        params={"force_reject": True},
        timeout=5,
    )
    assert resp.status_code == 200

    # Send invoice (any content, even invalid)
    soap_request = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:wcf="http://wcf.dian.colombia">
  <soap:Body>
    <wcf:SendBillSync>
      <wcf:fileName>test.xml</wcf:fileName>
      <wcf:contentFile>aW52YWxpZCBYTUw=</wcf:contentFile>
      <wcf:testSetId>123</wcf:testSetId>
    </wcf:SendBillSync>
  </soap:Body>
</soap:Envelope>"""

    resp = httpx.post(
        f"http://localhost:{MOCK_PORT}/WcfDianCustomerServices.svc",
        content=soap_request,
        headers={"Content-Type": "text/xml; charset=utf-8"},
        timeout=10,
    )

    assert resp.status_code == 200

    from xml.etree import ElementTree as ET
    root = ET.fromstring(resp.text)
    ns = {"wcf": "http://wcf.dian.colombia"}
    sc = root.find(".//wcf:StatusCode", ns)
    # Should be 01 (rechazada) because force_reject is on
    assert sc.text.strip() == "01"

    # Reset mock
    httpx.post(
        f"http://localhost:{MOCK_PORT}/admin/config",
        params={"force_reject": False},
        timeout=5,
    )


def test_mock_client_function():
    """Test _transmitir_mock function directly (without server)."""
    from unittest.mock import patch, MagicMock
    import httpx
    from app.dian.client import _transmitir_mock

    xml_bytes = b"<fake>invoice</fake>"
    expected_cufe = "MOCK" + "B" * 92

    with patch.object(httpx, "post") as mock_post:
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.text = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:wcf="http://wcf.dian.colombia">
  <soap:Body>
    <SendBillSyncResponse xmlns="http://wcf.dian.colombia">
      <SendBillSyncResult>
        <StatusCode>00</StatusCode>
        <UUID>{expected_cufe}</UUID>
        <DocumentKey>{expected_cufe}</DocumentKey>
      </SendBillSyncResult>
    </SendBillSyncResponse>
  </soap:Body>
</soap:Envelope>"""
        mock_post.return_value = mock_response

        result = _transmitir_mock(xml_bytes)

        assert result["status"] == "aceptada"
        assert result["cufe"] is not None
        assert result["cufe"] == expected_cufe
        assert len(result["cufe"]) == 96


def test_is_mock_flag():
    """_is_mock() returns True when DIAN_ENVIRONMENT=mock."""
    from app.dian.client import _is_mock
    from config import settings

    original = settings.dian_environment
    try:
        settings.dian_environment = "mock"
        assert _is_mock() is True

        settings.dian_environment = "test"
        assert _is_mock() is False

        settings.dian_environment = "prod"
        assert _is_mock() is False
    finally:
        settings.dian_environment = original
