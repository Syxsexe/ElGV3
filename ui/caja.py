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
        card = self._card(parent, width=400)
        card.pack(anchor="center", pady=40, ipadx=20, ipady=20)

        tk.Label(card, text="Abrir Caja", font=FONT_TITLE,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(20, 4))
        tk.Label(card, text="Ingresa los montos iniciales de cada caja",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(pady=(0, 20))

        # Efectivo
        tk.Label(card, text="Monto base efectivo ($)", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=30)
        self.entry_base = self._input(card)
        self.entry_base.pack(padx=30, fill="x", pady=(4, 16), ipady=6)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_base, "monto")

        # Digital
        tk.Label(card, text="Saldo inicial digital - Nequi/Transferencias ($)",
                 font=FONT_LABEL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=30)
        self.entry_base_digital = self._input(card)
        self.entry_base_digital.pack(padx=30, fill="x", pady=(4, 24), ipady=6)
        aplicar_validacion(self.entry_base_digital, "monto")

        self._btn_primary(card, "Abrir caja", self._abrir).pack(
            padx=30, fill="x", ipady=10, pady=(0, 20))

    def _abrir(self):
        from modules.caja import abrir_caja
        from modules.validaciones import leer_entero
        try:
            monto         = leer_entero(self.entry_base, default=0)
            monto_digital = leer_entero(self.entry_base_digital, default=0)
            if monto < 0 or monto_digital < 0:
                raise ValueError("Los montos no pueden ser negativos.")
            abrir_caja(monto, monto_base_digital=monto_digital)
            messagebox.showinfo("Caja abierta",
                                f"Caja abierta correctamente.\n"
                                f"Efectivo: ${monto:,}\n"
                                f"Digital:  ${monto_digital:,}")
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

        from modules.caja import formatear_pesos, migrar_dos_cajas
        from modules.proveedores import migrar_egresos
        from database import get_connection
        migrar_dos_cajas()
        migrar_egresos()

        base_ef   = sesion.get("monto_base", 0) or 0
        base_dig  = sesion.get("monto_base_digital", 0) or 0
        total_ef  = sesion.get("total_efectivo", 0) or 0
        total_dig = sesion.get("total_digital",  0) or 0

        # Egresos del turno separados por caja
        conn = get_connection()
        row_eg = conn.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN metodo_pago='efectivo'
                                 THEN total ELSE 0 END), 0) AS eg_ef,
                COALESCE(SUM(CASE WHEN metodo_pago!='efectivo'
                                 THEN total ELSE 0 END), 0) AS eg_dig
            FROM egresos WHERE sesion_id = ?
        """, (sesion["id"],)).fetchone()
        conn.close()
        eg_ef  = row_eg["eg_ef"]  if row_eg else 0
        eg_dig = row_eg["eg_dig"] if row_eg else 0

        esperado_ef  = base_ef  + total_ef  - eg_ef
        esperado_dig = base_dig + total_dig - eg_dig

        def fila_resumen(parent, label, valor, color=None):
            f = tk.Frame(parent, bg=COLORS["surface"])
            f.pack(fill="x", padx=20, pady=2)
            tk.Label(f, text=label, font=FONT_LABEL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
            tk.Label(f, text=formatear_pesos(valor), font=FONT_BOLD,
                     bg=COLORS["surface"],
                     fg=color or COLORS["text"]).pack(side="right")

        # ── CAJA EFECTIVO ─────────────────────────────────────────────────────
        tk.Label(resumen_card, text="CAJA EFECTIVO", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["accent"]).pack(
                     anchor="w", padx=20, pady=(0, 4))

        fila_resumen(resumen_card, "Inicial:",        base_ef)
        fila_resumen(resumen_card, "Ventas:",         total_ef,  COLORS["success"])
        fila_resumen(resumen_card, "Gastos:",         eg_ef,     COLORS["danger"])
        fila_resumen(resumen_card, "Esperado en caja:", esperado_ef, COLORS["accent"])

        tk.Frame(resumen_card, bg=COLORS["border"], height=1).pack(
            fill="x", padx=20, pady=8)

        fila_contado = tk.Frame(resumen_card, bg=COLORS["surface"])
        fila_contado.pack(fill="x", padx=20)
        tk.Label(fila_contado, text="Contado efectivo:", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(side="left")
        self.lbl_contado = tk.Label(fila_contado, text="$0", font=FONT_KPI,
                                     bg=COLORS["surface"], fg=COLORS["accent"])
        self.lbl_contado.pack(side="right")

        self.lbl_diferencia = tk.Label(resumen_card, text="",
                                        font=FONT_BOLD, bg=COLORS["surface"])
        self.lbl_diferencia.pack(anchor="e", padx=20, pady=4)

        # ── CAJA DIGITAL ──────────────────────────────────────────────────────
        tk.Frame(resumen_card, bg=COLORS["border"], height=1).pack(
            fill="x", padx=20, pady=(4, 8))

        tk.Label(resumen_card, text="CAJA DIGITAL", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["success"]).pack(
                     anchor="w", padx=20, pady=(0, 4))

        fila_resumen(resumen_card, "Inicial:",          base_dig)
        fila_resumen(resumen_card, "Ventas:",           total_dig, COLORS["success"])
        fila_resumen(resumen_card, "Gastos:",           eg_dig,    COLORS["danger"])
        fila_resumen(resumen_card, "Esperado en caja:", esperado_dig, COLORS["success"])

        tk.Frame(resumen_card, bg=COLORS["border"], height=1).pack(
            fill="x", padx=20, pady=8)

        # Campo conteo digital
        tk.Label(resumen_card, text="Saldo actual digital ($)", font=FONT_LABEL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=20)
        fila_dig_cont = tk.Frame(resumen_card, bg=COLORS["surface"])
        fila_dig_cont.pack(fill="x", padx=20, pady=(2, 0))
        self.entry_contado_digital = self._input(fila_dig_cont)
        self.entry_contado_digital.insert(0, str(int(esperado_dig)))
        self.entry_contado_digital.pack(side="left", fill="x", expand=True, ipady=5)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_contado_digital, "monto")

        self.lbl_dif_digital = tk.Label(resumen_card, text="",
                                         font=FONT_BOLD, bg=COLORS["surface"],
                                         fg=COLORS["text_muted"])
        self.lbl_dif_digital.pack(anchor="e", padx=20, pady=(2, 0))
        self.entry_contado_digital.bind(
            "<KeyRelease>",
            lambda e: self._actualizar_dif_digital(base_dig, total_dig - eg_dig)
        )
        self._esperado_ef = esperado_ef

        # Notas
        tk.Label(resumen_card, text="Notas (opcional)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=20, pady=(12, 4))
        self.txt_notas = tk.Text(resumen_card, height=3, font=FONT_SMALL,
                                  bg=COLORS["surface2"], fg=COLORS["text"],
                                  insertbackground=COLORS["accent"],
                                  relief="flat", highlightthickness=1,
                                  highlightbackground=COLORS["border"])
        self.txt_notas.pack(fill="x", padx=20)

        self._btn_danger(resumen_card, "Cerrar caja",
                         self._cerrar).pack(fill="x", padx=20, pady=20, ipady=10)

    def _actualizar_dif_digital(self, base_digital, total_digital):
        from modules.caja import formatear_pesos
        from modules.validaciones import leer_entero
        try:
            contado = leer_entero(self.entry_contado_digital, default=0)
            esperado = base_digital + total_digital
            dif = contado - esperado
            color = COLORS["success"] if dif >= 0 else COLORS["danger"]
            signo = "+" if dif >= 0 else ""
            self.lbl_dif_digital.config(
                text=f"Diferencia digital: {signo}{formatear_pesos(dif)}",
                fg=color
            )
        except Exception:
            pass

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
        from modules.validaciones import leer_entero
        denominaciones = {}
        for denom, (entry, _) in self._denom_entries.items():
            try:
                denominaciones[denom] = int(entry.get() or 0)
            except ValueError:
                denominaciones[denom] = 0

        denominaciones["digital"] = leer_entero(self.entry_contado_digital, default=0)

        notas = self.txt_notas.get("1.0", "end").strip()
        try:
            resumen = cerrar_caja(denominaciones, notas or None)
            dif_ef  = resumen["diferencia"]
            dif_dig = resumen["diferencia_digital"]

            def fmt_dif(d):
                signo = "+" if d >= 0 else ""
                return f"{signo}{formatear_pesos(d)}"

            msg = (
                f"Caja cerrada correctamente.\n\n"
                f"EFECTIVO\n"
                f"  Esperado:  {formatear_pesos(resumen['esperado_efectivo'])}\n"
                f"  Contado:   {formatear_pesos(resumen['monto_contado'])}\n"
                f"  Diferencia: {fmt_dif(dif_ef)}\n\n"
                f"DIGITAL\n"
                f"  Esperado:  {formatear_pesos(resumen['esperado_digital'])}\n"
                f"  Contado:   {formatear_pesos(resumen['esperado_digital'])}\n"
                f"  Diferencia: {fmt_dif(dif_dig)}"
            )

            # ── Sincronizar DEE POS con backend ─────────────────────────────
            from modules.dian_client import is_configured
            from modules.sync import get_sync_manager
            dian_msg = ""
            if is_configured():
                try:
                    sesion_data = {
                        "sesion_id": resumen["sesion_id"],
                        "monto_base": resumen.get("monto_base", 0),
                        "total_ventas": resumen.get("total_ventas", 0),
                        "total_efectivo": resumen.get("total_efectivo", 0),
                        "total_digital": resumen.get("total_digital", 0),
                        "denominaciones": resumen.get("denominaciones", []),
                        "notas": notas,
                    }
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                    if not loop.is_running():
                        sync_result = loop.run_until_complete(
                            get_sync_manager().process_cierre_caja(sesion_data)
                        )
                        if sync_result.get("status") == "sincronizado":
                            dian_msg = "\n\n✓ DEE POS transmitido a DIAN"
                        else:
                            dian_msg = "\n\n⚠ DEE POS en cola para transmisión"
                except Exception:
                    dian_msg = "\n\n⚠ No se pudo sincronizar con DIAN"

            messagebox.showinfo("Cierre de caja", msg + dian_msg)
            self.winfo_toplevel()._mostrar_caja()
        except Exception as e:
            messagebox.showerror("Error", str(e))