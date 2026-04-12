"""
ui/base.py — El G POS
Paleta de colores, fuentes y clase base FrameBase.
"""
import tkinter as tk
from tkinter import ttk
import auth

COLORS = {
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
}

FONT_TITLE  = ("Segoe UI", 22, "bold")
FONT_SUB    = ("Segoe UI", 11)
FONT_LABEL  = ("Segoe UI", 10)
FONT_BOLD   = ("Segoe UI", 10, "bold")
FONT_SMALL  = ("Segoe UI", 9)
FONT_NAV    = ("Segoe UI", 10, "bold")
FONT_KPI    = ("Segoe UI", 26, "bold")

class FrameBase(tk.Frame):
    def __init__(self, parent, titulo, subtitulo=""):
        super().__init__(parent, bg=COLORS["bg"])
        self._build_header(titulo, subtitulo)

    def _build_header(self, titulo, subtitulo):
        header = tk.Frame(self, bg=COLORS["bg"])
        header.pack(fill="x", padx=32, pady=(28, 0))

        tk.Label(header, text=titulo, font=FONT_TITLE,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w")
        if subtitulo:
            tk.Label(header, text=subtitulo, font=FONT_SUB,
                     bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(anchor="w", pady=(2, 0))

        sep = tk.Frame(self, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=32, pady=16)

    def _card(self, parent, **kwargs):
        """Crea un frame con estilo de tarjeta."""
        return tk.Frame(parent, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"],
                        highlightthickness=1, **kwargs)

    def _label_muted(self, parent, text, **kwargs):
        return tk.Label(parent, text=text, font=FONT_SMALL,
                        bg=COLORS["surface"], fg=COLORS["text_muted"], **kwargs)

    def _btn_primary(self, parent, text, cmd, **kwargs):
        return tk.Button(parent, text=text, font=FONT_BOLD,
                         bg=COLORS["accent"], fg=COLORS["text"],
                         activebackground=COLORS["accent_hover"],
                         activeforeground=COLORS["text"],
                         relief="flat", cursor="hand2",
                         command=cmd, **kwargs)

    def _btn_danger(self, parent, text, cmd, **kwargs):
        return tk.Button(parent, text=text, font=FONT_BOLD,
                         bg=COLORS["danger"], fg=COLORS["text"],
                         activebackground="#cc4444",
                         activeforeground=COLORS["text"],
                         relief="flat", cursor="hand2",
                         command=cmd, **kwargs)

    def _input(self, parent, **kwargs):
        return tk.Entry(parent, font=FONT_LABEL,
                        bg=COLORS["surface2"], fg=COLORS["text"],
                        insertbackground=COLORS["accent"],
                        relief="flat", bd=0,
                        highlightthickness=1,
                        highlightbackground=COLORS["border"],
                        highlightcolor=COLORS["accent"], **kwargs)

    def _tabla(self, parent, columnas, alto=10):
        """Crea un Treeview con estilo consistente."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("POS.Treeview",
                        background=COLORS["surface"],
                        foreground=COLORS["text"],
                        fieldbackground=COLORS["surface"],
                        rowheight=28,
                        font=FONT_LABEL,
                        borderwidth=0)
        style.configure("POS.Treeview.Heading",
                        background=COLORS["surface2"],
                        foreground=COLORS["text_muted"],
                        font=FONT_BOLD,
                        relief="flat")
        style.map("POS.Treeview",
                  background=[("selected", COLORS["accent"])],
                  foreground=[("selected", COLORS["text"])])

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

