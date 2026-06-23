"""
Genera XML UBL 2.1 CO para Documento Equivalente Electrónico — Tiquete POS (DEE POS).
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


def generar_xml_dee_pos(
    prefijo: str,
    consecutivo: int,
    fecha_emision: datetime,
    nit_emisor: str,
    razon_social_emisor: str,
    items: list[dict],
    total: Decimal,
    iva: Decimal,
    cufe: str,
    adquiriente_nit: str = "222222222222",
    adquiriente_razon_social: str = "CONSUMIDOR FINAL",
) -> bytes:
    numero = f"{prefijo}{consecutivo}"
    total_base = Decimal(str(total)) - Decimal(str(iva))

    doc = etree.Element(
        "Invoice",
        attrib={
            "xmlns": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
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
    _el(CBC + "CustomizationID", "38")
    _el(CBC + "ProfileID", "DIAN 2.1")
    _el(CBC + "ProfileExecutionID", "1")
    _el(CBC + "ID", numero)
    _el(CBC + "UUID", cufe, schemeID="2", schemeName="CUFE-SHA384")
    _el(CBC + "IssueDate", _fmt_date(fecha_emision))
    _el(CBC + "IssueTime", _fmt_time(fecha_emision))
    _el(CBC + "InvoiceTypeCode", "02",
        listVersionID="2.1", name="Documento Equivalente", listAgencyID="6")
    _el(CBC + "DocumentCurrencyCode", "COP",
        listID="ISO 4217 Alpha", listAgencyID="6")
    _el(CBC + "LineCountNumeric", str(len(items)))

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

    # Customer (CONSUMIDOR FINAL by default)
    cust = _el(CAC + "AccountingCustomerParty")
    cp = etree.SubElement(cust, CAC + "Party")
    pi3 = etree.SubElement(cp, CAC + "PartyIdentification")
    etree.SubElement(pi3, CBC + "ID", schemeAgencyID="6",
                     schemeID="13").text = adquiriente_nit
    ple2 = etree.SubElement(cp, CAC + "PartyLegalEntity")
    etree.SubElement(ple2, CBC + "RegistrationName").text = adquiriente_razon_social

    # Tax total
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

    # Monetary total
    mt = _el(CAC + "LegalMonetaryTotal")
    etree.SubElement(mt, CBC + "PayableAmount",
                     currencyID="COP").text = _fmt_money(total)

    # Lines
    for idx, item in enumerate(items, 1):
        cant = Decimal(str(item.get("cantidad", 1)))
        pu = Decimal(str(item.get("precio_unit", 0)))
        subt = Decimal(str(item.get("subtotal", cant * pu)))

        li = _el(CAC + "InvoiceLine")
        _el(CBC + "ID", str(idx), tag_of=li)
        etree.SubElement(li, CBC + "InvoicedQuantity", unitCode="94",
                         unitCodeListID="UNECE_Rec20",
                         unitCodeListAgencyID="6").text = _fmt_money(cant)
        etree.SubElement(li, CBC + "LineExtensionAmount",
                         currencyID="COP").text = _fmt_money(subt)

        line_item = etree.SubElement(li, CAC + "Item")
        etree.SubElement(line_item, CBC + "Description").text = \
            str(item.get("nombre", "Producto"))

        px = etree.SubElement(li, CAC + "Price")
        etree.SubElement(px, CBC + "PriceAmount",
                         currencyID="COP").text = _fmt_money(pu)

    return etree.tostring(doc, pretty_print=True, xml_declaration=True,
                          encoding="UTF-8", standalone=True)
