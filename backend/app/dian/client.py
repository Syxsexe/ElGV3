"""
DIAN SOAP Web Service Client
Comunicación con servicios web de la DIAN para facturación electrónica.
Soporta modo mock para pruebas locales sin conexión a DIAN real.
"""

import logging
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

MOCK_BASE_URL = "http://localhost:8081"


def _is_mock() -> bool:
    """Returns True when DIAN_ENVIRONMENT is 'mock'."""
    return settings.dian_environment == "mock"


def _get_service_url() -> str:
    """Returns the appropriate DIAN web service URL based on environment."""
    if _is_mock():
        return f"{MOCK_BASE_URL}/WcfDianCustomerServices.svc"
    if settings.dian_environment == "test":
        return settings.dian_test_url
    return settings.dian_prod_url


def transmitir_factura(xml_signed: bytes, test_set_id: str | None = None) -> dict:
    """
    Sends a signed electronic invoice XML to DIAN for validation.

    Args:
        xml_signed: The complete signed XML (bytes)
        test_set_id: Identificador del Juego de Pruebas (habilitación). Si es None
            se toma de DIAN_TEST_SET_ID (.env); como último recurso, "123456".

    Returns:
        Dict with DIAN response:
        - status: "aceptada" | "rechazada" | "error"
        - cufe: str (if accepted)
        - error_message: str (if rejected)
        - raw_response: str
    """
    if test_set_id is None:
        test_set_id = settings.dian_test_set_id or "123456"

    if _is_mock():
        return _transmitir_mock(xml_signed, test_set_id)

    import zeep
    from zeep import Client, Settings
    from zeep.transports import Transport
    from requests import Session
    from requests.adapters import HTTPAdapter

    try:
        session = Session()
        adapter = HTTPAdapter(max_retries=3)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        transport = Transport(session=session, timeout=30)
        client_settings = Settings(strict=False, xml_huge_tree=True)
        client = Client(_get_service_url(), transport=transport, settings=client_settings)

        xml_str = xml_signed.decode("utf-8")

        import base64
        xml_b64 = base64.b64encode(xml_signed).decode("utf-8")

        try:
            response = client.service.SendBillSync(
                fileName=f"factura_{test_set_id}.xml",
                contentFile=xml_b64,
                testSetId=test_set_id,
            )
        except Exception as soap_error:
            logger.warning(f"SendBillSync failed, trying SendBillAsync: {soap_error}")
            response = client.service.SendBillAsync(
                fileName=f"factura_{test_set_id}.xml",
                contentFile=xml_b64,
                testSetId=test_set_id,
            )

        return _parse_response(response, xml_str)

    except Exception as e:
        logger.error(f"Error transmitting to DIAN: {e}", exc_info=True)
        return {
            "status": "error",
            "cufe": None,
            "error_message": f"Error de conexión con DIAN: {e}",
            "raw_response": str(e),
        }


def _transmitir_mock(xml_signed: bytes, test_set_id: str = "123456") -> dict:
    """Send invoice to the local mock DIAN server via HTTP."""
    import base64
    import httpx

    xml_b64 = base64.b64encode(xml_signed).decode("utf-8")
    xml_str = xml_signed.decode("utf-8")

    soap_request = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:wcf="http://wcf.dian.colombia">
  <soap:Body>
    <wcf:SendBillSync>
      <wcf:fileName>factura_{test_set_id}.xml</wcf:fileName>
      <wcf:contentFile>{xml_b64}</wcf:contentFile>
      <wcf:testSetId>{test_set_id}</wcf:testSetId>
    </wcf:SendBillSync>
  </soap:Body>
</soap:Envelope>"""

    try:
        resp = httpx.post(
            f"{MOCK_BASE_URL}/WcfDianCustomerServices.svc",
            content=soap_request,
            headers={"Content-Type": "text/xml; charset=utf-8"},
            timeout=10,
        )

        if resp.status_code != 200:
            return {
                "status": "error",
                "error_message": f"Mock server error: HTTP {resp.status_code}",
                "raw_response": resp.text,
            }

        # Parse SOAP response
        return _parse_mock_response(resp.text, xml_str)

    except httpx.RequestError as e:
        return {
            "status": "error",
            "error_message": f"Mock server unreachable: {e}. "
                             f"Run: python backend/run_mock_dian.py",
            "raw_response": str(e),
        }


def _parse_mock_response(soap_xml: str, xml_str: str) -> dict:
    """Parse the mock DIAN SOAP XML response."""
    from xml.etree import ElementTree as ET

    result = {
        "status": "error",
        "cufe": None,
        "error_message": None,
        "raw_response": soap_xml,
    }

    try:
        root = ET.fromstring(soap_xml)
        ns = {
            "soap": "http://schemas.xmlsoap.org/soap/envelope/",
            "wcf": "http://wcf.dian.colombia",
        }

        status_code_el = root.find(".//wcf:StatusCode", ns)
        if status_code_el is None:
            status_code_el = root.find(".//StatusCode")

        if status_code_el is not None:
            code = status_code_el.text.strip()
            if code == "00":
                result["status"] = "aceptada"
                uuid_el = root.find(".//wcf:UUID", ns)
                if uuid_el is None:
                    uuid_el = root.find(".//UUID")
                if uuid_el is not None:
                    result["cufe"] = uuid_el.text.strip()
            else:
                result["status"] = "rechazada"
                desc_el = root.find(".//wcf:StatusDescription", ns)
                if desc_el is None:
                    desc_el = root.find(".//StatusDescription")
                if desc_el is not None:
                    result["error_message"] = desc_el.text.strip()
    except ET.ParseError as e:
        result["error_message"] = f"Error parsing mock response: {e}"

    return result


def _parse_response(response: Any, xml_str: str) -> dict:
    """
    Parses the SOAP response from DIAN.
    The response varies by operation and version.
    """
    result = {
        "status": "error",
        "cufe": None,
        "error_message": None,
        "raw_response": str(response),
    }

    try:
        if response is None:
            result["error_message"] = "No response from DIAN"
            return result

        # Response is typically a complex type with status code
        if hasattr(response, "StatusCode"):
            code = response.StatusCode
            if code == "00":
                result["status"] = "aceptada"
                if hasattr(response, "UUID"):
                    result["cufe"] = response.UUID
                elif hasattr(response, "DocumentKey"):
                    result["cufe"] = response.DocumentKey
            elif code in ("01", "02"):
                result["status"] = "rechazada"
                if hasattr(response, "StatusDescription"):
                    result["error_message"] = response.StatusDescription
                elif hasattr(response, "ErrorMessage"):
                    result["error_message"] = response.ErrorMessage
            else:
                result["status"] = "rechazada"
                result["error_message"] = f"DIAN status code: {code}"

        # Try to parse dict-like response
        elif isinstance(response, dict):
            if response.get("StatusCode") == "00":
                result["status"] = "aceptada"
                result["cufe"] = response.get("UUID") or response.get("DocumentKey")
            else:
                result["status"] = "rechazada"
                result["error_message"] = response.get("StatusDescription",
                                                        str(response))

    except Exception as e:
        result["error_message"] = f"Error parsing DIAN response: {e}"

    return result


def consultar_estado_dian(cufe: str) -> dict:
    """
    Queries DIAN for the status of a previously submitted document.
    """
    try:
        client = _create_client()
        response = client.service.GetStatus(cufe=cufe)
        return {"status": str(response), "cufe": cufe}
    except Exception as e:
        return {"status": "error", "error": str(e), "cufe": cufe}
