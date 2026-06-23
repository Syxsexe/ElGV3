"""
Mock DIAN SOAP Server
Simula el servicio web de la DIAN (SendBillSync) para pruebas locales.
Corre como servidor FastAPI independiente en http://localhost:8081.
"""
import base64
import hashlib
import logging
import uuid as uuid_lib
from datetime import datetime
from decimal import Decimal
from xml.etree import ElementTree as ET

from fastapi import FastAPI, Request
from fastapi.responses import Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock-dian")

app = FastAPI(title="Mock DIAN — Habilitación")

# ── Configurable behavior ──────────────────────────────────────────────
MOCK_CLAVE_TECNICA = "mock-clave-tecnica-0000000000000"
FORCE_REJECT = False          # set True to simulate rejection
FORCE_CONTINGENCY = False     # set True to simulate contingency
SIMULATE_DELAY = 0.5          # seconds delay before responding

# ── SOAP XML parsing ──────────────────────────────────────────────────

SOAP_NS = {
    "soap": "http://schemas.xmlsoap.org/soap/envelope/",
    "wcf": "http://wcf.dian.colombia",
}


def _parse_soap_request(body: str) -> dict:
    """Extract fileName, contentFile, testSetId from SOAP request."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return {}

    # Try namespaced
    ns = {
        "soap": "http://schemas.xmlsoap.org/soap/envelope/",
        "wcf": "http://wcf.dian.colombia",
    }
    send_bill = (
        root.find(".//wcf:SendBillSync", ns)
        or root.find(".//SendBillSync")
    )
    if send_bill is None:
        send_bill = (
            root.find(".//wcf:SendBillAsync", ns)
            or root.find(".//SendBillAsync")
        )

    if send_bill is None:
        return {}

    def _get(tag):
        el = send_bill.find(tag)
        if el is not None:
            return el.text or ""
        el = send_bill.find(f"wcf:{tag}", ns)
        return el.text if el is not None and el.text else ""

    return {
        "fileName": _get("fileName"),
        "contentFile": _get("contentFile"),
        "testSetId": _get("testSetId"),
    }


# ── XML Invoice parsing ───────────────────────────────────────────────

def _parse_invoice_xml(xml_str: str) -> dict:
    """Extract key fields from UBL 2.1 invoice XML."""
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return {}

    # Namespace agnostic — search by local name
    def _find_text(tag):
        for el in root.iter():
            if el.tag.endswith("}" + tag) or el.tag == tag:
                if el.text and el.text.strip():
                    return el.text.strip()
        return ""

    # Extract from known paths
    inv_id = _find_text("ID")
    cbc_ns = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"

    # Find NIT emisor
    nit_emisor = ""
    for el in root.iter():
        if el.tag.endswith("}PartyIdentification"):
            child = el.find(f"{cbc_ns}ID")
            if child is not None and child.text:
                nit_emisor = child.text.strip()
                break

    # Find total
    total = "0"
    for el in root.iter():
        if el.tag.endswith("}PayableAmount"):
            if el.text:
                total = el.text.strip()
            break

    fecha = _find_text("IssueDate")

    return {
        "numero": inv_id,
        "nit_emisor": nit_emisor,
        "total": total,
        "fecha": fecha,
    }


# ── Response builders ─────────────────────────────────────────────────

def _build_soap_response(status: str, cufe: str = "", error_msg: str = "") -> str:
    """Build a DIAN-like SOAP XML response."""
    if status == "aceptada":
        status_code = "00"
        description = "Factura recibida correctamente"
    elif status == "rechazada":
        status_code = "01"
        description = error_msg or "Error en la estructura del XML"
    else:
        status_code = "99"
        description = error_msg or "Error interno del procesador"

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <soap:Body>
    <SendBillSyncResponse xmlns="http://wcf.dian.colombia">
      <SendBillSyncResult>
        <StatusCode>{status_code}</StatusCode>
        <StatusDescription>{description}</StatusDescription>
        <StatusMessage>Proceso exitoso</StatusMessage>
        <UUID>{cufe}</UUID>
        <DocumentKey>{cufe}</DocumentKey>
        <ResponseDate>{datetime.now().strftime("%Y-%m-%dT%H:%M:%S")}</ResponseDate>
      </SendBillSyncResult>
    </SendBillSyncResponse>
  </soap:Body>
</soap:Envelope>"""


def _generate_mock_cufe(invoice_xml: str) -> str:
    """Generate a deterministic mock CUFE from invoice content."""
    raw = invoice_xml + MOCK_CLAVE_TECNICA + datetime.now().isoformat()
    return hashlib.sha384(raw.encode("utf-8")).hexdigest().upper()[:96]


# ── Validation ────────────────────────────────────────────────────────

def _validate_invoice(xml_str: str) -> list[str]:
    """Basic validation of invoice XML structure. Returns list of issues."""
    issues = []

    if not xml_str.strip():
        issues.append("XML vacío")
        return issues

    required = ["UBLVersionID", "InvoiceTypeCode", "ID", "IssueDate",
                "AccountingSupplierParty", "AccountingCustomerParty",
                "LegalMonetaryTotal", "PayableAmount"]

    for tag in required:
        if tag not in xml_str:
            issues.append(f"Falta elemento requerido: {tag}")

    return issues


# ── Routes ────────────────────────────────────────────────────────────

@app.post("/WcfDianCustomerServices.svc")
async def send_bill_sync(request: Request):
    """Mock DIAN SendBillSync endpoint (SOAP)."""
    import asyncio
    if SIMULATE_DELAY:
        await asyncio.sleep(SIMULATE_DELAY)

    body = await request.body()
    body_str = body.decode("utf-8")

    logger.info("=" * 50)
    logger.info("📨 RECIBIDA FACTURA PARA VALIDACIÓN DIAN (MOCK)")
    logger.info("-" * 50)

    params = _parse_soap_request(body_str)

    if not params.get("contentFile"):
        logger.warning("⚠ No contentFile in SOAP request")
        return Response(
            content=_build_soap_response("rechazada", error_msg="No se recibió contenido XML"),
            media_type="text/xml",
        )

    # Decode base64 XML
    try:
        invoice_xml = base64.b64decode(params["contentFile"]).decode("utf-8")
    except Exception:
        return Response(
            content=_build_soap_response("rechazada", error_msg="Error decodificando base64"),
            media_type="text/xml",
        )

    # Validate
    issues = _validate_invoice(invoice_xml)
    if issues:
        logger.warning(f"⚠ Validación fallida: {issues}")
        return Response(
            content=_build_soap_response("rechazada", error_msg="; ".join(issues)),
            media_type="text/xml",
        )

    # Extract info for display
    info = _parse_invoice_xml(invoice_xml)
    logger.info(f"  Número: {info.get('numero', '?')}")
    logger.info(f"  NIT Emisor: {info.get('nit_emisor', '?')}")
    logger.info(f"  Total: ${info.get('total', '?')}")
    logger.info(f"  Fecha: {info.get('fecha', '?')}")
    logger.info(f"  Archivo: {params.get('fileName', '?')}")
    logger.info(f"  TestSetId: {params.get('testSetId', '?')}")

    # Decide status
    if FORCE_REJECT:
        status = "rechazada"
        cufe = ""
        error_msg = "Error forzado por configuración mock"
        logger.warning(f"  ❌ RECHAZADA (forzado)")
    elif FORCE_CONTINGENCY:
        # Contingency means we accept but mark as contingency
        cufe = _generate_mock_cufe(invoice_xml)
        status = "aceptada"
        error_msg = ""
        logger.info(f"  ⚠ ACEPTADA EN CONTINGENCIA")
    else:
        cufe = _generate_mock_cufe(invoice_xml)
        status = "aceptada"
        error_msg = ""
        logger.info(f"  ✅ ACEPTADA - CUFE: {cufe[:20]}...")

    logger.info("=" * 50)

    response_xml = _build_soap_response(status, cufe, error_msg)
    return Response(content=response_xml, media_type="text/xml")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mock-dian", "mode": "testing"}


@app.get("/")
async def root():
    return {
        "name": "Mock DIAN — Habilitación",
        "version": "1.0",
        "endpoints": {
            "POST /WcfDianCustomerServices.svc": "SendBillSync (SOAP)",
            "GET /health": "Health check",
            "POST /admin/config": "Configure behavior",
        },
        "config": {
            "FORCE_REJECT": FORCE_REJECT,
            "FORCE_CONTINGENCY": FORCE_CONTINGENCY,
            "SIMULATE_DELAY": SIMULATE_DELAY,
        },
    }


@app.post("/admin/config")
async def set_config(
    force_reject: bool = False,
    force_contingency: bool = False,
    simulate_delay: float = 0.5,
):
    """Dynamically configure mock behavior."""
    global FORCE_REJECT, FORCE_CONTINGENCY, SIMULATE_DELAY
    FORCE_REJECT = force_reject
    FORCE_CONTINGENCY = force_contingency
    SIMULATE_DELAY = simulate_delay
    logger.info(f"Mock config updated: reject={FORCE_REJECT}, "
                f"contingency={FORCE_CONTINGENCY}, delay={SIMULATE_DELAY}s")
    return {
        "status": "ok",
        "config": {
            "FORCE_REJECT": FORCE_REJECT,
            "FORCE_CONTINGENCY": FORCE_CONTINGENCY,
            "SIMULATE_DELAY": SIMULATE_DELAY,
        },
    }


@app.get("/admin/invoices")
async def list_invoices():
    """Return count of processed invoices (in-memory, simplified)."""
    return {"message": "Invoices logged to stdout. Use a database for persistence."}


if __name__ == "__main__":
    import uvicorn

    print("╔══════════════════════════════════════════════╗")
    print("║      MOCK DIAN — Servicio de Pruebas        ║")
    print("╠══════════════════════════════════════════════╣")
    print("║  Endpoint: /WcfDianCustomerServices.svc     ║")
    print("║  Health:   /health                          ║")
    print("║  Config:   POST /admin/config               ║")
    print("╚══════════════════════════════════════════════╝")
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")
