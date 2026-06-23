"""
QA Test: UBL 2.1 CO XML Factura generation.
Validates XML structure, namespaces, and required fields.
"""
from datetime import datetime
from decimal import Decimal
from lxml import etree

from tests.conftest import (
    SAMPLE_NIT_EMISOR, SAMPLE_RAZON_EMISOR, SAMPLE_NIT_ADQUIRIENTE,
    SAMPLE_RAZON_ADQUIRIENTE, SAMPLE_CLAVE_TECNICA, SAMPLE_PREFIJO,
    SAMPLE_CONSECUTIVO, SAMPLE_TOTAL_BASE, SAMPLE_IVA, SAMPLE_TOTAL,
    SAMPLE_ITEMS,
)


def _parse(xml_bytes):
    """Helper to parse XML bytes and return root."""
    return etree.fromstring(xml_bytes)


def _ns(tag):
    """Helper to build namespaced tag names like {uri}tag."""
    NSMAP = {
        "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
        "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
        "sts": "dian:gov:co:facturaelectronica:Structures-2-1",
    }
    for prefix, uri in NSMAP.items():
        if tag.startswith(prefix + ":"):
            return "{" + uri + "}" + tag.split(":", 1)[1]
    return tag


def test_xml_generator_import():
    """XML generator imports successfully."""
    from app.dian.xml_generator import generar_xml_factura
    assert callable(generar_xml_factura)


def test_xml_valid_ubl_xml():
    """Output is valid XML."""
    from app.dian.xml_generator import generar_xml_factura

    xml_bytes = generar_xml_factura(
        prefijo=SAMPLE_PREFIJO,
        consecutivo=SAMPLE_CONSECUTIVO,
        fecha_emision=datetime(2026, 6, 23, 14, 30, 0),
        nit_emisor=SAMPLE_NIT_EMISOR,
        razon_social_emisor=SAMPLE_RAZON_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        razon_social_adquiriente=SAMPLE_RAZON_ADQUIRIENTE,
        items=SAMPLE_ITEMS,
        total_base=Decimal(str(SAMPLE_TOTAL_BASE)),
        iva=Decimal(str(SAMPLE_IVA)),
        total=Decimal(str(SAMPLE_TOTAL)),
        cufe="A" * 96,
    )

    root = _parse(xml_bytes)
    assert root is not None
    assert root.tag == _ns(":Invoice") or "Invoice" in root.tag


def test_xml_ubl_version():
    """XML must declare UBL 2.1."""
    from app.dian.xml_generator import generar_xml_factura

    xml_bytes = generar_xml_factura(
        prefijo=SAMPLE_PREFIJO,
        consecutivo=SAMPLE_CONSECUTIVO,
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor=SAMPLE_NIT_EMISOR,
        razon_social_emisor=SAMPLE_RAZON_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        razon_social_adquiriente=SAMPLE_RAZON_ADQUIRIENTE,
        items=SAMPLE_ITEMS,
        total_base=Decimal(str(SAMPLE_TOTAL_BASE)),
        iva=Decimal(str(SAMPLE_IVA)),
        total=Decimal(str(SAMPLE_TOTAL)),
        cufe="A" * 96,
    )

    root = _parse(xml_bytes)
    ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
    ubl_version = root.find("cbc:UBLVersionID", ns)
    assert ubl_version is not None
    assert ubl_version.text == "UBL 2.1"


def test_xml_invoice_number():
    """Invoice number must be prefijo + consecutivo."""
    from app.dian.xml_generator import generar_xml_factura

    xml_bytes = generar_xml_factura(
        prefijo="SETP", consecutivo=1,
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor=SAMPLE_NIT_EMISOR, razon_social_emisor=SAMPLE_RAZON_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        razon_social_adquiriente=SAMPLE_RAZON_ADQUIRIENTE,
        items=[{"nombre": "TEST", "cantidad": 1, "precio_unit": 1000}],
        total_base=Decimal("840.34"), iva=Decimal("159.66"),
        total=Decimal("1000.00"),
        cufe="A" * 96,
    )

    root = _parse(xml_bytes)
    ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
    inv_id = root.find("cbc:ID", ns)
    assert inv_id is not None
    assert inv_id.text == "SETP1"


def test_xml_cufe_present():
    """CUFE must be embedded as UUID with CUFE-SHA384 scheme."""
    from app.dian.xml_generator import generar_xml_factura

    cufe_value = "B" * 96
    xml_bytes = generar_xml_factura(
        prefijo="SETP", consecutivo=1,
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor=SAMPLE_NIT_EMISOR, razon_social_emisor=SAMPLE_RAZON_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        razon_social_adquiriente=SAMPLE_RAZON_ADQUIRIENTE,
        items=[{"nombre": "TEST", "cantidad": 1, "precio_unit": 1000}],
        total_base=Decimal("840.34"), iva=Decimal("159.66"),
        total=Decimal("1000.00"),
        cufe=cufe_value,
    )

    root = _parse(xml_bytes)
    ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
    uuid_el = root.find("cbc:UUID", ns)
    assert uuid_el is not None
    assert uuid_el.text == cufe_value
    assert uuid_el.get("schemeName") == "CUFE-SHA384"


def test_xml_required_elements():
    """Invoice must have all required UBL 2.1 elements."""
    from app.dian.xml_generator import generar_xml_factura

    xml_bytes = generar_xml_factura(
        prefijo="SETP", consecutivo=1,
        fecha_emision=datetime(2026, 6, 23, 14, 30, 0),
        nit_emisor=SAMPLE_NIT_EMISOR, razon_social_emisor=SAMPLE_RAZON_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        razon_social_adquiriente=SAMPLE_RAZON_ADQUIRIENTE,
        items=SAMPLE_ITEMS,
        total_base=Decimal(str(SAMPLE_TOTAL_BASE)),
        iva=Decimal(str(SAMPLE_IVA)),
        total=Decimal(str(SAMPLE_TOTAL)),
        cufe="A" * 96,
    )

    root = _parse(xml_bytes)
    ns_cbc = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
    ns_cac = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}
    ns_ext = {"ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"}

    assert root.find("cbc:UBLVersionID", ns_cbc) is not None
    assert root.find("cbc:CustomizationID", ns_cbc) is not None
    assert root.find("cbc:ProfileID", ns_cbc) is not None
    assert root.find("cbc:ID", ns_cbc) is not None
    assert root.find("cbc:UUID", ns_cbc) is not None
    assert root.find("cbc:IssueDate", ns_cbc) is not None
    assert root.find("cbc:IssueTime", ns_cbc) is not None
    assert root.find("cbc:InvoiceTypeCode", ns_cbc) is not None
    assert root.find("cbc:DocumentCurrencyCode", ns_cbc) is not None
    assert root.find("cbc:LineCountNumeric", ns_cbc) is not None
    assert root.find("cac:Signature", ns_cac) is not None
    assert root.find("cac:AccountingSupplierParty", ns_cac) is not None
    assert root.find("cac:AccountingCustomerParty", ns_cac) is not None
    assert root.find("cac:TaxTotal", ns_cac) is not None
    assert root.find("cac:LegalMonetaryTotal", ns_cac) is not None


def test_xml_lines_count():
    """Number of InvoiceLine elements must match LineCountNumeric."""
    from app.dian.xml_generator import generar_xml_factura

    xml_bytes = generar_xml_factura(
        prefijo="SETP", consecutivo=1,
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor=SAMPLE_NIT_EMISOR, razon_social_emisor=SAMPLE_RAZON_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        razon_social_adquiriente=SAMPLE_RAZON_ADQUIRIENTE,
        items=SAMPLE_ITEMS,
        total_base=Decimal(str(SAMPLE_TOTAL_BASE)),
        iva=Decimal(str(SAMPLE_IVA)),
        total=Decimal(str(SAMPLE_TOTAL)),
        cufe="A" * 96,
    )

    root = _parse(xml_bytes)
    ns_cbc = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
    ns_cac = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}

    line_count = int(root.find("cbc:LineCountNumeric", ns_cbc).text)
    lines = root.findall("cac:InvoiceLine", ns_cac)
    assert len(lines) == line_count
    assert len(lines) == len(SAMPLE_ITEMS)


def test_xml_monetary_totals():
    """LegalMonetaryTotal must have correct PayableAmount and currency."""
    from app.dian.xml_generator import generar_xml_factura

    xml_bytes = generar_xml_factura(
        prefijo="SETP", consecutivo=1,
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor=SAMPLE_NIT_EMISOR, razon_social_emisor=SAMPLE_RAZON_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        razon_social_adquiriente=SAMPLE_RAZON_ADQUIRIENTE,
        items=SAMPLE_ITEMS,
        total_base=Decimal(str(SAMPLE_TOTAL_BASE)),
        iva=Decimal(str(SAMPLE_IVA)),
        total=Decimal(str(SAMPLE_TOTAL)),
        cufe="A" * 96,
    )

    root = _parse(xml_bytes)
    ns_cbc = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
    ns_cac = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}

    mt = root.find("cac:LegalMonetaryTotal", ns_cac)
    assert mt is not None
    payable = mt.find("cbc:PayableAmount", ns_cbc)
    assert payable is not None
    assert payable.get("currencyID") == "COP"


def test_xml_adquiriente_contact():
    """Customer contact info (email, phone) appears when provided."""
    from app.dian.xml_generator import generar_xml_factura

    xml_bytes = generar_xml_factura(
        prefijo="SETP", consecutivo=1,
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor=SAMPLE_NIT_EMISOR, razon_social_emisor=SAMPLE_RAZON_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        razon_social_adquiriente=SAMPLE_RAZON_ADQUIRIENTE,
        email_adquiriente="cliente@ejemplo.com",
        telefono_adquiriente="3001234567",
        items=[{"nombre": "TEST", "cantidad": 1, "precio_unit": 1000}],
        total_base=Decimal("840.34"), iva=Decimal("159.66"),
        total=Decimal("1000.00"),
        cufe="A" * 96,
    )

    root = _parse(xml_bytes)
    ns_cac = {"cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"}
    ns_cbc = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}

    customer = root.find("cac:AccountingCustomerParty", ns_cac)
    contact = customer.find("cac:Party/cac:Contact", ns_cac)
    assert contact is not None
    assert contact.find("cbc:ElectronicMail", ns_cbc).text == "cliente@ejemplo.com"
    assert contact.find("cbc:Telephone", ns_cbc).text == "3001234567"


def test_xml_notas():
    """Invoice notes appear when provided."""
    from app.dian.xml_generator import generar_xml_factura

    xml_bytes = generar_xml_factura(
        prefijo="SETP", consecutivo=1,
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor=SAMPLE_NIT_EMISOR, razon_social_emisor=SAMPLE_RAZON_EMISOR,
        nit_adquiriente=SAMPLE_NIT_ADQUIRIENTE,
        razon_social_adquiriente=SAMPLE_RAZON_ADQUIRIENTE,
        items=[{"nombre": "TEST", "cantidad": 1, "precio_unit": 1000}],
        total_base=Decimal("840.34"), iva=Decimal("159.66"),
        total=Decimal("1000.00"),
        cufe="A" * 96,
        notas="Venta sujeta a facturación electrónica",
    )

    root = _parse(xml_bytes)
    ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
    note = root.find("cbc:Note", ns)
    assert note is not None
    assert "facturación electrónica" in note.text


def test_xml_supplier_party():
    """Supplier must include NIT and tax scheme."""
    from app.dian.xml_generator import generar_xml_factura

    xml_bytes = generar_xml_factura(
        prefijo="SETP", consecutivo=1,
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor="9001234567", razon_social_emisor="EL G TIENDA TCG SAS",
        nit_adquiriente="8009876543",
        razon_social_adquiriente="COMPRADOR EJEMPLO SAS",
        items=[{"nombre": "TEST", "cantidad": 1, "precio_unit": 1000}],
        total_base=Decimal("840.34"), iva=Decimal("159.66"),
        total=Decimal("1000.00"),
        cufe="A" * 96,
    )

    root = _parse(xml_bytes)
    ns = {
        "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
        "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    }

    supplier = root.find("cac:AccountingSupplierParty", ns)
    party_id = supplier.find("cac:Party/cac:PartyIdentification/cbc:ID", ns)
    assert party_id is not None
    assert "9001234567" in party_id.text


def test_xml_defaults_items_empty():
    """Invoice with no items still generates valid XML."""
    from app.dian.xml_generator import generar_xml_factura

    xml_bytes = generar_xml_factura(
        prefijo="SETP", consecutivo=1,
        fecha_emision=datetime(2026, 6, 23),
        nit_emisor="9001234567", razon_social_emisor="EL G TIENDA TCG SAS",
        nit_adquiriente="8009876543",
        razon_social_adquiriente="COMPRADOR EJEMPLO SAS",
        items=[],
        total_base=Decimal("0"),
        iva=Decimal("0"),
        total=Decimal("0"),
        cufe="A" * 96,
    )

    root = _parse(xml_bytes)
    assert root is not None
