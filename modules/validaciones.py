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
# Se guardan las referencias a los comandos registrados para reutilizarlos
_cmds: dict = {}


def registrar_validaciones(root: tk.Misc):
    """
    Registra todas las funciones de validación en el widget raíz.
    Llamar UNA sola vez al arrancar la aplicación (en LoginWindow.__init__).
    """
    _cmds["entero"]    = (root.register(_validar_entero),    "%P")
    _cmds["positivo"]  = (root.register(_validar_positivo),  "%P")
    _cmds["monto"]     = (root.register(_validar_monto),     "%P")
    _cmds["cantidad"]  = (root.register(_validar_cantidad),  "%P")
    _cmds["codigo"]    = (root.register(_validar_codigo),    "%P")


# ── Funciones de validación ───────────────────────────────────────────────────

def _validar_entero(valor_propuesto: str) -> bool:
    """
    Acepta solo dígitos enteros positivos o campo vacío.
    Úsalo para: stock, cantidades, denominaciones de caja.
    """
    return valor_propuesto == "" or valor_propuesto.isdigit()


def _validar_positivo(valor_propuesto: str) -> bool:
    """
    Acepta enteros positivos mayores a cero o campo vacío.
    Úsalo para: cantidad mínima de 1 en carrito.
    """
    return valor_propuesto == "" or valor_propuesto.isdigit()


def _validar_monto(valor_propuesto: str) -> bool:
    """
    Acepta enteros sin signo negativo o campo vacío.
    Úsalo para: precios, costos, montos de caja, descuentos.
    """
    return valor_propuesto == "" or valor_propuesto.isdigit()


def _validar_cantidad(valor_propuesto: str) -> bool:
    """
    Acepta enteros positivos o campo vacío.
    Úsalo para: cantidades en carrito y cuentas.
    """
    return valor_propuesto == "" or (valor_propuesto.isdigit() and int(valor_propuesto) >= 0)


def _validar_codigo(valor_propuesto: str) -> bool:
    """
    Acepta letras, números, guiones y guiones bajos (sin espacios ni tildes).
    Úsalo para: códigos de producto (SKU).
    """
    if valor_propuesto == "":
        return True
    permitidos = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
    return all(c in permitidos for c in valor_propuesto)


# ── Aplicar validación a un Entry existente ───────────────────────────────────

def aplicar_validacion(entry: tk.Entry, tipo: str):
    """
    Aplica una validación registrada a un Entry.

    tipos disponibles:
        'entero'   — solo dígitos, sin límite (stock, denominaciones)
        'positivo' — solo dígitos positivos (cantidad mínima 1)
        'monto'    — enteros sin negativo (precios, montos de caja)
        'cantidad' — enteros >= 0 (carrito, cuentas)
        'codigo'   — alfanumérico + guión (SKU de producto)

    Si las validaciones no están registradas aún, hace un registro
    automático usando el widget raíz del entry.
    """
    if not _cmds:
        registrar_validaciones(entry.winfo_toplevel())

    if tipo not in _cmds:
        raise ValueError(f"Tipo de validación desconocido: '{tipo}'. "
                         f"Opciones: {list(_cmds.keys())}")

    vcmd = _cmds[tipo]
    entry.config(
        validate="key",
        validatecommand=vcmd,
    )


# ── Helpers de lectura segura ─────────────────────────────────────────────────

def leer_entero(entry: tk.Entry, default: int = 0) -> int:
    """
    Lee el valor de un Entry numérico de forma segura.
    Retorna default si el campo está vacío o contiene un valor inválido.
    """
    valor = entry.get().strip()
    try:
        return int(valor) if valor else default
    except ValueError:
        return default


def leer_texto(entry: tk.Entry, default: str = "") -> str:
    """Lee y limpia el texto de un Entry."""
    return entry.get().strip() or default
