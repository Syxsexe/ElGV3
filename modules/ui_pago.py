"""
modules/ui_pago.py — El G POS
Diálogo de cobro reutilizable: pago simple, digital y mixto.
"""

import tkinter as tk
from tkinter import messagebox

COLORS = {
    "bg":           "#0F1117",
    "surface":      "#1A1D27",
    "surface2":     "#22263A",
    "border":       "#2E3350",
    "accent":       "#6C63FF",
    "accent_hover": "#8B84FF",
    "success":      "#43D9A2",
    "warning":      "#FFB547",
    "danger":       "#FF5757",
    "text":         "#E8E9F3",
    "text_muted":   "#7C8098",
    "text_dim":     "#4A4E6A",
}

FONT_LABEL = ("Segoe UI", 10)
FONT_BOLD  = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_KPI   = ("Segoe UI", 26, "bold")

# Métodos en dos filas de 3
_FILA1 = [("efectivo", "Efectivo"), ("tarjeta", "Tarjeta"), ("nequi", "Nequi")]
_FILA2 = [("daviplata", "Daviplata"), ("transferencia", "Transferencia"), ("mixto", "Mixto ⇄")]
METODOS_PAGO      = _FILA1 + _FILA2
METODOS_DIGITALES = ["tarjeta", "nequi", "daviplata", "transferencia"]


class DialogPago(tk.Toplevel):
    """
    Modal de cobro.  Llama a on_confirmar(pagos) donde pagos es:
        [{"metodo": str, "monto": float}, ...]
    """

    def __init__(self, parent, total: float, on_confirmar, titulo: str = "Cobrar venta"):
        super().__init__(parent)
        self.title(titulo)
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)
        self.grab_set()
        self.focus_force()

        self._total             = total
        self._on_confirmar      = on_confirmar
        self._metodo_sel        = "efectivo"
        self._metodo_digital_mx = tk.StringVar(value="nequi")
        self._pill_btns         = {}

        self._build()
        self.bind("<Return>", lambda e: self._confirmar())
        self.bind("<Escape>", lambda e: self.destroy())
        self._centrar()

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        from modules.caja import formatear_pesos

        outer = tk.Frame(self, bg=COLORS["bg"])
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        # ── Total ─────────────────────────────────────────────────────────────
        total_card = tk.Frame(outer, bg=COLORS["surface"],
                              highlightbackground=COLORS["border"],
                              highlightthickness=1)
        total_card.pack(fill="x")
        tk.Frame(total_card, bg=COLORS["accent"], height=3).pack(fill="x")
        tk.Label(total_card, text="Total a cobrar", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(10, 0))
        tk.Label(total_card, text=formatear_pesos(self._total),
                 font=FONT_KPI, bg=COLORS["surface"],
                 fg=COLORS["accent"]).pack(pady=(2, 12))

        # ── Método ────────────────────────────────────────────────────────────
        tk.Label(outer, text="Método de pago", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(anchor="w", pady=(14, 6))

        for fila in (_FILA1, _FILA2):
            row_f = tk.Frame(outer, bg=COLORS["bg"])
            row_f.pack(fill="x", pady=(0, 5))
            for key, label in fila:
                btn = tk.Button(
                    row_f, text=label, font=FONT_BOLD,
                    bg=COLORS["surface2"], fg=COLORS["text_muted"],
                    activebackground=COLORS["accent"],
                    activeforeground=COLORS["text"],
                    relief="flat", cursor="hand2",
                    pady=9,
                    command=lambda k=key: self._seleccionar_metodo(k),
                )
                btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
                self._pill_btns[key] = btn

        # ── Panel dinámico ────────────────────────────────────────────────────
        tk.Frame(outer, bg=COLORS["border"], height=1).pack(fill="x", pady=(6, 12))

        self._panel = tk.Frame(outer, bg=COLORS["bg"])
        self._panel.pack(fill="x")

        # ── Botones (siempre visibles al fondo) ───────────────────────────────
        tk.Frame(outer, bg=COLORS["border"], height=1).pack(fill="x", pady=(14, 12))

        btn_row = tk.Frame(outer, bg=COLORS["bg"])
        btn_row.pack(fill="x")

        cancel = tk.Button(
            btn_row, text="Cancelar", font=FONT_BOLD,
            bg=COLORS["surface2"], fg=COLORS["text_muted"],
            activebackground=COLORS["border"],
            relief="flat", cursor="hand2",
            command=self.destroy, width=10, pady=8,
        )
        cancel.pack(side="left")
        cancel.bind("<Enter>", lambda e: cancel.config(bg=COLORS["border"]))
        cancel.bind("<Leave>", lambda e: cancel.config(bg=COLORS["surface2"]))

        confirm = tk.Button(
            btn_row, text="✓  Confirmar pago", font=FONT_BOLD,
            bg=COLORS["accent"], fg=COLORS["text"],
            activebackground=COLORS["accent_hover"],
            relief="flat", cursor="hand2",
            command=self._confirmar,
        )
        confirm.pack(side="right", ipady=8, ipadx=20)
        confirm.bind("<Enter>", lambda e: confirm.config(bg=COLORS["accent_hover"]))
        confirm.bind("<Leave>", lambda e: confirm.config(bg=COLORS["accent"]))

        self._seleccionar_metodo("efectivo")

    # ── Método seleccionado ───────────────────────────────────────────────────

    def _seleccionar_metodo(self, key: str):
        self._metodo_sel = key
        for k, btn in self._pill_btns.items():
            btn.config(
                bg=COLORS["accent"] if k == key else COLORS["surface2"],
                fg=COLORS["text"]   if k == key else COLORS["text_muted"],
            )
        for w in self._panel.winfo_children():
            w.destroy()
        if key == "efectivo":
            self._render_efectivo()
        elif key == "mixto":
            self._render_mixto()
        else:
            self._render_digital(key)
        self._centrar()

    # ── Paneles dinámicos ─────────────────────────────────────────────────────

    def _render_efectivo(self):
        from modules.caja import formatear_pesos

        card = tk.Frame(self._panel, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"],
                        highlightthickness=1)
        card.pack(fill="x")

        inner = tk.Frame(card, bg=COLORS["surface"])
        inner.pack(fill="x", padx=16, pady=12)

        tk.Label(inner, text="Monto recibido ($)", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")

        self.entry_recibido = self._input(inner)
        self.entry_recibido.pack(fill="x", pady=(4, 10), ipady=8)
        self.entry_recibido.focus()
        self.entry_recibido.bind("<KeyRelease>", self._calcular_vuelto)

        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_recibido, "monto")

        vuelto_row = tk.Frame(inner, bg=COLORS["surface"])
        vuelto_row.pack(fill="x")
        tk.Label(vuelto_row, text="Vuelto", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self.lbl_vuelto = tk.Label(
            vuelto_row, text="—",
            font=("Segoe UI", 13, "bold"),
            bg=COLORS["surface"], fg=COLORS["text_dim"],
        )
        self.lbl_vuelto.pack(side="right")

    def _calcular_vuelto(self, event=None):
        from modules.caja import formatear_pesos
        try:
            recibido = float(
                self.entry_recibido.get().replace(".", "").replace(",", ".") or 0)
        except ValueError:
            recibido = 0
        vuelto = recibido - self._total
        if recibido == 0:
            self.lbl_vuelto.config(text="—", fg=COLORS["text_dim"])
        elif vuelto < 0:
            self.lbl_vuelto.config(
                text=f"Faltan {formatear_pesos(-vuelto)}", fg=COLORS["danger"])
        else:
            self.lbl_vuelto.config(
                text=formatear_pesos(vuelto), fg=COLORS["success"])

    def _render_digital(self, metodo: str):
        from modules.caja import formatear_pesos

        card = tk.Frame(self._panel, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"],
                        highlightthickness=1)
        card.pack(fill="x")

        inner = tk.Frame(card, bg=COLORS["surface"])
        inner.pack(fill="x", padx=16, pady=14)

        tk.Label(inner, text=metodo.capitalize(), font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        tk.Label(inner, text=formatear_pesos(self._total),
                 font=("Segoe UI", 17, "bold"),
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(anchor="w", pady=(4, 0))

    def _render_mixto(self):
        from modules.caja import formatear_pesos

        card = tk.Frame(self._panel, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"],
                        highlightthickness=1)
        card.pack(fill="x")

        inner = tk.Frame(card, bg=COLORS["surface"])
        inner.pack(fill="x", padx=16, pady=12)

        # Efectivo
        tk.Label(inner, text="Monto en efectivo ($)", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        self.entry_efectivo = self._input(inner)
        self.entry_efectivo.pack(fill="x", pady=(4, 12), ipady=8)
        self.entry_efectivo.focus()
        self.entry_efectivo.bind("<KeyRelease>", self._recalcular_digital)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_efectivo, "monto")

        # Método digital — pills
        tk.Label(inner, text="Método digital", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")

        pills_d = tk.Frame(inner, bg=COLORS["surface"])
        pills_d.pack(fill="x", pady=(6, 10))

        self._digital_btns = {}
        for m in METODOS_DIGITALES:
            btn = tk.Button(
                pills_d, text=m.capitalize(), font=FONT_SMALL,
                bg=COLORS["surface2"], fg=COLORS["text_muted"],
                activebackground=COLORS["accent"], activeforeground=COLORS["text"],
                relief="flat", cursor="hand2",
                pady=6,
                command=lambda k=m: self._sel_digital(k),
            )
            btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
            self._digital_btns[m] = btn

        self._sel_digital(self._metodo_digital_mx.get())

        # Monto digital auto
        tk.Frame(inner, bg=COLORS["border"], height=1).pack(fill="x", pady=(2, 8))

        resto_row = tk.Frame(inner, bg=COLORS["surface"])
        resto_row.pack(fill="x")
        tk.Label(resto_row, text="Monto digital", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self.lbl_digital = tk.Label(
            resto_row, text=formatear_pesos(self._total),
            font=("Segoe UI", 13, "bold"),
            bg=COLORS["surface"], fg=COLORS["success"],
        )
        self.lbl_digital.pack(side="right")

        self.lbl_aviso = tk.Label(
            inner, text="", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["warning"],
        )
        self.lbl_aviso.pack(anchor="w", pady=(6, 0))

    def _sel_digital(self, key: str):
        self._metodo_digital_mx.set(key)
        for k, btn in self._digital_btns.items():
            btn.config(
                bg=COLORS["accent"] if k == key else COLORS["surface2"],
                fg=COLORS["text"]   if k == key else COLORS["text_muted"],
            )

    def _recalcular_digital(self, event=None):
        from modules.caja import formatear_pesos
        try:
            efectivo = float(
                self.entry_efectivo.get().replace(".", "").replace(",", ".") or 0)
        except ValueError:
            efectivo = 0
        digital = self._total - efectivo
        if efectivo > self._total:
            self.lbl_digital.config(text="$0", fg=COLORS["text_muted"])
            self.lbl_aviso.config(text="El efectivo supera el total")
        elif digital <= 0:
            self.lbl_digital.config(text="$0", fg=COLORS["text_muted"])
            self.lbl_aviso.config(text="")
        else:
            self.lbl_digital.config(text=formatear_pesos(digital), fg=COLORS["success"])
            self.lbl_aviso.config(text="")

    # ── Confirmar ─────────────────────────────────────────────────────────────

    def _confirmar(self):
        metodo = self._metodo_sel

        if metodo == "mixto":
            try:
                raw      = self.entry_efectivo.get().replace(".", "").replace(",", ".")
                efectivo = float(raw) if raw else 0.0
            except ValueError:
                messagebox.showwarning(
                    "Monto inválido", "Ingresa un monto válido para efectivo.", parent=self)
                return
            if efectivo <= 0:
                messagebox.showwarning(
                    "Monto inválido",
                    "El monto en efectivo debe ser mayor a cero.", parent=self)
                return
            if efectivo >= self._total:
                messagebox.showwarning(
                    "Monto inválido",
                    "El efectivo cubre el total.\nSelecciona 'Efectivo' directamente.",
                    parent=self)
                return
            digital        = round(self._total - efectivo, 2)
            metodo_digital = self._metodo_digital_mx.get()
            pagos = [
                {"metodo": "efectivo",     "monto": round(efectivo, 2)},
                {"metodo": metodo_digital, "monto": digital},
            ]
        elif metodo == "efectivo":
            pagos = [{"metodo": "efectivo", "monto": self._total}]
        else:
            pagos = [{"metodo": metodo, "monto": self._total}]

        self.destroy()
        self._on_confirmar(pagos)

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _centrar(self):
        self.update_idletasks()
        w = max(self.winfo_reqwidth(), 480)
        h = self.winfo_reqheight() + 20   # margen de seguridad
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _input(self, parent, **kwargs):
        return tk.Entry(
            parent, font=FONT_LABEL,
            bg=COLORS["surface2"], fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            relief="flat", bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border"],
            highlightcolor=COLORS["accent"],
            **kwargs,
        )


def abrir_dialogo_pago(parent, total: float, on_confirmar, titulo: str = "Cobrar venta"):
    DialogPago(parent, total, on_confirmar, titulo)
