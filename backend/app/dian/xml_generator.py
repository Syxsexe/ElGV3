"""
DIAN UBL 2.1 CO XML Generator
Genera XML para Factura Electrónica de Venta (FEV) siguiendo anexo técnico v1.9.
"""

from datetime import datetime
from decimal import Decimal

from lxml import etree

from config import settings


CAC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}"
CBC = "{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}"
EXT = "{urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2}"
STS = "{dian:gov:co:facturaelectronica:Structures-2-1}"


def _fmt_money(val):
    return f"{Decimal(str(val)):.2f}"


def _fmt_date(dt):
    return dt.strftime("%Y-%m-%d")


def _fmt_time(dt):
    return dt.strftime("%H:%M:%S")


def generar_xml_factura(
    prefijo: str,
    consecutivo: int,
    fecha_emision: datetime,
    nit_emisor: str,
    razon_social_emisor: str,
    nit_adquiriente: str,
    razon_social_adquiriente: str,
    direccion_adquiriente: str | None = None,
    email_adquiriente: str | None = None,
    telefono_adquiriente: str | None = None,
    items: list | None = None,
    total_base: Decimal | None = None,
    iva: Decimal | None = None,
    iva_porcentaje: Decimal | None = None,
    total: Decimal | None = None,
    cufe: str = "",
    notas: str | None = None,
) -> bytes:
    if items is None:
        items = []
    if total_base is None:
        total_base = Decimal("0")
    if iva is None:
        iva = Decimal("0")
    if iva_porcentaje is None:
        iva_porcentaje = Decimal("19.00")
    if total is None:
        total = total_base + iva

    numero = f"{prefijo}{consecutivo}"

    inv = etree.Element(
        "Invoice",
        attrib={
            "xmlns": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
            "xmlns:cac": CAC.strip("{}"),
            "xmlns:cbc": CBC.strip("{}"),
            "xmlns:ext": EXT.strip("{}"),
            "xmlns:sts": STS.strip("{}"),
            "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        },
    )

    def _el(tag, text=None, **attrs):
        el = etree.SubElement(inv, tag)
        if text is not None:
            el.text = str(text)
        for k, v in attrs.items():
            el.set(k.replace("_", ""), str(v))
        return el

    # UBLExtensions placeholder
    ue = _el(EXT + "UBLExtensions")
    uel = etree.SubElement(ue, EXT + "UBLExtension")
    etree.SubElement(uel, EXT + "ExtensionContent")

    _el(CBC + "UBLVersionID", "UBL 2.1")
    _el(CBC + "CustomizationID", "10")
    _el(CBC + "ProfileID", "DIAN 2.1")
    _el(CBC + "ProfileExecutionID", "1")
    _el(CBC + "ID", numero)
    _el(CBC + "UUID", cufe, schemeID="2", schemeName="CUFE-SHA384")
    _el(CBC + "IssueDate", _fmt_date(fecha_emision))
    _el(CBC + "IssueTime", _fmt_time(fecha_emision))
    _el(CBC + "InvoiceTypeCode", "01",
        listVersionID="2.1", name="Factura de Venta", listAgencyID="6")
    if notas:
        _el(CBC + "Note", notas)
    _el(CBC + "DocumentCurrencyCode", "COP",
        listID="ISO 4217 Alpha", listAgencyID="6")
    _el(CBC + "LineCountNumeric", str(len(items)))

    # Signature
    sig = _el(CAC + "Signature")
    _el(CBC + "ID", numero, tag_of=sig)
    sp = etree.SubElement(sig, CAC + "SignatoryParty")
    pi = etree.SubElement(sp, CAC + "PartyIdentification")
    etree.SubElement(pi, CBC + "ID", schemeAgencyID="6", schemeID="4").text = nit_emisor
    pn = etree.SubElement(sp, CAC + "PartyName")
    etree.SubElement(pn, CBC + "Name").text = razon_social_emisor
    dsa = etree.SubElement(sig, CAC + "DigitalSignatureAttachment")
    er = etree.SubElement(dsa, CAC + "ExternalReference")
    etree.SubElement(er, CBC + "URI").text = f"#{numero}"

    # Supplier
    sup = _el(CAC + "AccountingSupplierParty")
    sp2 = etree.SubElement(sup, CAC + "Party")
    _add_party_id(sp2, nit_emisor, "4")
    _add_tax_scheme(sp2, razon_social_emisor, nit_emisor, "48")
    _add_addr(sp2, settings.emisor_municipio, settings.emisor_departamento, settings.emisor_pais)
    ple = etree.SubElement(sp2, CAC + "PartyLegalEntity")
    etree.SubElement(ple, CBC + "RegistrationName").text = razon_social_emisor
    etree.SubElement(ple, CBC + "CompanyID", schemeAgencyID="6", schemeID="4").text = nit_emisor

    # Customer
    cust = _el(CAC + "AccountingCustomerParty")
    cp = etree.SubElement(cust, CAC + "Party")
    _add_party_id(cp, nit_adquiriente, "4" if len(str(nit_adquiriente)) > 3 else "13")
    _add_tax_scheme(cp, razon_social_adquiriente, nit_adquiriente, "49")
    _add_addr(cp, "00000", "00", settings.emisor_pais)
    ple2 = etree.SubElement(cp, CAC + "PartyLegalEntity")
    etree.SubElement(ple2, CBC + "RegistrationName").text = razon_social_adquiriente
    etree.SubElement(ple2, CBC + "CompanyID", schemeAgencyID="6", schemeID="4").text = nit_adquiriente
    if email_adquiriente or telefono_adquiriente:
        ct = etree.SubElement(cp, CAC + "Contact")
        if telefono_adquiriente:
            etree.SubElement(ct, CBC + "Telephone").text = telefono_adquiriente
        if email_adquiriente:
            etree.SubElement(ct, CBC + "ElectronicMail").text = email_adquiriente

    # Tax total
    tt = _el(CAC + "TaxTotal")
    etree.SubElement(tt, CBC + "TaxAmount", currencyID="COP").text = _fmt_money(iva)
    ts = etree.SubElement(tt, CAC + "TaxSubtotal")
    etree.SubElement(ts, CBC + "TaxableAmount", currencyID="COP").text = _fmt_money(total_base)
    etree.SubElement(ts, CBC + "TaxAmount", currencyID="COP").text = _fmt_money(iva)
    etree.SubElement(ts, CBC + "Percent").text = str(iva_porcentaje)
    tc = etree.SubElement(ts, CAC + "TaxCategory")
    tsch = etree.SubElement(tc, CAC + "TaxScheme")
    etree.SubElement(tsch, CBC + "ID", schemeAgencyID="6", schemeName="IVA").text = "01"
    etree.SubElement(tsch, CBC + "Name").text = "IVA"

    # Monetary total
    mt = _el(CAC + "LegalMonetaryTotal")
    etree.SubElement(mt, CBC + "LineExtensionAmount", currencyID="COP").text = _fmt_money(total_base)
    etree.SubElement(mt, CBC + "TaxExclusiveAmount", currencyID="COP").text = _fmt_money(total_base)
    etree.SubElement(mt, CBC + "TaxInclusiveAmount", currencyID="COP").text = _fmt_money(total)
    etree.SubElement(mt, CBC + "PayableAmount", currencyID="COP").text = _fmt_money(total)

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

        pr = etree.SubElement(li, CAC + "PricingReference")
        ap = etree.SubElement(pr, CAC + "AlternativeConditionPrice")
        etree.SubElement(ap, CBC + "PriceAmount", currencyID="COP").text = _fmt_money(pu)
        etree.SubElement(ap, CBC + "PriceTypeCode",
                         listName="Precio de venta al público").text = "01"

        lt = etree.SubElement(li, CAC + "TaxTotal")
        iva_line = subt - (subt / (1 + iva_porcentaje / 100))
        etree.SubElement(lt, CBC + "TaxAmount", currencyID="COP").text = _fmt_money(iva_line)

        line_item = etree.SubElement(li, CAC + "Item")
        cod = item.get("codigo") or item.get("codigo_producto") or ""
        if cod:
            sid = etree.SubElement(line_item, CAC + "SellersItemIdentification")
            etree.SubElement(sid, CBC + "ID").text = str(cod)
        etree.SubElement(line_item, CBC + "Description").text = str(item.get("nombre", ""))

        px = etree.SubElement(li, CAC + "Price")
        etree.SubElement(px, CBC + "PriceAmount", currencyID="COP").text = _fmt_money(pu)

    xml_bytes = etree.tostring(
        inv, pretty_print=True, xml_declaration=True, encoding="UTF-8",
        standalone=True,
    )
    return xml_bytes


def _add_party_id(party, nit, scheme_id="4"):
    pi = etree.SubElement(party, CAC + "PartyIdentification")
    etree.SubElement(pi, CBC + "ID", schemeAgencyID="6",
                     schemeID=scheme_id).text = str(nit)


def _add_tax_scheme(party, name, nit, code="48"):
    ts = etree.SubElement(party, CAC + "PartyTaxScheme")
    etree.SubElement(ts, CBC + "RegistrationName").text = name
    etree.SubElement(ts, CBC + "CompanyID", schemeAgencyID="6",
                     schemeID="4").text = str(nit)
    etree.SubElement(ts, CBC + "TaxLevelCode",
                     listName="Régimen de IVA").text = code
    tsch = etree.SubElement(ts, CAC + "TaxScheme")
    etree.SubElement(tsch, CBC + "ID", schemeAgencyID="6",
                     schemeName="IVA").text = "01"
    etree.SubElement(tsch, CBC + "Name").text = "IVA"


def _add_addr(party, municipio, depto, pais):
    addr = etree.SubElement(party, CAC + "RegistrationAddress")
    etree.SubElement(addr, CBC + "ID", schemeAgencyID="6",
                     schemeName="Codigo Municipio").text = str(municipio)
    if settings.emisor_direccion:
        etree.SubElement(addr, CBC + "Line").text = settings.emisor_direccion
    alc = etree.SubElement(addr, CAC + "AddressLine")
    etree.SubElement(alc, CBC + "Line").text = f"Municipio: {municipio}, Depto: {depto}"
    ctry = etree.SubElement(addr, CAC + "Country")
    etree.SubElement(ctry, CBC + "IdentificationCode",
                     listAgencyID="6", listID="ISO 3166-1",
                     name="Colombia").text = pais
