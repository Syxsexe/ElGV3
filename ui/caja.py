"""
ui/caja.py — El G POS
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
import auth
from ui.base import FrameBase, COLORS, FONT_TITLE, FONT_SUB, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_NAV, FONT_KPI

class FrameCaja(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Caja", "Apertura y cierre de turno")
        self._tab = tk.StringVar(value="turno")
        self._build()

    def _build(self):
        # Tabs — solo admin ve Historial
        tab_frame = tk.Frame(self, bg=COLORS["bg"])
        tab_frame.pack(fill="x", padx=32, pady=(0, 12))

        tabs = [("Turno actual", "turno")]
        if auth.get_sesion() and auth.get_sesion()["rol"] == "admin":
            tabs.append(("Historial", "historial"))

        for label, val in tabs:
            tk.Radiobutton(
                tab_frame, text=label, variable=self._tab, value=val,
                font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text_muted"],
                selectcolor=COLORS["surface2"], activebackground=COLORS["bg"],
                indicatoron=False, relief="flat", cursor="hand2",
                command=self._cambiar_tab, padx=14, pady=6,
            ).pack(side="left", padx=(0, 4))

        self._main = tk.Frame(self, bg=COLORS["bg"])
        self._main.pack(fill="both", expand=True, padx=32, pady=(0, 24))
        self._cambiar_tab()

    def _cambiar_tab(self):
        for w in self._main.winfo_children():
            w.destroy()
        if self._tab.get() == "turno":
            self._panel_turno()
        else:
            self._panel_historial()

    def _panel_turno(self):
        from modules.caja import get_sesion_activa
        sesion = get_sesion_activa()
        if not sesion:
            self._panel_apertura(self._main)
        else:
            self._panel_cierre(self._main, sesion)

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
            self._refrescar()
        except Exception as e:
            messagebox.showerror("Error al abrir caja", str(e))

    def _panel_cierre(self, parent, sesion):
        from modules.caja import DENOMINACIONES_COP, formatear_pesos, calcular_desde_denominaciones

        encabezado = tk.Frame(parent, bg=COLORS["bg"])
        encabezado.pack(fill="x", pady=(0, 16))
        tk.Label(encabezado,
                 text=f"Caja abierta por: {sesion['cajero']}  ·  Desde: {sesion['apertura'][:16]}",
                 font=FONT_SMALL, bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side="left")
        self._btn_secondary(encabezado, "Refrescar",
                            self._refrescar).pack(
                                side="right", ipady=2, ipadx=6
                            )

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
        from modules.caja import formatear_pesos, calcular_desde_denominaciones
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

        dif = total - self._esperado_ef
        color = COLORS["success"] if dif >= 0 else COLORS["danger"]
        signo = "+" if dif >= 0 else ""
        self.lbl_diferencia.config(
            text=f"Diferencia efectivo: {signo}{formatear_pesos(dif)}",
            fg=color,
        )

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
                f"  Esperado:   {formatear_pesos(resumen['esperado_efectivo'])}\n"
                f"  Contado:    {formatear_pesos(resumen['monto_contado'])}\n"
                f"  Diferencia: {fmt_dif(dif_ef)}\n\n"
                f"DIGITAL\n"
                f"  Esperado:   {formatear_pesos(resumen['esperado_digital'])}\n"
                f"  Contado:    {formatear_pesos(resumen['monto_contado_digital'])}\n"
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

            # ── Generar PDF de cierre ────────────────────────────────────
            from modules.reporte_caja import generar_pdf_cierre
            pdf_msg = ""
            pdf_ruta = None
            try:
                pdf_ruta = generar_pdf_cierre(resumen)
                pdf_msg  = f"\n\nReporte PDF guardado en:\n{pdf_ruta}"
            except Exception as pdf_err:
                pdf_msg = f"\n\n⚠ No se pudo generar el PDF: {pdf_err}"

            messagebox.showinfo("Cierre de caja", msg + dian_msg + pdf_msg)

            if pdf_ruta:
                import subprocess, platform
                try:
                    if platform.system() == "Windows":
                        os.startfile(pdf_ruta)
                    elif platform.system() == "Darwin":
                        subprocess.Popen(["open", pdf_ruta])
                    else:
                        subprocess.Popen(["xdg-open", pdf_ruta])
                except Exception:
                    pass

            self._refrescar()
        except Exception as e:
            messagebox.showerror("Error al cerrar caja", str(e))
            from modules.caja import get_sesion_activa
            if not get_sesion_activa():
                self._refrescar()

    # ── Utilidades ────────────────────────────────────────────────────────────

    def _refrescar(self):
        """Recarga el tab activo."""
        self._tab.set("turno")
        self._cambiar_tab()

    # ── Historial de cajas ────────────────────────────────────────────────────

    def _panel_historial(self):
        from modules.caja import formatear_pesos

        # Barra de filtros
        filtros = self._card(self._main)
        filtros.pack(fill="x", pady=(0, 12), ipadx=10, ipady=6)

        fila_f = tk.Frame(filtros, bg=COLORS["surface"])
        fila_f.pack(fill="x", padx=16, pady=8)

        tk.Label(fila_f, text="Desde:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self._h_desde = self._input(fila_f, width=12)
        self._h_desde.pack(side="left", padx=(4, 16), ipady=3)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self._h_desde, "fecha")

        tk.Label(fila_f, text="Hasta:", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self._h_hasta = self._input(fila_f, width=12)
        self._h_hasta.pack(side="left", padx=(4, 16), ipady=3)
        aplicar_validacion(self._h_hasta, "fecha")

        self._btn_primary(fila_f, "Buscar", self._cargar_historial).pack(
            side="left", padx=(0, 8), ipady=3)
        self._btn_secondary(fila_f, "Limpiar", self._limpiar_hist).pack(
            side="left", ipady=3)

        # KPIs
        self._hist_kpis = tk.Frame(self._main, bg=COLORS["bg"])
        self._hist_kpis.pack(fill="x", pady=(0, 12))

        # Layout: tabla izquierda + detalle derecha
        layout = tk.Frame(self._main, bg=COLORS["bg"])
        layout.pack(fill="both", expand=True)

        # Tabla
        cols = ("#", "Cajero", "Apertura", "Cierre", "Ventas", "Ef. Dif.", "Dig. Dif.")
        self._hist_tree = self._tabla(layout, cols, alto=14)
        self._hist_tree.pack(side="left", fill="both", expand=True)

        self._hist_tree.column("#",        width=40,  anchor="center")
        self._hist_tree.column("Cajero",   width=90,  anchor="w")
        self._hist_tree.column("Apertura", width=130, anchor="w")
        self._hist_tree.column("Cierre",   width=130, anchor="w")
        self._hist_tree.column("Ventas",   width=100, anchor="e")
        self._hist_tree.column("Ef. Dif.", width=90,  anchor="e")
        self._hist_tree.column("Dig. Dif.",width=90,  anchor="e")

        self._hist_tree.bind("<<TreeviewSelect>>", self._on_sesion_sel)

        # Panel de detalle
        det_outer = tk.Frame(layout, bg=COLORS["border"],
                             highlightbackground=COLORS["border"],
                             highlightthickness=1, width=290)
        det_outer.pack(side="right", fill="y", padx=(12, 0))
        det_outer.pack_propagate(False)

        det_canvas = tk.Canvas(det_outer, bg=COLORS["surface"],
                               highlightthickness=0, bd=0, width=288)
        det_scroll = tk.Scrollbar(det_outer, orient="vertical",
                                  command=det_canvas.yview)
        det_canvas.configure(yscrollcommand=det_scroll.set)
        det_scroll.pack(side="right", fill="y")
        det_canvas.pack(side="left", fill="both", expand=True)

        self._det_panel = tk.Frame(det_canvas, bg=COLORS["surface"])
        self._det_win   = det_canvas.create_window(
            (0, 0), window=self._det_panel, anchor="nw")
        det_canvas.bind("<Configure>",
            lambda e: det_canvas.itemconfig(self._det_win, width=e.width))
        self._det_panel.bind("<Configure>",
            lambda e: det_canvas.configure(
                scrollregion=det_canvas.bbox("all")))

        self._det_canvas = det_canvas

        tk.Label(self._det_panel, text="Selecciona una sesión",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(padx=16, pady=24)

        self._cargar_historial()

    def _cargar_historial(self):
        from modules.caja import listar_sesiones, formatear_pesos

        desde = self._h_desde.get().strip() or None
        hasta = self._h_hasta.get().strip() or None

        try:
            sesiones = listar_sesiones(fecha_inicio=desde, fecha_fin=hasta)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        # KPIs
        for w in self._hist_kpis.winfo_children():
            w.destroy()
        total_v   = sum(s.get("total_ventas", 0) or 0 for s in sesiones)
        total_dif = sum(s.get("diferencia", 0) or 0 for s in sesiones)
        self._kpi_hist(self._hist_kpis, "Sesiones",     str(len(sesiones)))
        self._kpi_hist(self._hist_kpis, "Total ventas", formatear_pesos(total_v))
        self._kpi_hist(self._hist_kpis, "Dif. neta ef.",formatear_pesos(total_dif))

        # Tabla
        for row in self._hist_tree.get_children():
            self._hist_tree.delete(row)

        for s in sesiones:
            dif_ef  = s.get("diferencia", 0) or 0
            dif_dig = s.get("diferencia_digital", 0) or 0

            def fmt_dif(d):
                if d is None: return "—"
                return ("+" if d >= 0 else "") + formatear_pesos(d)

            tag = "sobrante" if dif_ef >= 0 else "faltante"
            self._hist_tree.insert("", "end", iid=str(s["id"]), tags=(tag,),
                                   values=(
                                       s["id"],
                                       s["cajero"],
                                       s["apertura"][:16],
                                       s["cierre"][:16] if s["cierre"] else "—",
                                       formatear_pesos(s.get("total_ventas", 0) or 0),
                                       fmt_dif(dif_ef),
                                       fmt_dif(dif_dig),
                                   ))

        self._hist_tree.tag_configure("sobrante", foreground=COLORS["success"])
        self._hist_tree.tag_configure("faltante", foreground=COLORS["danger"])

    def _limpiar_hist(self):
        self._h_desde.delete(0, "end")
        self._h_hasta.delete(0, "end")
        self._cargar_historial()

    def _on_sesion_sel(self, event):
        sel = self._hist_tree.selection()
        if not sel:
            return
        sesion_id = int(sel[0])
        self._mostrar_detalle(sesion_id)

    def _mostrar_detalle(self, sesion_id: int):
        from modules.caja import obtener_sesion, formatear_pesos, egresos_sesion
        from modules.gastos import resumen_gastos_sesion

        for w in self._det_panel.winfo_children():
            w.destroy()

        sesion = obtener_sesion(sesion_id)
        if not sesion:
            return

        eg_ef, eg_dig = egresos_sesion(sesion_id)

        def sep():
            tk.Frame(self._det_panel, bg=COLORS["border"], height=1).pack(
                fill="x", padx=12, pady=6)

        def fila(label, valor, color=None):
            f = tk.Frame(self._det_panel, bg=COLORS["surface"])
            f.pack(fill="x", padx=12, pady=2)
            tk.Label(f, text=label, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
            tk.Label(f, text=valor, font=FONT_BOLD,
                     bg=COLORS["surface"],
                     fg=color or COLORS["text"]).pack(side="right")

        def titulo(txt, color=None):
            tk.Label(self._det_panel, text=txt, font=FONT_BOLD,
                     bg=COLORS["surface"],
                     fg=color or COLORS["accent"]).pack(
                         anchor="w", padx=12, pady=(8, 2))

        # Encabezado
        tk.Label(self._det_panel,
                 text=f"Sesión #{sesion_id}",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(anchor="w", padx=12, pady=(14, 0))
        tk.Label(self._det_panel,
                 text=sesion["cajero"],
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w", padx=12)

        sep()
        fila("Apertura:", sesion["apertura"][:16])
        cierre_txt = sesion["cierre"][:16] if sesion["cierre"] else "Abierta"
        fila("Cierre:", cierre_txt)

        # ── Efectivo ──────────────────────────────────────────────────
        sep()
        titulo("EFECTIVO", COLORS["accent"])
        base_ef   = sesion.get("monto_base", 0) or 0
        total_ef  = sesion.get("total_efectivo", 0) or 0
        esp_ef    = base_ef + total_ef - eg_ef
        contado_ef = sesion.get("monto_cierre", 0) or 0
        dif_ef    = sesion.get("diferencia", 0)

        fila("Base inicial:", formatear_pesos(base_ef))
        fila("Ventas:", formatear_pesos(total_ef), COLORS["success"])
        if eg_ef:
            fila("Gastos/egresos:", f"- {formatear_pesos(eg_ef)}", COLORS["danger"])
        fila("Esperado:", formatear_pesos(esp_ef))
        fila("Contado:", formatear_pesos(contado_ef))
        if dif_ef is not None:
            signo = "+" if dif_ef >= 0 else ""
            color = COLORS["success"] if dif_ef >= 0 else COLORS["danger"]
            fila("Diferencia:", f"{signo}{formatear_pesos(dif_ef)}", color)

        # Denominaciones
        denoms = [d for d in sesion.get("denominaciones", []) if d["cantidad"] > 0]
        if denoms:
            tk.Label(self._det_panel, text="Denominaciones:",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(anchor="w", padx=12, pady=(6, 2))
            for d in denoms:
                f2 = tk.Frame(self._det_panel, bg=COLORS["surface"])
                f2.pack(fill="x", padx=20, pady=1)
                tk.Label(f2, text=formatear_pesos(d["denominacion"]),
                         font=FONT_SMALL, bg=COLORS["surface"],
                         fg=COLORS["text_muted"]).pack(side="left")
                tk.Label(f2, text=f"×{d['cantidad']}  {formatear_pesos(d['subtotal'])}",
                         font=FONT_SMALL, bg=COLORS["surface"],
                         fg=COLORS["text"]).pack(side="right")

        # ── Digital ───────────────────────────────────────────────────
        sep()
        titulo("DIGITAL", COLORS["success"])
        base_dig   = sesion.get("monto_base_digital", 0) or 0
        total_dig  = sesion.get("total_digital", 0) or 0
        esp_dig    = base_dig + total_dig - eg_dig
        dif_dig    = sesion.get("diferencia_digital", 0)

        fila("Base inicial:", formatear_pesos(base_dig))
        fila("Ventas:", formatear_pesos(total_dig), COLORS["success"])
        if eg_dig:
            fila("Gastos/egresos:", f"- {formatear_pesos(eg_dig)}", COLORS["danger"])
        fila("Esperado:", formatear_pesos(esp_dig))
        if dif_dig is not None:
            signo = "+" if dif_dig >= 0 else ""
            color = COLORS["success"] if dif_dig >= 0 else COLORS["danger"]
            fila("Diferencia:", f"{signo}{formatear_pesos(dif_dig)}", color)

        # ── Gastos generales del turno ─────────────────────────────────
        gastos = resumen_gastos_sesion(sesion_id)
        if gastos:
            sep()
            titulo("GASTOS GENERALES", COLORS["warning"])
            total_g = 0
            for g in gastos:
                f3 = tk.Frame(self._det_panel, bg=COLORS["surface"])
                f3.pack(fill="x", padx=12, pady=1)
                tk.Label(f3, text=g["concepto"],
                         font=FONT_SMALL, bg=COLORS["surface"],
                         fg=COLORS["text_muted"]).pack(side="left")
                tk.Label(f3, text=formatear_pesos(g["total"]),
                         font=FONT_SMALL, bg=COLORS["surface"],
                         fg=COLORS["text"]).pack(side="right")
                total_g += g["total"]
            sep()
            fila("Total gastos:", formatear_pesos(total_g), COLORS["warning"])

        # ── Notas ─────────────────────────────────────────────────────
        if sesion.get("notas"):
            sep()
            tk.Label(self._det_panel, text="Notas:",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(anchor="w", padx=12)
            tk.Label(self._det_panel, text=sesion["notas"],
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text"], wraplength=240,
                     justify="left").pack(anchor="w", padx=12, pady=(2, 0))

        # ── Botón PDF ──────────────────────────────────────────────────
        sep()
        self._btn_secondary(
            self._det_panel, "Generar PDF",
            lambda sid=sesion_id: self._generar_pdf_sesion(sid)
        ).pack(fill="x", padx=12, pady=(0, 16), ipady=6)

        self._det_canvas.yview_moveto(0)

    def _generar_pdf_sesion(self, sesion_id: int):
        from modules.caja import obtener_sesion, formatear_pesos, egresos_sesion
        from modules.gastos import resumen_gastos_sesion
        from modules.reporte_caja import generar_pdf_cierre

        sesion = obtener_sesion(sesion_id)
        if not sesion:
            messagebox.showerror("Error", "Sesión no encontrada.")
            return

        eg_ef, eg_dig = egresos_sesion(sesion_id)
        base_ef  = sesion.get("monto_base", 0) or 0
        base_dig = sesion.get("monto_base_digital", 0) or 0
        total_ef = sesion.get("total_efectivo", 0) or 0
        total_dig = sesion.get("total_digital", 0) or 0

        resumen = {
            "sesion_id":             sesion["id"],
            "cajero":                sesion["cajero"],
            "apertura":              sesion["apertura"],
            "monto_base":            base_ef,
            "monto_base_digital":    base_dig,
            "total_ventas":          sesion.get("total_ventas", 0) or 0,
            "total_efectivo":        total_ef,
            "total_digital":         total_dig,
            "egresos_efectivo":      eg_ef,
            "egresos_digital":       eg_dig,
            "esperado_efectivo":     base_ef + total_ef - eg_ef,
            "esperado_digital":      base_dig + total_dig - eg_dig,
            "monto_contado":         sesion.get("monto_cierre", 0) or 0,
            "monto_contado_digital": base_dig + total_dig - eg_dig,
            "diferencia":            sesion.get("diferencia", 0) or 0,
            "diferencia_digital":    sesion.get("diferencia_digital", 0) or 0,
            "denominaciones":        sesion.get("denominaciones", []),
            "notas":                 sesion.get("notas", ""),
        }

        try:
            pdf_ruta = generar_pdf_cierre(resumen)
            messagebox.showinfo("PDF generado",
                                f"Reporte guardado en:\n{pdf_ruta}")
            import subprocess, platform
            try:
                if platform.system() == "Windows":
                    os.startfile(pdf_ruta)
                elif platform.system() == "Darwin":
                    subprocess.Popen(["open", pdf_ruta])
                else:
                    subprocess.Popen(["xdg-open", pdf_ruta])
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _kpi_hist(self, parent, label, valor):
        card = self._card(parent)
        card.pack(side="left", ipadx=14, ipady=6, padx=(0, 10))
        tk.Label(card, text=label, font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                     anchor="w", padx=10, pady=(8, 0))
        tk.Label(card, text=valor, font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=10, pady=(0, 8))