"""
ui/base.py — El G POS
Paleta de colores, fuentes, temas (claro/oscuro) y clase base FrameBase.
"""
import json
import tkinter as tk
from tkinter import ttk
import auth
from paths import ruta_datos

# ── Temas ─────────────────────────────────────────────────────────────────────
_CONFIG_PATH = ruta_datos("config.json")

_DARK = {
    "bg":           "#0F1117",
    "surface":      "#1A1D27",
    "surface2":     "#22263A",
    "border":       "#2E3350",
    "accent":       "#6C63FF",
    "accent_hover": "#8B84FF",
    "accent2":      "#FF6584",
    "success":      "#43D9A2",
    "warning":      "#FFB547",
    "danger":       "#FF5757",
    "text":         "#E8E9F3",
    "text_muted":   "#7C8098",
    "text_dim":     "#4A4E6A",
    "on_accent":    "#FFFFFF",   # texto sobre fondos de color (botones accent/danger)
}

_LIGHT = {
    "bg":           "#F4F5FA",
    "surface":      "#FFFFFF",
    "surface2":     "#ECEEF6",
    "border":       "#D7DBE8",
    "accent":       "#6C63FF",
    "accent_hover": "#8B84FF",
    "accent2":      "#FF6584",
    "success":      "#1FA97D",
    "warning":      "#C77A12",
    "danger":       "#E23B3B",
    "text":         "#1B1E2B",
    "text_muted":   "#5C6178",
    "text_dim":     "#9499AE",
    "on_accent":    "#FFFFFF",
}

_TEMAS = {"oscuro": _DARK, "claro": _LIGHT}


def _leer_config() -> dict:
    try:
        return json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _guardar_config(cfg: dict) -> None:
    try:
        _CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    except OSError:
        pass


def tema_actual() -> str:
    """Nombre del tema activo: 'oscuro' | 'claro'."""
    return _leer_config().get("tema", "oscuro")


# Diccionario MUTABLE compartido por toda la app: nunca se reasigna, solo se muta
# en sitio para que `from ui.base import COLORS` siga apuntando al mismo objeto en
# todos los módulos (así un cambio de tema se propaga sin reimportar).
COLORS = {}
COLORS.update(_TEMAS.get(tema_actual(), _DARK))


def aplicar_tema(nombre: str) -> None:
    """Cambia la paleta activa (en sitio) y persiste la preferencia."""
    if nombre not in _TEMAS:
        nombre = "oscuro"
    COLORS.clear()
    COLORS.update(_TEMAS[nombre])
    cfg = _leer_config()
    cfg["tema"] = nombre
    _guardar_config(cfg)

FONT_TITLE  = ("Segoe UI", 24, "bold")
FONT_SUB    = ("Segoe UI", 11)
FONT_LABEL  = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_SMALL  = ("Segoe UI", 9)
FONT_NAV    = ("Segoe UI", 10, "bold")
FONT_KPI    = ("Segoe UI", 26, "bold")


def _add_hover(btn, color_normal, color_hover):
    """Agrega efecto hover real (Enter/Leave) a un tk.Button."""
    btn.bind("<Enter>", lambda e: btn.config(bg=color_hover))
    btn.bind("<Leave>", lambda e: btn.config(bg=color_normal))


class FrameBase(tk.Frame):
    def __init__(self, parent, titulo, subtitulo=""):
        super().__init__(parent, bg=COLORS["bg"])
        self._build_header(titulo, subtitulo)

    def _build_header(self, titulo, subtitulo):
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=32, pady=(28, 0))

        row = tk.Frame(header, bg=COLORS["bg"])
        row.pack(anchor="w")

        # Barra de acento izquierda
        tk.Frame(row, bg=COLORS["accent"], width=4).pack(
            side="left", fill="y", padx=(0, 14))

        col = tk.Frame(row, bg=COLORS["bg"])
        col.pack(side="left")

        tk.Label(col, text=titulo, font=FONT_TITLE,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w")
        if subtitulo:
            tk.Label(col, text=subtitulo, font=FONT_SUB,
                     bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(anchor="w", pady=(2, 0))

        tk.Frame(self, bg=COLORS["border"], height=1).pack(
            fill="x", padx=32, pady=18)

    def _card(self, parent, **kwargs):
        return tk.Frame(parent, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"],
                        highlightthickness=1, **kwargs)

    def _label_muted(self, parent, text, **kwargs):
        return tk.Label(parent, text=text, font=FONT_SMALL,
                        bg=COLORS["surface"], fg=COLORS["text_muted"], **kwargs)

    def _btn_primary(self, parent, text, cmd, **kwargs):
        btn = tk.Button(parent, text=text, font=FONT_BOLD,
                        bg=COLORS["accent"], fg=COLORS["on_accent"],
                        activebackground=COLORS["accent_hover"],
                        activeforeground=COLORS["on_accent"],
                        relief="flat", cursor="hand2",
                        command=cmd, **kwargs)
        _add_hover(btn, COLORS["accent"], COLORS["accent_hover"])
        return btn

    def _btn_danger(self, parent, text, cmd, **kwargs):
        btn = tk.Button(parent, text=text, font=FONT_BOLD,
                        bg=COLORS["danger"], fg=COLORS["on_accent"],
                        activebackground="#cc4444",
                        activeforeground=COLORS["on_accent"],
                        relief="flat", cursor="hand2",
                        command=cmd, **kwargs)
        _add_hover(btn, COLORS["danger"], "#cc4444")
        return btn

    def _btn_secondary(self, parent, text, cmd, **kwargs):
        """Botón secundario (surface) para acciones no primarias."""
        btn = tk.Button(parent, text=text, font=FONT_BOLD,
                        bg=COLORS["surface2"], fg=COLORS["text_muted"],
                        activebackground=COLORS["border"],
                        activeforeground=COLORS["text"],
                        relief="flat", cursor="hand2",
                        command=cmd, **kwargs)
        _add_hover(btn, COLORS["surface2"], COLORS["border"])
        return btn

    def _input(self, parent, **kwargs):
        return tk.Entry(parent, font=FONT_LABEL,
                        bg=COLORS["surface2"], fg=COLORS["text"],
                        insertbackground=COLORS["accent"],
                        relief="flat", bd=0,
                        highlightthickness=1,
                        highlightbackground=COLORS["border"],
                        highlightcolor=COLORS["accent"], **kwargs)

    def _tabla(self, parent, columnas, alto=10):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("POS.Treeview",
                        background=COLORS["surface"],
                        foreground=COLORS["text"],
                        fieldbackground=COLORS["surface"],
                        rowheight=30,
                        font=FONT_LABEL,
                        borderwidth=0)
        style.configure("POS.Treeview.Heading",
                        background=COLORS["surface2"],
                        foreground=COLORS["text_muted"],
                        font=FONT_BOLD,
                        relief="flat",
                        padding=(8, 6))
        style.map("POS.Treeview",
                  background=[("selected", COLORS["accent"])],
                  foreground=[("selected", COLORS["text"])])
        style.layout("POS.Treeview", [
            ("POS.Treeview.treearea", {"sticky": "nswe"}),
        ])

        tree = ttk.Treeview(parent, columns=columnas, show="headings",
                            height=alto, style="POS.Treeview")
        for col in columnas:
            tree.heading(col, text=col)
            tree.column(col, anchor="center", width=120)

        scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree
