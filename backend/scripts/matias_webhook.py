#!/usr/bin/env python3
"""
Registro del webhook de Matias API (recibir el veredicto DIAN asíncrono).

Sólo librería estándar; corre con cualquier Python. Se ejecuta a mano una vez
(o cuando cambie la URL pública). Necesita:
  1. un PAT válido (MATIAS_TOKEN) — el mismo de backend/.env,
  2. una URL HTTPS PÚBLICA que apunte a nuestro endpoint receptor:
         https://TU-DOMINIO/webhooks/fe/matias
     (en desarrollo puedes exponerla con un túnel: cloudflared / ngrok).

Matias devuelve el `secret` HMAC UNA sola vez al registrar: cópialo en
backend/.env como MATIAS_WEBHOOK_SECRET (con eso verificamos X-Webhook-Signature).

Uso:

    # registrar (la URL se arma sola a partir del dominio público)
    MATIAS_TOKEN=... python3 backend/scripts/matias_webhook.py registrar \
        --public-url https://pos.midominio.com

    # o pasar la URL completa del endpoint
    MATIAS_TOKEN=... python3 backend/scripts/matias_webhook.py registrar \
        --url https://pos.midominio.com/webhooks/fe/matias

    # listar los webhooks registrados
    MATIAS_TOKEN=... python3 backend/scripts/matias_webhook.py listar

    # borrar uno por id
    MATIAS_TOKEN=... python3 backend/scripts/matias_webhook.py borrar --id 123
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "https://api-v2.matias-api.com/api/ubl2.1"

# Ruta de nuestro endpoint receptor (app/routes/webhooks.py -> /webhooks/fe/{proveedor}).
RUTA_RECEPTORA = "/webhooks/fe/matias"

# Eventos que sabemos manejar (ver _EVENTO_ESTADO en app/fe/proveedores/matias.py).
EVENTOS_DEFECTO = ["document.accepted", "document.rejected", "document.voided"]


def _request(method: str, url: str, body: dict | None = None,
             token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8") or "{}"
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw}
    except urllib.error.URLError as e:
        print(f"✗ Error de conexión: {e}", file=sys.stderr)
        sys.exit(2)


def _resolver_url(args) -> str:
    """URL final del endpoint receptor a partir de --url o --public-url."""
    if args.url:
        url = args.url.strip()
    elif args.public_url:
        base = args.public_url.strip().rstrip("/")
        url = f"{base}{RUTA_RECEPTORA}"
    else:
        print("✗ Falta la URL. Usa --url o --public-url.", file=sys.stderr)
        sys.exit(2)
    if not url.startswith("https://"):
        print(f"✗ La URL del webhook debe ser HTTPS pública: {url}", file=sys.stderr)
        sys.exit(2)
    return url


def registrar(base: str, token: str, url: str, eventos: list[str]) -> None:
    print(f"› Registrando webhook → {url}")
    print(f"  eventos: {', '.join(eventos)}\n")
    status, data = _request(
        "POST", f"{base}/webhooks",
        {"url": url, "events": eventos},
        token=token,
    )
    if status >= 400:
        print(f"✗ Registro falló (HTTP {status}): {data}", file=sys.stderr)
        sys.exit(1)

    # El secret HMAC se devuelve UNA sola vez; el nombre del campo puede variar.
    secret = (
        data.get("secret")
        or data.get("signing_secret")
        or (data.get("data") or {}).get("secret")
    )
    wh_id = data.get("id") or (data.get("data") or {}).get("id")
    print(f"✓ Webhook registrado (id={wh_id}).")
    if secret:
        print("\n  Copia este secret en backend/.env (se muestra una sola vez):\n")
        print(f"    MATIAS_WEBHOOK_SECRET={secret}\n")
    else:
        print("⚠ No ubiqué el secret en la respuesta. Respuesta completa:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("\n  Busca el campo del secret y ponlo en MATIAS_WEBHOOK_SECRET.")


def listar(base: str, token: str) -> None:
    status, data = _request("GET", f"{base}/webhooks", token=token)
    if status >= 400:
        print(f"✗ Listado falló (HTTP {status}): {data}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(data, indent=2, ensure_ascii=False))


def borrar(base: str, token: str, wh_id: str) -> None:
    status, data = _request("DELETE", f"{base}/webhooks/{wh_id}", token=token)
    if status >= 400:
        print(f"✗ Borrado falló (HTTP {status}): {data}", file=sys.stderr)
        sys.exit(1)
    print(f"✓ Webhook {wh_id} borrado.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Registro de webhook Matias API")
    parser.add_argument("accion", choices=["registrar", "listar", "borrar"])
    parser.add_argument("--base", default=os.environ.get("MATIAS_BASE_URL", DEFAULT_BASE))
    parser.add_argument("--token", default=None, help="PAT (o MATIAS_TOKEN en el entorno)")
    parser.add_argument("--url", default=None, help="URL completa del endpoint receptor")
    parser.add_argument("--public-url", default=None,
                        help="Dominio público; se le agrega " + RUTA_RECEPTORA)
    parser.add_argument("--eventos", default=",".join(EVENTOS_DEFECTO),
                        help="Lista de eventos separados por coma")
    parser.add_argument("--id", default=None, help="id del webhook (para 'borrar')")
    args = parser.parse_args()

    token = args.token or os.environ.get("MATIAS_TOKEN")
    if not token:
        print("✗ Falta el token. Usa --token o MATIAS_TOKEN=...", file=sys.stderr)
        sys.exit(2)

    base = args.base.rstrip("/")

    if args.accion == "registrar":
        url = _resolver_url(args)
        eventos = [e.strip() for e in args.eventos.split(",") if e.strip()]
        registrar(base, token, url, eventos)
    elif args.accion == "listar":
        listar(base, token)
    elif args.accion == "borrar":
        if not args.id:
            print("✗ Falta --id del webhook a borrar.", file=sys.stderr)
            sys.exit(2)
        borrar(base, token, args.id)


if __name__ == "__main__":
    main()
