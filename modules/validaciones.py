"""
modules/validaciones.py — El G POS
Funciones de validación para campos de entrada Tkinter.
Se registran con widget.register() y se usan con validatecommand.

Uso típico:
    from modules.validaciones import registrar_validaciones, solo_entero

    registrar_validaciones(root)   # una sola vez al iniciar la app

    entry = tk.Entry(parent)
    aplicar_validacion(entry, "entero")
"""

import tkinter as tk


# ── Registro global ───────────────────────────────────────────────────────────
_cmds: dict = {}


def registrar_validaciones(root: tk.Misc):
    """
    Registra todas las funciones de validación en el widget raíz.
    Usa %d (acción) y %S (carácter) juntos:
      %d == "1"  → inserción → validar el carácter
      %d == "0"  → borrado (Backspace/Delete) → siempre permitir
      %d == "-1" → foco/otros → siempre permitir
    """
    _cmds["entero"]   = (root.register(_validar_entero),  "%d", "%S")
    _cmds["positivo"] = (root.register(_validar_entero),  "%d", "%S")
    _cmds["monto"]    = (root.register(_validar_entero),  "%d", "%S")
    _cmds["cantidad"] = (root.register(_validar_entero),  "%d", "%S")
    _cmds["decimal"]  = (root.register(_validar_decimal), "%d", "%S")
    _cmds["codigo"]   = (root.register(_validar_codigo),  "%d", "%S")
    _cmds["fecha"]    = (root.register(_validar_fecha),   "%d", "%S")


# ── Funciones de validación ───────────────────────────────────────────────────

def _validar_entero(accion: str, char: str) -> bool:
    """Solo dígitos 0-9. Permite borrado y foco."""
    if accion != "1":
        return True
    return char.isdigit()


def _validar_decimal(accion: str, char: str) -> bool:
    """
    Dígitos y un único punto decimal.
    Usado para stock de insumos (ej: 3000.5g, 1.5L).
    No valida el punto duplicado aquí — eso se maneja al leer el valor.
    """
    if accion != "1":
        return True
    return char.isdigit() or char == "."


def _validar_codigo(accion: str, char: str) -> bool:
    """Letras, números, guiones y guiones bajos."""
    if accion != "1":
        return True
    permitidos = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    return char in permitidos


def _validar_fecha(accion: str, char: str) -> bool:
    """Dígitos y guión — para fechas en formato YYYY-MM-DD."""
    if accion != "1":
        return True
    return char.isdigit() or char == "-"


# ── Aplicar validación a un Entry existente ───────────────────────────────────

def aplicar_validacion(entry: tk.Entry, tipo: str):
    """
    Aplica una validación de caracteres a un Entry.

    tipos disponibles:
        'entero'   — solo dígitos (stock, denominaciones, stock mínimo)
        'positivo' — solo dígitos (alias de entero)
        'monto'    — solo dígitos (precios, costos, montos de caja)
        'cantidad' — solo dígitos (carrito, cuentas)
        'codigo'   — alfanumérico + guión/guión_bajo (SKU de producto)
    """
    # Siempre registrar contra el intérprete del widget — evita usar comandos
    # de un tk.Tk anterior que ya fue destruido (caso LoginWindow → MainWindow).
    registrar_validaciones(entry.winfo_toplevel())

    if tipo not in _cmds:
        raise ValueError(f"Tipo desconocido: '{tipo}'. Opciones: {list(_cmds.keys())}")

    vcmd = _cmds[tipo]
    invcmd = (entry.register(lambda: None),)
    entry.config(
        validate="key",
        validatecommand=vcmd,
        invalidcommand=invcmd,
    )


# ── Helpers de lectura segura ─────────────────────────────────────────────────

def leer_entero(entry: tk.Entry, default: int = 0) -> int:
    """Lee un entero de un Entry. Retorna default si está vacío o inválido."""
    valor = entry.get().strip()
    try:
        return int(float(valor)) if valor else default
    except ValueError:
        return default


def leer_decimal(entry: tk.Entry, default: float = 0.0) -> float:
    """
    Lee un número decimal de un Entry.
    Usado para stock de insumos (ej: 3000.5g, 1500ml).
    Retorna default si está vacío o inválido.
    """
    valor = entry.get().strip()
    try:
        return float(valor) if valor else default
    except ValueError:
        return default


def leer_texto(entry: tk.Entry, default: str = "") -> str:
    """Lee y limpia el texto de un Entry."""
    return entry.get().strip() or default