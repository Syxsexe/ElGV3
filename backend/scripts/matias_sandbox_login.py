#!/usr/bin/env python3
"""
Login en el SANDBOX de Matias API + generación de un PAT (token de integración).

Sirve para verificar si nuestra cuenta ya está replicada en el sandbox
(docs.matias-api.com dice que las credenciales son globales) y, si lo está,
obtener un PAT para configurar backend/.env sin esperar a soporte.

Es SEGURO: sólo hace login y crea un token. NO registra cuentas, NO emite
documentos, NO toca producción. Sólo librería estándar.

La contraseña NUNCA se pasa por argumento (quedaría en el historial del shell):
se lee de la variable de entorno MATIAS_SANDBOX_PASSWORD o se pide de forma
oculta por teclado.

Uso:

    # con el correo en variable de entorno (recomendado)
    MATIAS_SANDBOX_EMAIL=tu@email.com python3 backend/scripts/matias_sandbox_login.py

    # o pasando el correo por argumento (la clave igual se pide oculta)
    python3 backend/scripts/matias_sandbox_login.py --email tu@email.com

    # sólo probar el login, sin generar PAT
    python3 backend/scripts/matias_sandbox_login.py --email tu@email.com --solo-login
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "https://sandbox-api.matias-api.com/api/ubl2.1"


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


def _extraer(data: dict, *claves: str) -> str | None:
    """Busca la primera clave presente en data o en data['data']."""
    interno = data.get("data") if isinstance(data.get("data"), dict) else {}
    for clave in claves:
        valor = data.get(clave) or interno.get(clave)
        if valor:
            return valor
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", default=os.environ.get("MATIAS_SANDBOX_EMAIL"),
                        help="Correo de la cuenta (o var MATIAS_SANDBOX_EMAIL).")
    parser.add_argument("--base", default=DEFAULT_BASE,
                        help=f"Base del sandbox (por defecto {DEFAULT_BASE}).")
    parser.add_argument("--nombre-token", default="El G POS - integracion sandbox",
                        help="Nombre del PAT a generar.")
    parser.add_argument("--solo-login", action="store_true",
                        help="Sólo verificar el login, sin generar PAT.")
    args = parser.parse_args()

    email = (args.email or "").strip()
    if not email:
        print("✗ Falta el correo. Usa --email o la var MATIAS_SANDBOX_EMAIL.",
              file=sys.stderr)
        sys.exit(2)

    password = os.environ.get("MATIAS_SANDBOX_PASSWORD")
    if not password:
        password = getpass.getpass(f"Contraseña de {email} (oculta): ")
    if not password:
        print("✗ Contraseña vacía.", file=sys.stderr)
        sys.exit(2)

    base = args.base.rstrip("/")

    # 1) Login
    print(f"› Login en sandbox → {base}/auth/login  ({email})")
    status, data = _request("POST", f"{base}/auth/login",
                            {"email": email, "password": password})
    if status == 404 or status == 401:
        print(f"\n✗ Login rechazado (HTTP {status}): {data}")
        print("  → La cuenta AÚN no está en el sandbox. Opciones:")
        print("    a) Registrarla contra producción (replica al sandbox), o")
        print("    b) Escribir a soporte@matias-api.com para que la habiliten.")
        sys.exit(1)
    if status >= 400:
        print(f"\n✗ Login falló (HTTP {status}): {data}", file=sys.stderr)
        sys.exit(1)

    access_token = _extraer(data, "access_token", "token")
    if not access_token:
        print(f"\n✗ Login OK pero no encontré access_token en la respuesta: {data}",
              file=sys.stderr)
        sys.exit(1)
    print("✓ Login correcto: la cuenta SÍ existe en el sandbox.\n")

    if args.solo_login:
        return

    # 2) Generar PAT
    print(f"› Generando PAT → {base}/auth/token  (nombre: {args.nombre_token})")
    status, data = _request("POST", f"{base}/auth/token",
                            {"name": args.nombre_token}, token=access_token)
    if status >= 400:
        print(f"\n✗ No se pudo generar el PAT (HTTP {status}): {data}", file=sys.stderr)
        sys.exit(1)

    pat = _extraer(data, "token", "access_token", "secret", "personal_access_token")
    if not pat:
        print(f"\n✗ PAT creado pero no encontré el valor en la respuesta: {data}",
              file=sys.stderr)
        sys.exit(1)

    print("✓ PAT generado. Cópialo en backend/.env (se muestra una sola vez):\n")
    print(f"    FE_PROVIDER=matias")
    print(f"    MATIAS_BASE_URL={base}")
    print(f"    MATIAS_TOKEN={pat}\n")
    print("  (No lo pongas en .env.example ni lo subas a git.)")


if __name__ == "__main__":
    main()
