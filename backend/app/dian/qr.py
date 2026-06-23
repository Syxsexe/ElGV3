"""
DIAN QR Code Generator
Generates QR with invoice verification data for graphical representation.
"""

import base64
import io
import qrcode
from qrcode.image.pil import PilImage


def generar_qr_base64(
    nit_emisor: str,
    numero_factura: str,
    cufe: str,
    total: float,
    iva: float,
    fecha: str,
    url_verificacion: str = "https://catalogo-vpfe.dian.gov.co/User/SearchDocument",
) -> str:
    """
    Generates a QR code image as base64 string.
    The QR contains the DIAN verification URL with document parameters.

    DIAN standard QR content format:
    NIT Emisor + NumFactura + CUFE + URL Verificación + Total + IVA + Fecha
    """
    qr_content = (
        f"{nit_emisor}|"
        f"{numero_factura}|"
        f"{cufe}|"
        f"{url_verificacion}|"
        f"{total:.0f}|"
        f"{iva:.0f}|"
        f"{fecha}"
    )

    img = qrcode.make(qr_content, image_factory=PilImage)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def generar_qr_url(
    cufe: str,
    url_verificacion: str = "https://catalogo-vpfe.dian.gov.co/User/SearchDocument",
) -> str:
    """
    Returns the DIAN verification URL with the CUFE for manual validation.
    """
    return f"{url_verificacion}?cufe={cufe}"
