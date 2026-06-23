"""
Genera XML UBL 2.1 CO para Nota Crédito y Nota Débito.
"""

from datetime import datetime
from decimal import Decimal
from lxml import etree

from config import settings

CAC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}"
CBC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
EXT = "{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}"


def _fmt_money(val):
    return f"{Decimal(str(val)):.2f}"


def _fmt_date(dt):
    return dt.strftime("%Y-%m-%d")


def _fmt_time(dt):
    return dt.strftime("%H:%M:%S")


def _build_base_xml(root_tag: str, numero: str, fecha_emision: datetime,
                     nit_emisor: str, razon_social_emisor: str,
                     nit_adquiriente: str, razon_social_adquiriente: str,
                     cude: str) -> etree.Element:
    doc = etree.Element(
        root_tag,
        attrib={
            "xmlns": f"urn:oasis:names:specification:ubl:schema:xsd:{root_tag}-2",
            "xmlns:cac": CAC.strip("{}"),
            "xmlns:cbc": CBC.strip("{}"),
            "xmlns:ext": EXT.strip("{}"),
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        },
    )

    def _el(tag, text=None, **attrs):
        el = etree.SubElement(doc, tag)
        if text is not None:
            el.text = str(text)
        for k, v in attrs.items():
            el.set(k.replace("_", ""), str(v))
        return el

    ue = _el(EXT + "UBLExtensions")
    uel = etree.SubElement(ue, EXT + "UBLExtension")
    etree.SubElement(uel, EXT + "ExtensionContent")

    _el(CBC + "UBLVersionID", "UBL 2.1")
    _el(CBC + "CustomizationID", "10")
    _el(CBC + "ProfileID", "DIAN 2.1")
    _el(CBC + "ProfileExecutionID", "1")
    _el(CBC + "ID", numero)
    _el(CBC + "UUID", cude, schemeID="2", schemeName="CUDE-SHA384")
    _el(CBC + "IssueDate", _fmt_date(fecha_emision))
    _el(CBC + "IssueTime", _fmt_time(fecha_emision))
    _el(CBC + "DocumentCurrencyCode", "COP",
        listID="ISO 4217 Alpha", listAgencyID="6")

    # Signature
    sig = _el(CAC + "Signature")
    _el(CBC + "ID", numero, tag_of=sig)
    sp = etree.SubElement(sig, CAC + "SignatoryParty")
    pi = etree.SubElement(sp, CAC + "PartyIdentification")
    etree.SubElement(pi, CBC + "ID", schemeAgencyID="6",
                     schemeID="4").text = nit_emisor
    pn = etree.SubElement(sp, CAC + "PartyName")
    etree.SubElement(pn, CBC + "Name").text = razon_social_emisor
    dsa = etree.SubElement(sig, CAC + "DigitalSignatureAttachment")
    er = etree.SubElement(dsa, CAC + "ExternalReference")
    etree.SubElement(er, CBC + "URI").text = f"#{numero}"

    # Supplier
    sup = _el(CAC + "AccountingSupplierParty")
    sp2 = etree.SubElement(sup, CAC + "Party")
    pi2 = etree.SubElement(sp2, CAC + "PartyIdentification")
    etree.SubElement(pi2, CBC + "ID", schemeAgencyID="6",
                     schemeID="4").text = nit_emisor
    ple = etree.SubElement(sp2, CAC + "PartyLegalEntity")
    etree.SubElement(ple, CBC + "RegistrationName").text = razon_social_emisor

    # Customer
    cust = _el(CAC + "AccountingCustomerParty")
    cp = etree.SubElement(cust, CAC + "Party")
    pi3 = etree.SubElement(cp, CAC + "PartyIdentification")
    etree.SubElement(pi3, CBC + "ID", schemeAgencyID="6",
                     schemeID="4").text = nit_adquiriente
    ple2 = etree.SubElement(cp, CAC + "PartyLegalEntity")
    etree.SubElement(ple2, CBC + "RegistrationName").text = razon_social_adquiriente

    return doc


def _add_monetary_total(doc, total_base, iva, total):
    def _el(tag, text=None, **attrs):
        el = etree.SubElement(doc, tag)
        if text is not None:
            el.text = str(text)
        for k, v in attrs.items():
            el.set(k.replace("_", ""), str(v))
        return el

    if iva > 0:
        tt = _el(CAC + "TaxTotal")
        etree.SubElement(tt, CBC + "TaxAmount",
                         currencyID="COP").text = _fmt_money(iva)
        ts = etree.SubElement(tt, CAC + "TaxSubtotal")
        etree.SubElement(ts, CBC + "TaxableAmount",
                         currencyID="COP").text = _fmt_money(total_base)
        etree.SubElement(ts, CBC + "TaxAmount",
                         currencyID="COP").text = _fmt_money(iva)
        etree.SubElement(ts, CBC + "Percent").text = "19.00"

    mt = _el(CAC + "LegalMonetaryTotal")
    etree.SubElement(mt, CBC + "PayableAmount",
                     currencyID="COP").text = _fmt_money(total)


def _add_lines(doc, items):
    def _el(tag, text=None, **attrs):
        el = etree.SubElement(doc, tag)
        if text is not None:
            el.text = str(text)
        for k, v in attrs.items():
            el.set(k.replace("_", ""), str(v))
        return el

    for idx, item in enumerate(items, 1):
        cant = Decimal(str(item.get("cantidad", 1)))
        pu = Decimal(str(item.get("precio_unit", 0)))
        subt = Decimal(str(item.get("subtotal", cant * pu)))
        tag = "CreditNoteLine" if doc.tag.endswith("CreditNote") else "DebitNoteLine"

        li = _el(CAC + tag)
        _el(CBC + "ID", str(idx), tag_of=li)
        etree.SubElement(li, CBC + "LineExtensionAmount",
                         currencyID="COP").text = _fmt_money(subt)

        line_item = etree.SubElement(li, CAC + "Item")
        etree.SubElement(line_item, CBC + "Description").text = \
            str(item.get("nombre", "Producto"))

        px = etree.SubElement(li, CAC + "Price")
        etree.SubElement(px, CBC + "PriceAmount",
                         currencyID="COP").text = _fmt_money(pu)


def _add_credit_note_specifics(doc, factura_numero: str, motivo: str,
                                cufe_factura_original: str | None = None):
    def _el(tag, text=None, **attrs):
        el = etree.SubElement(doc, tag)
        if text is not None:
            el.text = str(text)
        for k, v in attrs.items():
            el.set(k.replace("_", ""), str(v))
        return el

    _el(CBC + "Note", motivo)
    _el(CBC + "CreditNoteTypeCode", "01",
        listVersionID="2.1", name="Nota Crédito")

    # Reference to original invoice
    billing_ref = _el(CAC + "BillingReference")
    inv_doc_ref = etree.SubElement(billing_ref, CAC + "InvoiceDocumentReference")
    etree.SubElement(inv_doc_ref, CBC + "ID").text = factura_numero
    if cufe_factura_original:
        etree.SubElement(inv_doc_ref, CBC + "UUID", schemeID="2",
                         schemeName="CUFE-SHA384").text = cufe_factura_original


def _add_debit_note_specifics(doc, factura_numero: str, motivo: str,
                               cufe_factura_original: str | None = None):
    def _el(tag, text=None, **attrs):
        el = etree.SubElement(doc, tag)
        if text is not None:
            el.text = str(text)
        for k, v in attrs.items():
            el.set(k.replace("_", ""), str(v))
        return el

    _el(CBC + "Note", motivo)
    _el(CBC + "DebitNoteTypeCode", "01",
        listVersionID="2.1", name="Nota Débito")

    billing_ref = _el(CAC + "BillingReference")
    inv_doc_ref = etree.SubElement(billing_ref, CAC + "InvoiceDocumentReference")
    etree.SubElement(inv_doc_ref, CBC + "ID").text = factura_numero
    if cufe_factura_original:
        etree.SubElement(inv_doc_ref, CBC + "UUID", schemeID="2",
                         schemeName="CUFE-SHA384").text = cufe_factura_original


def generar_xml_nota_credito(
    prefijo: str,
    consecutivo: int,
    fecha_emision: datetime,
    nit_emisor: str,
    razon_social_emisor: str,
    nit_adquiriente: str,
    razon_social_adquiriente: str,
    factura_original_numero: str,
    motivo: str,
    items: list[dict],
    total_base: Decimal,
    iva: Decimal,
    total: Decimal,
    cude: str,
    cufe_factura_original: str | None = None,
) -> bytes:
    numero = f"{prefijo}{consecutivo}"
    doc = _build_base_xml(
        "CreditNote", numero, fecha_emision,
        nit_emisor, razon_social_emisor,
        nit_adquiriente, razon_social_adquiriente,
        cude,
    )
    _add_credit_note_specifics(doc, factura_original_numero, motivo,
                                cufe_factura_original)
    _add_monetary_total(doc, total_base, iva, total)
    _add_lines(doc, items)

    etree.SubElement(doc, CBC + "LineCountNumeric").text = str(len(items))

    return etree.tostring(doc, pretty_print=True, xml_declaration=True,
                          encoding="UTF-8", standalone=True)


def generar_xml_nota_debito(
    prefijo: str,
    consecutivo: int,
    fecha_emision: datetime,
    nit_emisor: str,
    razon_social_emisor: str,
    nit_adquiriente: str,
    razon_social_adquiriente: str,
    factura_original_numero: str,
    motivo: str,
    items: list[dict],
    total_base: Decimal,
    iva: Decimal,
    total: Decimal,
    cude: str,
    cufe_factura_original: str | None = None,
) -> bytes:
    numero = f"{prefijo}{consecutivo}"
    doc = _build_base_xml(
        "DebitNote", numero, fecha_emision,
        nit_emisor, razon_social_emisor,
        nit_adquiriente, razon_social_adquiriente,
        cude,
    )
    _add_debit_note_specifics(doc, factura_original_numero, motivo,
                               cufe_factura_original)
    _add_monetary_total(doc, total_base, iva, total)
    _add_lines(doc, items)
    return etree.tostring(doc, pretty_print=True, xml_declaration=True,
                          encoding="UTF-8", standalone=True)
