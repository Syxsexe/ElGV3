#!/usr/bin/env python3
"""
Setup de credenciales Matias API (login + generación de PAT).

No requiere dependencias externas (solo librería estándar), así corre con
cualquier Python. Pensado para ejecutarse a mano una vez, con TUS credenciales.

Uso típico (sandbox):

    # opción A: pasar email por flag, password se pide por teclado (no queda en historial)
    python3 backend/scripts/matias_setup.py pat --email tu@correo.com --name "ElG POS"

    # opción B: por variables de entorno
    MATIAS_EMAIL=tu@correo.com MATIAS_PASSWORD='...' \
        python3 backend/scripts/matias_setup.py pat --name "ElG POS"

    # solo probar el login
    python3 backend/scripts/matias_setup.py login --email tu@correo.com

El registro de la cuenta se hace en el portal/producción de Matias; las
credenciales se replican al sandbox. Este script asume que ya tienes cuenta.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

SANDBOX_BASE = "https://sandbox-api.matias-api.com/api/ubl2.1"


def _request(method: str, url: str, body: dict | None = None,
             token: str | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"raw": raw}
    except urllib.error.URLError as e:
        print(f"✗ Error de conexión: {e}", file=sys.stderr)
        sys.exit(2)


def _post(url: str, body: dict, token: str | None = None) -> tuple[int, dict]:
    return _request("POST", url, body, token)


# Bases candidatas para descubrir la correcta según la cuenta.
_BASES_CANDIDATAS = [
    "https://api-v2.matias-api.com/api/ubl2.1",
    "https://api-v2.matias-api.com",
    "https://sandbox-api.matias-api.com/api/ubl2.1",
]
# Endpoints de SOLO LECTURA para validar token+base (no emiten nada).
_ENDPOINTS_LECTURA = ["/v1/user", "/user", "/tokens"]


def check(base_arg: str, token: str) -> None:
    """Prueba (solo lectura) varias bases/endpoints para ver cuál autentica el token."""
    bases = [base_arg] + [b for b in _BASES_CANDIDATAS if b != base_arg]
    print("› Probando bases (solo lectura, sin emitir):\n")
    exito = False
    for base in bases:
        for ep in _ENDPOINTS_LECTURA:
            status, data = _request("GET", f"{base}{ep}", token=token)
            marca = "✓" if status == 200 else " "
            print(f"  [{marca}] GET {base}{ep}  →  HTTP {status}")
            if status == 200:
                exito = True
                print(f"      ↳ base válida: {base}")
        print()
    if exito:
        print("✓ Encontré al menos una base que autentica el token.")
        print("  Usa esa en backend/.env como MATIAS_BASE_URL.")
    else:
        print("✗ Ninguna base autenticó el token. Revisa que el token sea correcto")
        print("  o pide a soporte@matias-api.com la URL base de tu cuenta.")


def _resolver_credenciales(args) -> tuple[str, str]:
    email = args.email or os.environ.get("MATIAS_EMAIL")
    password = os.environ.get("MATIAS_PASSWORD")
    if not email:
        email = input("Email Matias: ").strip()
    if not password:
        password = getpass.getpass("Password Matias: ")
    if not email or not password:
        print("✗ Faltan email o password.", file=sys.stderr)
        sys.exit(2)
    return email, password


def login(base: str, email: str, password: str) -> str:
    status, data = _post(
        f"{base}/auth/login",
        {"email": email, "password": password, "remember_me": 0},
    )
    if status >= 400 or not data.get("access_token"):
        print(f"✗ Login falló (HTTP {status}): {data}", file=sys.stderr)
        sys.exit(1)
    print(f"✓ Login OK — access_token válido hasta {data.get('expires_at', '?')}")
    return data["access_token"]


def crear_pat(base: str, access_token: str, name: str, dias: int) -> None:
    status, data = _post(
        f"{base}/tokens",
        {"name": name, "description": "Token para El G POS", "expires_in_days": dias},
        token=access_token,
    )
    if status >= 400:
        print(f"✗ Creación de PAT falló (HTTP {status}): {data}", file=sys.stderr)
        sys.exit(1)

    # El token en claro se devuelve UNA sola vez; el nombre del campo varía según
    # versión (Laravel Sanctum suele usar plainTextToken).
    pat = (
        data.get("plainTextToken")
        or data.get("token")
        or data.get("access_token")
        or (data.get("data") or {}).get("token")
    )
    print("✓ PAT creado.")
    if pat:
        print("\n  Copia este token en backend/.env (se muestra una sola vez):\n")
        print(f"    MATIAS_TOKEN={pat}\n")
    else:
        print("⚠ No pude ubicar el token en la respuesta. Respuesta completa:")
        print(json.dumps(data, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Setup credenciales Matias API")
    parser.add_argument("accion", choices=["login", "pat", "check"],
                        help="login = probar login; pat = login + crear PAT; "
                             "check = validar token+base (solo lectura)")
    parser.add_argument("--base", default=os.environ.get("MATIAS_BASE_URL", SANDBOX_BASE))
    parser.add_argument("--email", default=None)
    parser.add_argument("--token", default=None, help="PAT ya generado (para 'check')")
    parser.add_argument("--name", default="ElG POS", help="nombre del PAT")
    parser.add_argument("--dias", type=int, default=90, help="expires_in_days (1-90)")
    args = parser.parse_args()

    # 'check' no necesita login: usa un token existente para probar bases.
    if args.accion == "check":
        token = args.token or os.environ.get("MATIAS_TOKEN")
        if not token:
            print("✗ Falta el token. Usa --token o MATIAS_TOKEN=...", file=sys.stderr)
            sys.exit(2)
        check(args.base, token)
        return

    print(f"› Base: {args.base}")
    email, password = _resolver_credenciales(args)
    access_token = login(args.base, email, password)

    if args.accion == "pat":
        crear_pat(args.base, access_token, args.name, args.dias)


if __name__ == "__main__":
    main()
