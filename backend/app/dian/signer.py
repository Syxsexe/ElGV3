"""
DIAN XML Digital Signer
Firma digital XML para facturación electrónica usando certificado ONAC.
"""

import os
import tempfile
from pathlib import Path

from lxml import etree
from signxml import XMLSigner, methods


def _load_certificate(cert_path: str | Path, password: str) -> tuple[bytes, str]:
    """
    Load a PKCS#12 (.p12) certificate.
    Returns (cert_bytes, password).
    """
    cert_path = Path(cert_path)
    if not cert_path.exists():
        raise FileNotFoundError(f"Certificate not found: {cert_path}")

    with open(cert_path, "rb") as f:
        cert_bytes = f.read()

    return cert_bytes, password


def firmar_xml(
    xml_bytes: bytes,
    cert_path: str | Path,
    cert_password: str,
    reference_uri: str | None = None,
) -> bytes:
    """
    Digitally signs a UBL 2.1 CO XML for DIAN.

    Args:
        xml_bytes: The unsigned XML content
        cert_path: Path to the .p12 certificate file
        cert_password: Certificate password
        reference_uri: URI reference for the signature (e.g., "#SETP1")

    Returns:
        Signed XML bytes ready for DIAN transmission
    """
    cert_bytes, password = _load_certificate(cert_path, cert_password)
    doc = etree.fromstring(xml_bytes)
    
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
        c14n_algorithm="http://www.w3.org/2001/10/xml-exc-c14n#",
    )

    signed_doc = signer.sign(
        doc,
        key=cert_bytes,
        cert=cert_bytes,
        password=password,
        reference_uri=reference_uri,
    )

    return etree.tostring(
        signed_doc, pretty_print=True, xml_declaration=True,
        encoding="UTF-8", standalone=True,
    )


def get_certificate_info(cert_path: str | Path, password: str) -> dict:
    """
    Extracts information from a PKCS#12 certificate.
    Returns dict with NIT, name, validity dates.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import pkcs12

    cert_path = Path(cert_path)
    if not cert_path.exists():
        return {"error": "Certificate not found"}

    with open(cert_path, "rb") as f:
        p12_data = f.read()

    try:
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            p12_data, password.encode() if password else None
        )
    except Exception as e:
        return {"error": f"Failed to load certificate: {e}"}

    if certificate is None:
        return {"error": "No certificate found in PKCS#12 file"}

    cert = certificate

    info = {
        "subject": str(cert.subject),
        "issuer": str(cert.issuer),
        "serial_number": str(cert.serial_number),
        "not_valid_before": cert.not_valid_before_utc.isoformat(),
        "not_valid_after": cert.not_valid_after_utc.isoformat(),
        "is_expired": cert.not_valid_after_utc < datetime.utcnow(),
        "signature_algorithm": cert.signature_algorithm_oid._name,
    }

    # Try to extract NIT from subject
    for attr in cert.subject:
        if attr.oid._name == "organizationIdentifier":
            info["nit"] = attr.value
            break
        if attr.oid._name == "organizationName":
            info["organization"] = attr.value

    return info


from datetime import datetime
