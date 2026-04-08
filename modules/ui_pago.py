"""
modules/ui_pago.py — El G POS
Widget de pago reutilizable: soporta pago simple y pago mixto
(efectivo + un método digital). Se usa en FrameVentas y FrameCuentas.
"""

import tkinter as tk
from tkinter import ttk, messagebox

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
}

FONT_LABEL = ("Segoe UI", 10)
FONT_BOLD  = ("Segoe UI", 10, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_KPI   = ("Segoe UI", 22, "bold")

METODOS_DIGITALES = ["transferencia", "tarjeta", "nequi", "daviplata"]


class DialogPago(tk.Toplevel):
    """
    Ventana emergente de cobro con soporte para pago mixto.

    Al confirmar llama a on_confirmar(pagos) donde pagos es:
        [{"metodo": "efectivo", "monto": 10000},
         {"metodo": "nequi",    "monto": 5000}]
    Si es pago simple, la lista tiene un solo elemento.
    """

    def __init__(self, parent, total: float, on_confirmar, titulo: str = "Cobrar venta"):
        super().__init__(parent)
        self.title(titulo)
        self.configure(bg=COLORS["surface"])
        self.resizable(False, False)
        self.grab_set()          # modal
        self.focus_force()

        self._total        = total
        self._on_confirmar = on_confirmar
        self._mixto        = tk.BooleanVar(value=False)

        self._build()
        self._centrar(420, 400)

    def _centrar(self, w, h):
        self.update_idletasks()
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
            **kwargs
        )

    def _build(self):
        from modules.caja import formatear_pesos

        pad = {"padx": 24, "pady": 6}

        # Total
        tk.Label(self, text="Total a cobrar", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(20, 0))
        tk.Label(self, text=formatear_pesos(self._total), font=FONT_KPI,
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(pady=(0, 12))

        sep = tk.Frame(self, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=24, pady=(0, 12))

        # Toggle pago mixto
        chk = tk.Checkbutton(
            self, text="Pago mixto (efectivo + digital)",
            variable=self._mixto, font=FONT_LABEL,
            bg=COLORS["surface"], fg=COLORS["text"],
            selectcolor=COLORS["surface2"],
            activebackground=COLORS["surface"],
            activeforeground=COLORS["text"],
            command=self._toggle_mixto,
        )
        chk.pack(anchor="w", padx=24, pady=(0, 8))

        # ── Pago simple ───────────────────────────────────────────────────────
        self.frame_simple = tk.Frame(self, bg=COLORS["surface"])
        self.frame_simple.pack(fill="x", **pad)

        tk.Label(self.frame_simple, text="Método de pago", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        self.combo_simple = ttk.Combobox(
            self.frame_simple,
            values=["efectivo"] + METODOS_DIGITALES,
            font=FONT_LABEL, state="readonly", width=28
        )
        self.combo_simple.set("efectivo")
        self.combo_simple.pack(anchor="w", pady=(2, 0), ipady=4)

        # ── Pago mixto ────────────────────────────────────────────────────────
        self.frame_mixto = tk.Frame(self, bg=COLORS["surface"])
        # (no se hace pack todavía — aparece al activar el toggle)

        # Efectivo
        tk.Label(self.frame_mixto, text="Monto en efectivo ($)",
                 font=FONT_LABEL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).grid(row=0, column=0, sticky="w", pady=4)
        self.entry_efectivo = self._input(self.frame_mixto, width=16)
        self.entry_efectivo.grid(row=0, column=1, padx=(8, 0), ipady=5)
        self.entry_efectivo.bind("<KeyRelease>", self._recalcular_digital)

        # Digital
        tk.Label(self.frame_mixto, text="Método digital",
                 font=FONT_LABEL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).grid(row=1, column=0, sticky="w", pady=4)
        self.combo_digital = ttk.Combobox(
            self.frame_mixto, values=METODOS_DIGITALES,
            font=FONT_LABEL, state="readonly", width=14
        )
        self.combo_digital.set("nequi")
        self.combo_digital.grid(row=1, column=1, padx=(8, 0), ipady=4)

        tk.Label(self.frame_mixto, text="Monto digital ($)",
                 font=FONT_LABEL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).grid(row=2, column=0, sticky="w", pady=4)
        self.lbl_digital = tk.Label(
            self.frame_mixto, text=formatear_pesos(self._total),
            font=FONT_BOLD, bg=COLORS["surface"], fg=COLORS["success"]
        )
        self.lbl_digital.grid(row=2, column=1, padx=(8, 0), sticky="w")

        # Aviso diferencia
        self.lbl_aviso = tk.Label(
            self.frame_mixto, text="", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["warning"]
        )
        self.lbl_aviso.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        for child in self.frame_mixto.winfo_children():
            child.configure(bg=COLORS["surface"]) if isinstance(child, tk.Label) else None

        sep2 = tk.Frame(self, bg=COLORS["border"], height=1)
        sep2.pack(fill="x", padx=24, pady=12)

        # Botones
        btn_row = tk.Frame(self, bg=COLORS["surface"])
        btn_row.pack(fill="x", padx=24, pady=(0, 20))

        tk.Button(
            btn_row, text="Cancelar", font=FONT_BOLD,
            bg=COLORS["surface2"], fg=COLORS["text_muted"],
            activebackground=COLORS["border"],
            relief="flat", cursor="hand2",
            command=self.destroy, width=10
        ).pack(side="left")

        tk.Button(
            btn_row, text="✓  Confirmar pago", font=FONT_BOLD,
            bg=COLORS["accent"], fg=COLORS["text"],
            activebackground=COLORS["accent_hover"],
            relief="flat", cursor="hand2",
            command=self._confirmar
        ).pack(side="right", ipady=8, ipadx=16)

    def _toggle_mixto(self):
        if self._mixto.get():
            self.frame_simple.pack_forget()
            self.frame_mixto.pack(fill="x", padx=24, pady=4)
            self.entry_efectivo.focus()
        else:
            self.frame_mixto.pack_forget()
            self.frame_simple.pack(fill="x", padx=24, pady=6)

    def _recalcular_digital(self, event=None):
        from modules.caja import formatear_pesos
        try:
            efectivo = float(self.entry_efectivo.get().replace(".", "").replace(",", ".") or 0)
        except ValueError:
            efectivo = 0

        digital = self._total - efectivo

        if efectivo > self._total:
            self.lbl_digital.config(text="$0", fg=COLORS["text_muted"])
            self.lbl_aviso.config(
                text=f"⚠ El efectivo supera el total ({formatear_pesos(self._total)})"
            )
        elif digital < 0:
            self.lbl_digital.config(text="$0", fg=COLORS["text_muted"])
            self.lbl_aviso.config(text="")
        else:
            self.lbl_digital.config(
                text=formatear_pesos(digital),
                fg=COLORS["success"]
            )
            self.lbl_aviso.config(text="")

    def _confirmar(self):
        from modules.caja import formatear_pesos

        if self._mixto.get():
            # Pago mixto
            try:
                raw = self.entry_efectivo.get().replace(".", "").replace(",", ".")
                efectivo = float(raw) if raw else 0.0
            except ValueError:
                messagebox.showwarning("Monto inválido",
                                        "Ingresa un monto válido para efectivo.",
                                        parent=self)
                return

            if efectivo <= 0:
                messagebox.showwarning("Monto inválido",
                                        "El monto en efectivo debe ser mayor a cero.",
                                        parent=self)
                return

            if efectivo >= self._total:
                messagebox.showwarning("Monto inválido",
                                        "El efectivo cubre el total completo.\n"
                                        "Desactiva el pago mixto o ajusta el monto.",
                                        parent=self)
                return

            digital = round(self._total - efectivo, 2)
            metodo_digital = self.combo_digital.get()

            pagos = [
                {"metodo": "efectivo",      "monto": round(efectivo, 2)},
                {"metodo": metodo_digital,  "monto": digital},
            ]
        else:
            # Pago simple
            pagos = [{"metodo": self.combo_simple.get(), "monto": self._total}]

        self.destroy()
        self._on_confirmar(pagos)


def abrir_dialogo_pago(parent, total: float, on_confirmar, titulo: str = "Cobrar venta"):
    """
    Función de conveniencia para abrir el diálogo de pago.
    Uso:
        abrir_dialogo_pago(self, carrito.total(), self._procesar_pago)
    """
    DialogPago(parent, total, on_confirmar, titulo)
