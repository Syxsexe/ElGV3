"""
DIAN SOAP Web Service Client
Comunicación con servicios web de la DIAN para facturación electrónica.
"""

import logging
from typing import Any

import zeep
from zeep import Client, Settings
from zeep.transports import Transport
from requests import Session
from requests.adapters import HTTPAdapter

from config import settings

logger = logging.getLogger(__name__)


def _get_service_url() -> str:
    """Returns the appropriate DIAN web service URL based on environment."""
    if settings.dian_environment == "test":
        return settings.dian_test_url
    return settings.dian_prod_url


def _create_client() -> Client:
    """Creates a zeep SOAP client for DIAN web services."""
    session = Session()
    adapter = HTTPAdapter(max_retries=3)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    transport = Transport(session=session, timeout=30)
    client_settings = Settings(strict=False, xml_huge_tree=True)

    wsdl_url = _get_service_url()
    client = Client(wsdl_url, transport=transport, settings=client_settings)
    return client


def transmitir_factura(xml_signed: bytes, test_set_id: str = "123456") -> dict:
    """
    Sends a signed electronic invoice XML to DIAN for validation.

    Args:
        xml_signed: The complete signed XML (bytes)
        test_set_id: Identificador del Juego de Pruebas (habilitación)

    Returns:
        Dict with DIAN response:
        - status: "aceptada" | "rechazada" | "error"
        - cufe: str (if accepted)
        - error_message: str (if rejected)
        - raw_response: str
    """
    try:
        client = _create_client()

        xml_str = xml_signed.decode("utf-8")

        # DIAN expects base64-encoded XML
        import base64
        xml_b64 = base64.b64encode(xml_signed).decode("utf-8")

        # SendBillSync operation
        # Parameters depend on the WSDL version
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
