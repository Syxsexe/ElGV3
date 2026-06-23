"""
QA Test: CUFE / CUDE generation (SHA-384).
Validates that the CUFE hash matches the DIAN algorithm specification.
"""
import hashlib
from datetime import datetime

from tests.conftest import (
    SAMPLE_NIT_EMISOR, SAMPLE_NIT_ADQUIRIENTE, SAMPLE_CLAVE_TECNICA,
    SAMPLE_PREFIJO, SAMPLE_CONSECUTIVO, SAMPLE_TOTAL_BASE,
    SAMPLE_IVA, SAMPLE_TOTAL,
)


def test_generar_cufe_import():
    """CUFE module imports successfully."""
    from app.dian.cufe import generar_cufe
    assert callable(generar_cufe)


def test_generar_cufe_output_length():
    """CUFE output is a 96-character uppercase hex string."""
    from app.dian.cufe import generar_cufe

    cufe = generar_cufe(
        numero_factura=f"{SAMPLE_PREFIJO}{SAMPLE_CONSECUTIVO}",
        fecha_emision=datetime(2026, 6, 23, 14, 30, 0),
        nit_emisor=SAMPLE_NIT_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        total_sin_impuestos=SAMPLE_TOTAL_BASE,
        total_con_impuestos=SAMPLE_TOTAL,
        clave_tecnica=SAMPLE_CLAVE_TECNICA,
        tipo_documento="01",
    )

    assert len(cufe) == 96, "CUFE debe ser de 96 caracteres hex"
    assert cufe.isalnum() and cufe.isupper(), "CUFE debe ser hexadecimal en mayúsculas"


def test_generar_cufe_deterministic():
    """Same inputs produce same CUFE."""
    from app.dian.cufe import generar_cufe

    cufe1 = generar_cufe(
        numero_factura="SETP1",
        fecha_emision=datetime(2026, 6, 23, 14, 30, 0),
        nit_emisor="9001234567",
        nit_adquiriente="8009876543",
        total_sin_impuestos=84033.61,
        total_con_impuestos=100000.00,
        clave_tecnica="6a7b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d",
        tipo_documento="01",
    )

    cufe2 = generar_cufe(
        numero_factura="SETP1",
        fecha_emision=datetime(2026, 6, 23, 14, 30, 0),
        nit_emisor="9001234567",
        nit_adquiriente="8009876543",
        total_sin_impuestos=84033.61,
        total_con_impuestos=100000.00,
        clave_tecnica="6a7b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d",
        tipo_documento="01",
    )

    assert cufe1 == cufe2, "CUFE debe ser determinista"


def test_generar_cufe_algorithm():
    """Validate CUFE uses SHA-384 with correct concatenation format."""
    from app.dian.cufe import generar_cufe

    fecha = datetime(2026, 6, 23, 14, 30, 0)
    numero = "SETP1"
    nit_emi = "9001234567"
    nit_adq = "8009876543"
    base = 84033.61
    total = 100000.00
    clave = "6a7b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d"
    tipo = "01"

    cufe = generar_cufe(
        numero_factura=numero,
        fecha_emision=fecha,
        nit_emisor=nit_emi,
        nit_adquiriente=nit_adq,
        total_sin_impuestos=base,
        total_con_impuestos=total,
        clave_tecnica=clave,
        tipo_documento=tipo,
    )

    # Manually compute
    expected_raw = (
        numero
        + fecha.strftime("%Y-%m-%dT%H:%M:%S")
        + "".join(c for c in nit_emi if c.isdigit())
        + "".join(c for c in nit_adq if c.isdigit())
        + str(int(round(base, 0)))
        + str(int(round(total, 0)))
        + clave
        + tipo
    )
    expected = hashlib.sha384(expected_raw.encode("utf-8")).hexdigest().upper()

    assert cufe == expected, "CUFE debe coincidir con SHA-384 manual"


def test_generar_cufe_nit_with_non_digits():
    """NITs with non-digit characters (e.g., DV) are cleaned."""
    from app.dian.cufe import generar_cufe

    cufe = generar_cufe(
        numero_factura="SETP1",
        fecha_emision=datetime(2026, 6, 23, 14, 30, 0),
        nit_emisor="900.123.456-7",   # with DV formatting
        nit_adquiriente="8009876543",
        total_sin_impuestos=1000,
        total_con_impuestos=1190,
        clave_tecnica=SAMPLE_CLAVE_TECNICA,
    )

    assert len(cufe) == 96
    assert cufe.isalnum()


def test_generar_cufe_different_inputs():
    """Different inputs produce different CUFE."""
    from app.dian.cufe import generar_cufe

    base = dict(
        numero_factura="SETP1",
        fecha_emision=datetime(2026, 6, 23, 14, 30, 0),
        nit_emisor="9001234567",
        nit_adquiriente="8009876543",
        total_sin_impuestos=84033.61,
        total_con_impuestos=100000.00,
        clave_tecnica="6a7b8c9d-0e1f-2a3b-4c5d-6e7f8a9b0c1d",
        tipo_documento="01",
    )

    original = generar_cufe(**base)

    # Change NIT
    mod = base.copy()
    mod["nit_adquiriente"] = "9999999999"
    assert generar_cufe(**mod) != original

    # Change total — use value that rounds to different int
    mod2 = base.copy()
    mod2["total_con_impuestos"] = 95000.00
    assert generar_cufe(**mod2) != original


def test_generar_cufe_con_montos_cero():
    """CUFE works with zero amounts."""
    from app.dian.cufe import generar_cufe

    cufe = generar_cufe(
        numero_factura="SETP1",
        fecha_emision=datetime(2026, 6, 23, 14, 30, 0),
        nit_emisor="9001234567",
        nit_adquiriente="8009876543",
        total_sin_impuestos=0,
        total_con_impuestos=0,
        clave_tecnica=SAMPLE_CLAVE_TECNICA,
    )

    assert len(cufe) == 96


def test_generar_cude_import():
    """CUDE (Notas) generation works."""
    from app.dian.cufe import generar_cude

    cude = generar_cude(
        numero_documento="NC001",
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor="9001234567",
        nit_adquiriente="8009876543",
        total_sin_impuestos=50000,
        total_con_impuestos=59500,
        clave_tecnica=SAMPLE_CLAVE_TECNICA,
        tipo_documento="04",
    )

    assert len(cude) == 96
    assert cude.isalnum()


def test_cufe_dee_pos():
    """DEE POS CUFE uses default NIT for consumer."""
    from app.dian.cufe import generar_cufe_dee_pos

    cufe = generar_cufe_dee_pos(
        numero_documento="POS001",
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor="9001234567",
        total_con_impuestos=50000,
        clave_tecnica=SAMPLE_CLAVE_TECNICA,
    )

    assert len(cufe) == 96


def test_cufe_fecha_desde_string():
    """CUFE accepts ISO date strings."""
    from app.dian.cufe import generar_cufe

    cufe = generar_cufe(
        numero_factura="SETP1",
        fecha_emision="2026-06-23T14:30:00",
        nit_emisor="9001234567",
        nit_adquiriente="8009876543",
        total_sin_impuestos=1000,
        total_con_impuestos=1190,
        clave_tecnica=SAMPLE_CLAVE_TECNICA,
    )

    assert len(cufe) == 96
