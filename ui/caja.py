"""
ui/caja.py — El G POS
"""
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI

class FrameCaja(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Caja", "Apertura y cierre de turno")
        self._build()

    def _build(self):
        from modules.caja import get_sesion_activa, formatear_pesos, DENOMINACIONES_COP

        sesion = get_sesion_activa()
        main   = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        if not sesion:
            self._panel_apertura(main)
        else:
            self._panel_cierre(main, sesion)

    def _panel_apertura(self, parent):
        card = self._card(parent, width=360)
        card.pack(anchor="center", pady=40, ipadx=20, ipady=20)

        tk.Label(card, text="Abrir Caja", font=FONT_TITLE,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(20, 4))
        tk.Label(card, text="Ingresa el monto base en efectivo",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(pady=(0, 20))

        tk.Label(card, text="Monto base ($)", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=30)
        self.entry_base = self._input(card)
        self.entry_base.pack(padx=30, fill="x", pady=(4, 20), ipady=6)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_base, "monto")

        self._btn_primary(card, "Abrir caja", self._abrir).pack(
            padx=30, fill="x", ipady=10, pady=(0, 20))

    def _abrir(self):
        from modules.caja import abrir_caja
        try:
            monto = float(self.entry_base.get().replace(".", "").replace(",", "."))
            abrir_caja(monto)
            messagebox.showinfo("Caja abierta", "✓ Caja abierta correctamente.")
            self.winfo_toplevel()._mostrar_caja()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _panel_cierre(self, parent, sesion):
        from modules.caja import DENOMINACIONES_COP, formatear_pesos, calcular_desde_denominaciones

        tk.Label(parent, text=f"Caja abierta por: {sesion['cajero']}  ·  Desde: {sesion['apertura'][:16]}",
                 font=FONT_SMALL, bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(anchor="w", pady=(0, 16))

        cols = tk.Frame(parent, bg=COLORS["bg"])
        cols.pack(fill="both", expand=True)

        # Denominaciones
        denom_card = self._card(cols)
        denom_card.pack(side="left", fill="y", padx=(0, 12), ipadx=10, ipady=10)

        tk.Label(denom_card, text="Conteo de denominaciones",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 8))

        self._denom_entries = {}
        self._lbl_contado   = None

        for denom in reversed(DENOMINACIONES_COP):
            fila = tk.Frame(denom_card, bg=COLORS["surface"])
            fila.pack(fill="x", padx=16, pady=2)
            tk.Label(fila, text=formatear_pesos(denom), font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["text"],
                     width=12, anchor="w").pack(side="left")
            entry = self._input(fila, width=6)
            entry.insert(0, "0")
            entry.pack(side="left", padx=8, ipady=4)
            entry.bind("<KeyRelease>", lambda e: self._actualizar_contado())
            from modules.validaciones import aplicar_validacion
            aplicar_validacion(entry, "entero")

            subtotal_lbl = tk.Label(fila, text="$0", font=FONT_SMALL,
                                     bg=COLORS["surface"], fg=COLORS["text_muted"],
                                     width=12, anchor="e")
            subtotal_lbl.pack(side="left")
            self._denom_entries[denom] = (entry, subtotal_lbl)

        # Resumen
        resumen_card = self._card(cols)
        resumen_card.pack(side="left", fill="both", expand=True, ipady=10)

        tk.Label(resumen_card, text="Resumen del turno",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", padx=20, pady=(16, 12))

        from modules.caja import formatear_pesos
        datos = [
            ("Monto base:",        formatear_pesos(sesion["monto_base"])),
            ("Ventas del turno:",  formatear_pesos(sesion["total_ventas"])),
            ("Total esperado:",    formatear_pesos(sesion["monto_base"] + sesion["total_ventas"])),
        ]
        for label, valor in datos:
            fila = tk.Frame(resumen_card, bg=COLORS["surface"])
            fila.pack(fill="x", padx=20, pady=4)
            tk.Label(fila, text=label, font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
            tk.Label(fila, text=valor, font=FONT_BOLD,
                     bg=COLORS["surface"], fg=COLORS["text"]).pack(side="right")

        sep = tk.Frame(resumen_card, bg=COLORS["border"], height=1)
        sep.pack(fill="x", padx=20, pady=12)

        fila_contado = tk.Frame(resumen_card, bg=COLORS["surface"])
        fila_contado.pack(fill="x", padx=20)
        tk.Label(fila_contado, text="Monto contado:", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(side="left")
        self.lbl_contado = tk.Label(fila_contado, text="$0", font=FONT_KPI,
                                     bg=COLORS["surface"], fg=COLORS["accent"])
        self.lbl_contado.pack(side="right")

        self.lbl_diferencia = tk.Label(resumen_card, text="",
                                        font=FONT_BOLD, bg=COLORS["surface"])
        self.lbl_diferencia.pack(anchor="e", padx=20, pady=4)

        # Notas
        tk.Label(resumen_card, text="Notas (opcional)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=20, pady=(12, 4))
        self.txt_notas = tk.Text(resumen_card, height=3, font=FONT_SMALL,
                                  bg=COLORS["surface2"], fg=COLORS["text"],
                                  insertbackground=COLORS["accent"],
                                  relief="flat",
                                  highlightthickness=1,
                                  highlightbackground=COLORS["border"])
        self.txt_notas.pack(fill="x", padx=20)

        self._btn_danger(resumen_card, "Cerrar caja",
                         self._cerrar).pack(fill="x", padx=20, pady=20, ipady=10)

    def _actualizar_contado(self):
        from modules.caja import formatear_pesos, calcular_desde_denominaciones, DENOMINACIONES_COP
        denominaciones = {}
        for denom, (entry, lbl_sub) in self._denom_entries.items():
            try:
                cant = int(entry.get() or 0)
            except ValueError:
                cant = 0
            denominaciones[denom] = cant
            lbl_sub.config(text=formatear_pesos(denom * cant))

        total = calcular_desde_denominaciones(denominaciones)
        self.lbl_contado.config(text=formatear_pesos(total))

    def _cerrar(self):
        from modules.caja import cerrar_caja, get_sesion_activa, formatear_pesos
        denominaciones = {}
        for denom, (entry, _) in self._denom_entries.items():
            try:
                denominaciones[denom] = int(entry.get() or 0)
            except ValueError:
                denominaciones[denom] = 0

        notas = self.txt_notas.get("1.0", "end").strip()
        try:
            resumen = cerrar_caja(denominaciones, notas or None)
            dif     = resumen["diferencia"]
            color   = COLORS["success"] if dif >= 0 else COLORS["danger"]
            msg     = (
                f"Caja cerrada correctamente.\n\n"
                f"Esperado:  {formatear_pesos(resumen['monto_esperado'])}\n"
                f"Contado:   {formatear_pesos(resumen['monto_contado'])}\n"
                f"Diferencia: {formatear_pesos(dif)}"
            )
            messagebox.showinfo("Cierre de caja", msg)
            self.winfo_toplevel()._mostrar_caja()
        except Exception as e:
            messagebox.showerror("Error", str(e))

