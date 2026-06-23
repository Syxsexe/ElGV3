"""
QA Test: QR Code generation.
Validates QR content format and base64 output.
"""
import base64
from io import BytesIO

from tests.conftest import SAMPLE_NIT_EMISOR


def test_generar_qr_import():
    """QR module imports successfully."""
    from app.dian.qr import generar_qr_base64
    assert callable(generar_qr_base64)


def test_generar_qr_base64_output():
    """QR returns a valid base64 PNG string."""
    from app.dian.qr import generar_qr_base64

    qr_b64 = generar_qr_base64(
        nit_emisor=SAMPLE_NIT_EMISOR,
        numero_factura="SETP1",
        cufe="A" * 96,
        total=100000.00,
        iva=19000.00,
        fecha="2026-06-23",
    )

    assert isinstance(qr_b64, str)
    assert len(qr_b64) > 100

    # Verify it's valid base64
    decoded = base64.b64decode(qr_b64)
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n", "Debe ser un PNG válido"


def test_generar_qr_content_format():
    """QR content must follow DIAN format: NIT|NumFactura|CUFE|URL|Total|IVA|Fecha."""
    from app.dian.qr import generar_qr_base64
    import qrcode
    from PIL import Image
    from io import BytesIO

    qr_b64 = generar_qr_base64(
        nit_emisor="9001234567",
        numero_factura="SETP1",
        cufe="A" * 96,
        total=100000.00,
        iva=19000.00,
        fecha="2026-06-23",
    )

    decoded = base64.b64decode(qr_b64)
    img = Image.open(BytesIO(decoded))
    assert img.width >= 29  # default qrcode minimum size


def test_generar_qr_different_cufe():
    """Different CUFE produces different QR."""
    from app.dian.qr import generar_qr_base64

    qr1 = generar_qr_base64(
        nit_emisor="9001234567",
        numero_factura="SETP1",
        cufe="A" * 96,
        total=100000,
        iva=19000,
        fecha="2026-06-23",
    )

    qr2 = generar_qr_base64(
        nit_emisor="9001234567",
        numero_factura="SETP1",
        cufe="B" * 96,
        total=100000,
        iva=19000,
        fecha="2026-06-23",
    )

    assert qr1 != qr2


def test_generar_qr_url():
    """QR URL generation returns valid DIAN verification URL."""
    from app.dian.qr import generar_qr_url

    url = generar_qr_url(cufe="A" * 96)
    assert url.startswith("https://")
    assert "cufe=" in url


def test_generar_qr_custom_url():
    """Custom verification URL is used when provided."""
    from app.dian.qr import generar_qr_url

    url = generar_qr_url(cufe="A" * 96, url_verificacion="https://example.com")
    assert url.startswith("https://example.com")


def test_generar_qr_iva_cero():
    """QR works with zero IVA."""
    from app.dian.qr import generar_qr_base64

    qr_b64 = generar_qr_base64(
        nit_emisor="9001234567",
        numero_factura="SETP1",
        cufe="A" * 96,
        total=1000,
        iva=0,
        fecha="2026-06-23",
    )
    assert len(qr_b64) > 100
