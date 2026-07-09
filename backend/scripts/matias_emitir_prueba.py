#!/usr/bin/env python3
"""
Emisión de PRUEBA contra el SANDBOX de Matias (Fase 1/2 del go-live).

Emite una factura mínima (1 ítem, a CONSUMIDOR FINAL) usando el mismo camino
que el backend en producción (`MatiasProvider.emitir` → `construir_payload`).
Sirve para VALIDAR los catálogos DIAN de `matias_mapper.py` (city_id,
tax_regime_id, identity_document_id, country_id, unidades, tributos): si algún
ID está mal, el sandbox lo rechaza y nos dice cuál.

SEGURO: en sandbox NO hay documentos reales ante la DIAN. Aun así este script
ABORTA si `MATIAS_BASE_URL` apunta a producción (api-v2), para no emitir de verdad.

Imprime (1) el payload JSON que se envía y (2) la respuesta cruda del PT.

Uso:

    python3 backend/scripts/matias_emitir_prueba.py \
        --resolution 18760000001 --prefix SETP --number 990000001

Ajusta --resolution/--prefix/--number a lo que tenga registrado tu cuenta de
sandbox (si el número ya se usó, súbelo; el sandbox lleva su propio consecutivo).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Permite importar `app.*` y `config` corriendo el script desde cualquier cwd:
# backend/ es el padre de la carpeta scripts/.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--resolution", default="18760000001",
                        help="resolution_number registrado en la cuenta de sandbox.")
    parser.add_argument("--prefix", default="SETP", help="Prefijo de la resolución.")
    parser.add_argument("--number", type=int, default=990000001,
                        help="Consecutivo del documento de prueba.")
    parser.add_argument("--precio", type=str, default="10000",
                        help="Precio unitario del ítem (sin IVA).")
    parser.add_argument("--force-status", default=None,
                        help="X-Sandbox-Force-Status (ej. ERROR_REJECTED). "
                             "Déjalo vacío para validación real de catálogos.")
    args = parser.parse_args()

    load_dotenv(_BACKEND_DIR / ".env", override=True)

    base = os.environ.get("MATIAS_BASE_URL", "")
    if "sandbox" not in base:
        raise SystemExit(
            f"✗ ABORTADO: MATIAS_BASE_URL no es sandbox ({base!r}).\n"
            "  Este script solo corre contra sandbox. Ajusta backend/.env."
        )
    if args.force_status:
        os.environ["MATIAS_FORCE_STATUS"] = args.force_status

    # Importar después de cargar el .env para que el proveedor lea la config buena.
    from app.fe.base import AdquirienteFE, DocumentoFE, ItemFE
    from app.fe.proveedores.matias_mapper import construir_payload
    from app.fe import get_proveedor

    # Factura mínima: 1 ítem gravado 19%, a consumidor final.
    precio = Decimal(args.precio)              # base sin IVA
    iva = (precio * Decimal("0.19")).quantize(Decimal("0.01"))
    total = precio + iva

    item = ItemFE(
        descripcion="Producto de prueba (sandbox)",
        cantidad=Decimal("1"),
        precio_unit=precio,
        subtotal=precio,                       # sin IVA
        iva_porcentaje=Decimal("19"),
        iva_valor=iva,
        codigo="TEST-001",
    )
    doc = DocumentoFE(
        tipo="factura",
        prefijo=args.prefix,
        consecutivo=args.number,
        resolucion_numero=args.resolution,
        fecha_emision=datetime.now(),
        adquiriente=AdquirienteFE(nit="222222222222", razon_social="CONSUMIDOR FINAL"),
        items=[item],
        total_base=precio,
        iva=iva,
        total=total,
    )

    print("=" * 70)
    print("PAYLOAD que se enviará a Matias (POST /invoice):")
    print("=" * 70)
    payload = construir_payload(doc, generar_pdf=False, enviar_email=False)
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    prov = get_proveedor()
    print("\n" + "=" * 70)
    print(f"Emitiendo → {prov.base_url}/invoice  ({doc.numero})")
    print("=" * 70)
    res = asyncio.run(prov.emitir(doc))

    print(f"\nestado:   {res.estado}")
    print(f"numero:   {res.numero}")
    print(f"cufe:     {res.cufe}")
    print(f"track_id: {res.track_id}")
    print(f"mensaje:  {res.mensaje}")
    print(f"pdf_url:  {res.pdf_url}")
    print(f"xml_url:  {res.xml_url}")
    print("\n--- respuesta cruda del PT ---")
    print(json.dumps(res.raw, indent=2, ensure_ascii=False)[:4000])

    if res.estado in ("aceptada", "en_proceso"):
        print("\n✓ Emisión OK: los catálogos del payload son válidos para Matias.")
    else:
        print("\n⚠ No aceptada. Revisa 'mensaje'/respuesta cruda: si es un ID de "
              "catálogo inválido (city_id, tax_regime_id, etc.), corrígelo en "
              "app/fe/proveedores/matias_mapper.py y reintenta.")


if __name__ == "__main__":
    main()
