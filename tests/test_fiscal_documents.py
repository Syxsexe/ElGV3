"""
QA Test: Desktop Fiscal Documents (Notas Crédito / Débito, DEE POS).
Validates NC/ND data preparation logic.
"""
from unittest.mock import patch, MagicMock
from datetime import datetime

from tests.conftest import (
    SAMPLE_NIT_EMISOR, SAMPLE_NIT_ADQUIRIENTE,
)


def test_preparar_venta_para_dian_import():
    """Fiscal documents module imports."""
    from modules.fiscal_documents import preparar_venta_para_dian
    assert callable(preparar_venta_para_dian)


def test_preparar_venta_para_dian_minimal():
    """Minimal venta data is prepared correctly."""
    from modules.fiscal_documents import preparar_venta_para_dian

    venta = {
        "id": 1,
        "fecha": "2026-06-23 14:30:00",
        "total": 100000.00,
        "metodo_pago": "efectivo",
        "tipo": "tienda",
        "detalle": [
            {"producto_id": 1, "nombre": "PRODUCTO A",
             "cantidad": 2, "precio_unit": 25000.00, "subtotal": 50000.00},
        ],
    }

    result = preparar_venta_para_dian(venta_data=venta)

    assert result["venta_id"] == 1
    assert result["total"] == 100000.00
    assert result["tipo"] == "tienda"
    assert len(result["items"]) == 1
    assert result["adquiriente"]["nit"] == "222222222222"  # default consumer
    assert result["adquiriente"]["razon_social"] == "CONSUMIDOR FINAL"


def test_preparar_venta_para_dian_with_client():
    """Client info is included when provided."""
    from modules.fiscal_documents import preparar_venta_para_dian

    venta = {
        "id": 1,
        "fecha": "2026-06-23",
        "total": 50000,
        "metodo_pago": "tarjeta",
        "tipo": "tienda",
        "detalle": [],
    }
    cliente = {
        "documento": "8009876543",
        "nombre": "JUAN PEREZ",
        "tipo_documento": "CC",
        "email": "juan@ejemplo.com",
        "direccion": "Calle 10 #20-30",
        "telefono": "3001234567",
    }

    result = preparar_venta_para_dian(venta_data=venta, cliente=cliente)

    assert result["adquiriente"]["nit"] == "8009876543"
    assert result["adquiriente"]["razon_social"] == "JUAN PEREZ"
    assert result["adquiriente"]["email"] == "juan@ejemplo.com"
    assert result["adquiriente"]["direccion"] == "Calle 10 #20-30"


def test_crear_nota_credito_import():
    """crear_nota_credito function exists."""
    from modules.fiscal_documents import crear_nota_credito
    assert callable(crear_nota_credito)


def test_crear_nota_credito_structure():
    """Crear nota crédito returns correct structure."""
    from modules.fiscal_documents import crear_nota_credito

    # We need a venta in the DB - mock the DB
    mock_venta = {
        "id": 1, "total": 100000.00, "fecha": "2026-06-23",
        "metodo_pago": "efectivo", "tipo": "tienda",
        "usuario_id": 1, "sesion_id": 1,
    }
    mock_detalle = [
        {"id": 1, "producto_id": 1, "cantidad": 2,
         "precio_unit": 25000.00, "subtotal": 50000.00},
    ]

    with patch("modules.fiscal_documents.get_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_venta
        mock_cursor.fetchall.return_value = mock_detalle
        mock_conn.return_value.execute.return_value = mock_cursor
        mock_conn.return_value.__enter__ = lambda s: s
        mock_conn.return_value.__exit__ = lambda *a: None

        nc = crear_nota_credito(venta_id=1, motivo="Devolución total")

    assert nc["tipo"] == "nota_credito"
    assert nc["venta_id_original"] == 1
    assert nc["motivo"] == "Devolución total"
    assert nc["anulacion_total"] is True
    assert nc["total"] == 100000.00
    assert nc["total_base"] == round(100000 / 1.19, 2)
    assert nc["iva"] == round(100000 - 100000 / 1.19, 2)


def test_crear_nota_credito_motivo_required():
    """Motivo is included in output."""
    from modules.fiscal_documents import crear_nota_credito

    mock_venta = {"id": 1, "total": 50000}
    mock_detalle = [{"id": 1, "subtotal": 50000}]

    with patch("modules.fiscal_documents.get_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = mock_venta
        mock_cursor.fetchall.return_value = mock_detalle
        mock_conn.return_value.execute.return_value = mock_cursor
        mock_conn.return_value.__enter__ = lambda s: s
        mock_conn.return_value.__exit__ = lambda *a: None

        nc = crear_nota_credito(venta_id=1, motivo="Error en precio")

    assert nc["motivo"] == "Error en precio"


def test_crear_nota_debito_import():
    """crear_nota_debito function exists."""
    from modules.fiscal_documents import crear_nota_debito
    assert callable(crear_nota_debito)


def test_crear_nota_debito_structure():
    """Debit note is created with additional value."""
    from modules.fiscal_documents import crear_nota_debito

    with patch("modules.fiscal_documents.get_connection") as mock_conn:
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = {"id": 1, "total": 100000}
        mock_conn.return_value.execute.return_value = mock_cursor
        mock_conn.return_value.__enter__ = lambda s: s
        mock_conn.return_value.__exit__ = lambda *a: None

        nd = crear_nota_debito(venta_id=1, motivo="Ajuste precio",
                                valor_adicional=10000)

    assert nd["tipo"] == "nota_debito"
    assert nd["venta_id_original"] == 1
    assert nd["motivo"] == "Ajuste precio"
    assert nd["total"] == 10000
    assert nd["total_base"] == round(10000 / 1.19, 2)
    assert nd["iva"] == round(10000 - 10000 / 1.19, 2)
