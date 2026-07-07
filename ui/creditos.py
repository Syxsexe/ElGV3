"""
ui/creditos.py — El G POS
Panel de créditos: saldos por cliente, historial y registro de abonos.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import (
    FrameBase, COLORS,
    FONT_BOLD, FONT_SMALL, FONT_LABEL, FONT_KPI, FONT_SUB,
)


class FrameCreditos(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Créditos", "Saldos, historial y abonos de clientes")
        from modules.creditos import migrar
        migrar()
        self._cliente_sel_id   = None
        self._tab              = tk.StringVar(value="saldos")
        self._build()

    # ── Estructura principal ──────────────────────────────────────────────────

    def _build(self):
        # Barra de tabs
        tab_bar = tk.Frame(self, bg=COLORS["bg"])
        tab_bar.pack(fill="x", padx=32, pady=(0, 0))

        self._tab_btns = {}
        for key, lbl in [("saldos", "Saldos"), ("pendientes", "Pendientes"), ("historial", "Historial")]:
            b = tk.Button(
                tab_bar, text=lbl, font=FONT_BOLD,
                bg=COLORS["surface"], fg=COLORS["text_muted"],
                activebackground=COLORS["surface2"], relief="flat", cursor="hand2",
                padx=18, pady=8,
                command=lambda k=key: self._cambiar_tab(k),
            )
            b.pack(side="left", padx=(0, 4))
            self._tab_btns[key] = b

        self._area = tk.Frame(self, bg=COLORS["bg"])
        self._area.pack(fill="both", expand=True, padx=32, pady=(8, 24))

        self._cambiar_tab("saldos")

    def _cambiar_tab(self, key: str):
        self._tab.set(key)
        for k, b in self._tab_btns.items():
            b.config(
                bg=COLORS["accent"] if k == key else COLORS["surface"],
                fg=COLORS["text"]   if k == key else COLORS["text_muted"],
            )
        for w in self._area.winfo_children():
            w.destroy()
        if key == "saldos":
            self._panel_saldos()
        elif key == "pendientes":
            self._panel_pendientes()
        else:
            self._panel_historial()

    # ════════════════════════════════════════════════════════════
    # TAB SALDOS
    # ════════════════════════════════════════════════════════════

    def _panel_saldos(self):
        main = tk.Frame(self._area, bg=COLORS["bg"])
        main.pack(fill="both", expand=True)

        # ── Panel izquierdo: tabla de saldos ─────────────────────────────────
        left = tk.Frame(main, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 16))

        hdr = tk.Frame(left, bg=COLORS["bg"])
        hdr.pack(fill="x", pady=(0, 8))
        tk.Label(hdr, text="Clientes con crédito", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(side="left")
        tk.Button(hdr, text="↻ Refrescar", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=self._cargar_saldos).pack(side="right")

        wrap = tk.Frame(left, bg=COLORS["bg"])
        wrap.pack(fill="both", expand=True)

        self.tree_saldos = self._tabla(
            wrap,
            ("nombre", "limite", "saldo", "disponible", "vencidas", "vence"),
            alto=18,
        )
        self.tree_saldos.heading("nombre",    text="Cliente")
        self.tree_saldos.heading("limite",    text="Límite")
        self.tree_saldos.heading("saldo",     text="Deuda")
        self.tree_saldos.heading("disponible",text="Disponible")
        self.tree_saldos.heading("vencidas",  text="Vencidas")
        self.tree_saldos.heading("vence",     text="Próx. venc.")
        self.tree_saldos.column("nombre",    width=190, anchor="w")
        self.tree_saldos.column("limite",    width=100, anchor="e")
        self.tree_saldos.column("saldo",     width=100, anchor="e")
        self.tree_saldos.column("disponible",width=100, anchor="e")
        self.tree_saldos.column("vencidas",  width=68,  anchor="center")
        self.tree_saldos.column("vence",     width=100, anchor="center")

        self.tree_saldos.tag_configure("deuda",   foreground=COLORS["danger"])
        self.tree_saldos.tag_configure("vencido",  foreground=COLORS["danger"])
        self.tree_saldos.tag_configure("ok",      foreground=COLORS["success"])
        self.tree_saldos.tag_configure("sin",     foreground=COLORS["text_muted"])
        self.tree_saldos.bind("<<TreeviewSelect>>", self._al_sel_saldo)

        # ── Panel derecho: configurar crédito + registrar abono ───────────────
        right = self._card(main, width=300)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        canvas = tk.Canvas(right, bg=COLORS["surface"], highlightthickness=0)
        sb = ttk.Scrollbar(right, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=COLORS["surface"])
        win = canvas.create_window((0, 0), window=sf, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        sf.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        def _lbl(texto):
            tk.Label(sf, text=texto, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)

        # — Configurar crédito —
        tk.Label(sf, text="Configurar crédito", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 4))

        self.lbl_cliente_conf = tk.Label(
            sf, text="Selecciona un cliente", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text_muted"], wraplength=240, justify="left"
        )
        self.lbl_cliente_conf.pack(anchor="w", padx=16, pady=(0, 8))

        # Búsqueda de cliente
        _lbl("Buscar cliente")
        self.entry_buscar_cli = self._input(sf)
        self.entry_buscar_cli.pack(fill="x", padx=16, pady=(2, 0), ipady=5)
        self.entry_buscar_cli.bind("<KeyRelease>", self._buscar_cli)

        self._lst_cli_res = tk.Listbox(
            sf, font=FONT_SMALL, height=4,
            bg=COLORS["surface2"], fg=COLORS["text"],
            selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1, highlightbackground=COLORS["border"],
        )
        self._lst_cli_res.bind("<<ListboxSelect>>", self._sel_cli_conf)
        self._cli_conf_resultados = []
        # No empaquetado todavía

        _lbl("Límite de crédito ($)")
        self.entry_limite = self._input(sf)
        self.entry_limite.pack(fill="x", padx=16, pady=(2, 8), ipady=5)
        from modules.validaciones import aplicar_validacion
        aplicar_validacion(self.entry_limite, "monto")

        _lbl("Días para pagar")
        self.entry_dias = self._input(sf, width=8)
        self.entry_dias.insert(0, "30")
        self.entry_dias.pack(anchor="w", padx=16, pady=(2, 8), ipady=5)
        aplicar_validacion(self.entry_dias, "entero")

        self._btn_primary(sf, "Guardar configuración",
                          self._guardar_limite).pack(fill="x", padx=16, ipady=8)

        tk.Frame(sf, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=14)

        # — Registrar abono —
        tk.Label(sf, text="Registrar abono", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 4))

        self.lbl_saldo_abono = tk.Label(
            sf, text="Saldo: $0", font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["danger"]
        )
        self.lbl_saldo_abono.pack(anchor="w", padx=16, pady=(0, 6))

        _lbl("Monto del abono ($)")
        self.entry_abono = self._input(sf)
        self.entry_abono.pack(fill="x", padx=16, pady=(2, 8), ipady=5)
        aplicar_validacion(self.entry_abono, "monto")

        _lbl("Método de pago")
        self._var_metodo_abono = tk.StringVar(value="efectivo")
        metodos = ["efectivo", "transferencia", "nequi", "daviplata", "tarjeta"]
        combo_m = ttk.Combobox(sf, values=metodos, textvariable=self._var_metodo_abono,
                               state="readonly", font=FONT_SMALL)
        combo_m.pack(fill="x", padx=16, pady=(2, 8), ipady=3)

        _lbl("Notas")
        self.entry_notas_abono = self._input(sf)
        self.entry_notas_abono.pack(fill="x", padx=16, pady=(2, 8), ipady=5)

        self._btn_primary(sf, "Registrar abono",
                          self._registrar_abono).pack(fill="x", padx=16, ipady=8)

        tk.Frame(sf, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=(10, 6))

        tk.Button(
            sf, text="Pagar toda la deuda", font=FONT_SMALL,
            bg=COLORS["surface2"], fg=COLORS["warning"],
            activebackground=COLORS["border"], relief="flat", cursor="hand2",
            command=self._pagar_todo_cliente, pady=8,
        ).pack(fill="x", padx=16, pady=(0, 16))

        # Carga inicial
        self._cargar_saldos()
        self._id_cliente_conf = None

    def _cargar_saldos(self):
        from modules.creditos import listar_saldos
        from modules.caja import formatear_pesos

        self.tree_saldos.delete(*self.tree_saldos.get_children())
        for s in listar_saldos():
            vencidos = s.get("vencidos", 0)
            if vencidos > 0:
                tag = "vencido"
            elif s["saldo"] > 0:
                tag = "deuda"
            elif s["limite"] > 0:
                tag = "ok"
            else:
                tag = "sin"
            venc = s["prox_venc"][:10] if s.get("prox_venc") else "—"
            self.tree_saldos.insert("", "end", iid=str(s["id"]), values=(
                s["nombre"],
                formatear_pesos(s["limite"]),
                formatear_pesos(s["saldo"]),
                formatear_pesos(s["disponible"]),
                str(vencidos) if vencidos > 0 else "—",
                venc,
            ), tags=(tag,))

    def _al_sel_saldo(self, event=None):
        from modules.creditos import get_info_credito
        from modules.caja import formatear_pesos
        sel = self.tree_saldos.focus()
        if not sel:
            return
        self._cliente_sel_id = int(sel)
        self._id_cliente_conf = self._cliente_sel_id
        info = get_info_credito(self._cliente_sel_id)
        nombre = self.tree_saldos.item(sel, "values")[0]
        self.lbl_cliente_conf.config(text=f"Cliente: {nombre}", fg=COLORS["accent"])
        self.entry_limite.delete(0, "end")
        self.entry_limite.insert(0, str(int(info["limite"])))
        self.entry_dias.delete(0, "end")
        self.entry_dias.insert(0, str(info["dias_credito"]))
        saldo = info["saldo"]
        self.lbl_saldo_abono.config(
            text=f"Saldo: {formatear_pesos(saldo)}",
            fg=COLORS["danger"] if saldo > 0 else COLORS["text_muted"]
        )

    def _buscar_cli(self, event=None):
        from modules.clientes import buscar_clientes
        texto = self.entry_buscar_cli.get().strip()
        self._lst_cli_res.delete(0, "end")
        self._cli_conf_resultados = []
        if not texto:
            self._lst_cli_res.pack_forget()
            return
        res = buscar_clientes(texto)[:8]
        if not res:
            self._lst_cli_res.pack_forget()
            return
        self._cli_conf_resultados = res
        for c in res:
            self._lst_cli_res.insert("end", f"  {c['nombre']}")
        self._lst_cli_res.pack(fill="x", padx=16)

    def _sel_cli_conf(self, event=None):
        from modules.creditos import get_info_credito
        from modules.caja import formatear_pesos
        idx = self._lst_cli_res.curselection()
        if not idx or idx[0] >= len(self._cli_conf_resultados):
            return
        c = self._cli_conf_resultados[idx[0]]
        self._id_cliente_conf  = c["id"]
        self._cliente_sel_id   = c["id"]
        self.lbl_cliente_conf.config(text=f"Cliente: {c['nombre']}", fg=COLORS["accent"])
        info = get_info_credito(c["id"])
        self.entry_limite.delete(0, "end")
        self.entry_limite.insert(0, str(int(info["limite"])))
        self.entry_dias.delete(0, "end")
        self.entry_dias.insert(0, str(info["dias_credito"]))
        saldo = info["saldo"]
        self.lbl_saldo_abono.config(
            text=f"Saldo: {formatear_pesos(saldo)}",
            fg=COLORS["danger"] if saldo > 0 else COLORS["text_muted"]
        )
        self._lst_cli_res.pack_forget()
        self.entry_buscar_cli.delete(0, "end")

    def _guardar_limite(self):
        from modules.creditos import set_limite_credito
        from modules.validaciones import leer_entero
        if not getattr(self, "_id_cliente_conf", None):
            messagebox.showwarning("Sin cliente", "Selecciona un cliente primero.")
            return
        try:
            limite = leer_entero(self.entry_limite)
            dias   = leer_entero(self.entry_dias, default=30)
            set_limite_credito(self._id_cliente_conf, limite, dias)
            messagebox.showinfo("Guardado", "Configuración de crédito actualizada.")
            self._cargar_saldos()
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _registrar_abono(self):
        from modules.creditos import registrar_abono
        from modules.caja import get_sesion_activa
        from modules.validaciones import leer_entero
        if not self._cliente_sel_id:
            messagebox.showwarning("Sin cliente", "Selecciona un cliente de la tabla.")
            return
        monto = leer_entero(self.entry_abono)
        if monto <= 0:
            messagebox.showwarning("Monto inválido", "Ingresa un monto mayor a cero.")
            return
        metodo  = self._var_metodo_abono.get()
        notas   = self.entry_notas_abono.get().strip() or None
        sesion  = get_sesion_activa()
        try:
            abono_id = registrar_abono(
                self._cliente_sel_id, monto,
                metodo_pago=metodo,
                sesion_id=sesion["id"] if sesion else None,
                notas=notas,
            )
            self.entry_abono.delete(0, "end")
            self.entry_notas_abono.delete(0, "end")
            self._cargar_saldos()
            self._al_sel_saldo()
            if messagebox.askyesno(
                    "Abono registrado",
                    f"Abono de ${monto:,.0f} registrado.\n¿Imprimir recibo de caja?"):
                from ui.ticket_dialog import mostrar_recibo_caja
                mostrar_recibo_caja(self, abono_id)
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    # ════════════════════════════════════════════════════════════
    # TAB HISTORIAL
    # ════════════════════════════════════════════════════════════

    def _panel_historial(self):
        main = tk.Frame(self._area, bg=COLORS["bg"])
        main.pack(fill="both", expand=True)

        # Selector de cliente
        top = tk.Frame(main, bg=COLORS["bg"])
        top.pack(fill="x", pady=(0, 10))

        tk.Label(top, text="Cliente:", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(side="left")

        self.combo_hist_cli = ttk.Combobox(top, state="readonly", font=FONT_SMALL, width=28)
        self.combo_hist_cli.pack(side="left", padx=(8, 16))
        self.combo_hist_cli.bind("<<ComboboxSelected>>", lambda e: self._cargar_historial())
        self._btn_primary(top, "Ver historial", self._cargar_historial).pack(side="left", ipady=4)

        self._cargar_combo_hist()

        # KPIs
        self._kpi_hist = tk.Frame(main, bg=COLORS["bg"])
        self._kpi_hist.pack(fill="x", pady=(0, 10))

        # Tabla
        cols = ("fecha", "tipo", "monto", "metodo", "vence", "notas")
        self.tree_hist = self._tabla(main, cols, alto=20)
        self.tree_hist.heading("fecha",  text="Fecha")
        self.tree_hist.heading("tipo",   text="Tipo")
        self.tree_hist.heading("monto",  text="Monto")
        self.tree_hist.heading("metodo", text="Método")
        self.tree_hist.heading("vence",  text="Vencimiento")
        self.tree_hist.heading("notas",  text="Notas")
        self.tree_hist.column("fecha",  width=145, anchor="w")
        self.tree_hist.column("tipo",   width=80,  anchor="center")
        self.tree_hist.column("monto",  width=110, anchor="e")
        self.tree_hist.column("metodo", width=100, anchor="center")
        self.tree_hist.column("vence",  width=100, anchor="center")
        self.tree_hist.column("notas",  width=280, anchor="w")

        self.tree_hist.tag_configure("cargo", foreground=COLORS["danger"])
        self.tree_hist.tag_configure("abono", foreground=COLORS["success"])

    def _cargar_combo_hist(self):
        from modules.clientes import listar_clientes
        clientes = listar_clientes()
        self._hist_clientes = clientes
        self.combo_hist_cli["values"] = [c["nombre"] for c in clientes]
        if clientes:
            self.combo_hist_cli.current(0)

    def _cargar_historial(self):
        from modules.creditos import historial_cliente, get_info_credito
        from modules.caja import formatear_pesos

        idx = self.combo_hist_cli.current()
        if idx < 0 or not self._hist_clientes:
            return
        cli = self._hist_clientes[idx]
        cli_id = cli["id"]

        movs = historial_cliente(cli_id)
        self.tree_hist.delete(*self.tree_hist.get_children())
        for m in movs:
            tipo  = m["tipo"]
            venc  = m["fecha_vencimiento"][:10] if m.get("fecha_vencimiento") else "—"
            monto = formatear_pesos(m["monto"])
            if tipo == "cargo":
                monto = f"−{monto}"
            self.tree_hist.insert("", "end", values=(
                m["fecha"],
                "Cargo" if tipo == "cargo" else "Abono",
                monto,
                m.get("metodo_pago") or "—",
                venc,
                m.get("notas") or "",
            ), tags=(tipo,))

        # KPIs
        for w in self._kpi_hist.winfo_children():
            w.destroy()
        info = get_info_credito(cli_id)
        for etiqueta, valor, color in [
            ("Límite",      formatear_pesos(info["limite"]),     COLORS["text"]),
            ("Deuda actual", formatear_pesos(info["saldo"]),     COLORS["danger"]),
            ("Disponible",  formatear_pesos(info["disponible"]), COLORS["success"]),
            ("Plazo",       f"{info['dias_credito']} días",      COLORS["text_muted"]),
        ]:
            card = tk.Frame(self._kpi_hist, bg=COLORS["surface"],
                            highlightbackground=COLORS["border"], highlightthickness=1)
            card.pack(side="left", padx=(0, 12), ipadx=14, ipady=8)
            tk.Label(card, text=valor, font=FONT_KPI,
                     bg=COLORS["surface"], fg=color).pack()
            tk.Label(card, text=etiqueta, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack()

    # ════════════════════════════════════════════════════════════
    # TAB PENDIENTES
    # ════════════════════════════════════════════════════════════

    def _panel_pendientes(self):
        main = tk.Frame(self._area, bg=COLORS["bg"])
        main.pack(fill="both", expand=True)

        hdr = tk.Frame(main, bg=COLORS["bg"])
        hdr.pack(fill="x", pady=(0, 8))
        tk.Label(hdr, text="Compras a crédito pendientes (todos los clientes)",
                 font=FONT_BOLD, bg=COLORS["bg"], fg=COLORS["text"]).pack(side="left")
        self._var_solo_vencidos = tk.BooleanVar(value=False)
        tk.Checkbutton(
            hdr, text="Solo vencidas", variable=self._var_solo_vencidos,
            bg=COLORS["bg"], fg=COLORS["text_muted"],
            selectcolor=COLORS["surface"], activebackground=COLORS["bg"],
            command=self._cargar_pendientes,
        ).pack(side="left", padx=(16, 0))
        tk.Button(hdr, text="↻ Refrescar", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=self._cargar_pendientes).pack(side="right")

        cols = ("cliente", "venta", "total", "pagado", "pendiente", "vence", "estado")
        self.tree_pendientes = self._tabla(main, cols, alto=22)
        self.tree_pendientes.heading("cliente",  text="Cliente")
        self.tree_pendientes.heading("venta",    text="Venta #")
        self.tree_pendientes.heading("total",    text="Total")
        self.tree_pendientes.heading("pagado",   text="Pagado")
        self.tree_pendientes.heading("pendiente",text="Pendiente")
        self.tree_pendientes.heading("vence",    text="Vence")
        self.tree_pendientes.heading("estado",   text="Estado")
        self.tree_pendientes.column("cliente",   width=200, anchor="w")
        self.tree_pendientes.column("venta",     width=68,  anchor="center")
        self.tree_pendientes.column("total",     width=108, anchor="e")
        self.tree_pendientes.column("pagado",    width=100, anchor="e")
        self.tree_pendientes.column("pendiente", width=108, anchor="e")
        self.tree_pendientes.column("vence",     width=100, anchor="center")
        self.tree_pendientes.column("estado",    width=80,  anchor="center")
        self.tree_pendientes.tag_configure("vencido", foreground=COLORS["danger"])
        self.tree_pendientes.tag_configure("al_dia",  foreground=COLORS["text"])

        self._cargar_pendientes()

    def _cargar_pendientes(self):
        from modules.creditos import listar_cargos_pendientes_todos
        from modules.caja import formatear_pesos
        self.tree_pendientes.delete(*self.tree_pendientes.get_children())
        solo = getattr(self, "_var_solo_vencidos", None)
        for f in listar_cargos_pendientes_todos(solo_vencidos=solo.get() if solo else False):
            venc   = f["fecha_vencimiento"][:10] if f.get("fecha_vencimiento") else "—"
            estado = "VENCIDA" if f["vencido"] else "Al día"
            tag    = "vencido" if f["vencido"] else "al_dia"
            self.tree_pendientes.insert("", "end", iid=str(f["id"]), values=(
                f.get("cliente_nombre", "—"),
                f.get("venta_id") or "—",
                formatear_pesos(f["monto"]),
                formatear_pesos(f["pagado"]),
                formatear_pesos(f["pendiente"]),
                venc,
                estado,
            ), tags=(tag,))

    # ── Acciones extra ────────────────────────────────────────────────────────

    def _pagar_todo_cliente(self):
        from modules.creditos import get_saldo, registrar_abono_masivo
        from modules.caja import get_sesion_activa, formatear_pesos
        if not self._cliente_sel_id:
            messagebox.showwarning("Sin cliente", "Selecciona un cliente de la tabla.")
            return
        saldo = get_saldo(self._cliente_sel_id)
        if saldo <= 0:
            messagebox.showinfo("Sin deuda", "Este cliente no tiene saldo pendiente.")
            return
        metodo = self._var_metodo_abono.get()
        if not messagebox.askyesno(
            "Confirmar pago total",
            f"¿Registrar pago de {formatear_pesos(saldo)} para saldar toda la deuda?",
        ):
            return
        sesion = get_sesion_activa()
        try:
            registrar_abono_masivo(
                self._cliente_sel_id, saldo,
                metodo_pago=metodo,
                sesion_id=sesion["id"] if sesion else None,
            )
            messagebox.showinfo("Pagado", f"Deuda de {formatear_pesos(saldo)} saldada.")
            self._cargar_saldos()
            self._al_sel_saldo()
        except ValueError as e:
            messagebox.showerror("Error", str(e))
