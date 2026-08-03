"""
ui/torneos.py — El G POS
Torneos de TCG: cada jugador se inscribe con su método de pago (efectivo,
transferencia, … o CRÉDITO ligado a su cliente, con el mismo buscador de cliente
que la pantalla de Ventas) y los sobres entregados como premio salen del
inventario. La creación se hace en una ventana grande (mucha información).
"""
import tkinter as tk
from tkinter import ttk, messagebox

from ui.base import (
    FrameBase, COLORS, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_KPI,
)
from ui.modal import ModalForm

_JUEGOS = ["Yu-Gi-Oh!", "MTG", "Riftbound", "Torneo genérico"]
_METODOS = ["efectivo", "transferencia", "nequi", "daviplata", "tarjeta", "credito"]


class FrameTorneos(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Torneos", "Inscripciones, premios entregados y ganancia por torneo")
        self._modal        = None
        self._win          = None
        self._inscritos    = []   # participantes en construcción
        self._premios      = []   # premios en construcción
        self._prods_tienda = []
        self._insc_cli_id  = None  # cliente seleccionado para la inscripción actual
        self._build()

    # ── Layout principal ──────────────────────────────────────────────────────

    def _build(self):
        acciones = tk.Frame(self, bg=COLORS["bg"])
        acciones.pack(fill="x", padx=32, pady=(0, 8))
        self._btn_primary(acciones, "+ Nuevo torneo", self._ventana_torneo).pack(
            side="right", padx=(8, 0), ipady=4, ipadx=12)
        self._btn_secondary(acciones, "Ver detalle", self._ver_detalle).pack(
            side="right", ipady=4, ipadx=12)

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        tk.Label(main, text="Doble clic en un torneo para ver inscritos y premios.",
                 font=FONT_SMALL, bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(
                     anchor="w", pady=(0, 6))

        tabla_wrap = tk.Frame(main, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)
        cols = ("id", "fecha", "nombre", "juego", "jug", "recaudado", "costo", "ganancia")
        self.tree = self._tabla(tabla_wrap, cols, alto=12)
        textos = {"id": "#", "fecha": "Fecha", "nombre": "Torneo", "juego": "Juego",
                  "jug": "Inscr.", "recaudado": "Recaudado", "costo": "Costo premios",
                  "ganancia": "Ganancia"}
        anchos = {"id": 40, "fecha": 130, "nombre": 200, "juego": 120, "jug": 60,
                  "recaudado": 120, "costo": 120, "ganancia": 120}
        for c in cols:
            self.tree.heading(c, text=textos[c])
            anchor = "w" if c in ("nombre", "juego") else ("center" if c in ("id", "jug", "fecha") else "e")
            self.tree.column(c, width=anchos[c], anchor=anchor)
        self.tree.tag_configure("neg", foreground=COLORS["danger"])
        self.tree.tag_configure("pos", foreground=COLORS["success"])
        self.tree.bind("<Double-1>", lambda e: self._ver_detalle())

        self._cargar_torneos()

    def _cargar_torneos(self):
        from modules.torneos import listar_torneos
        from modules.caja import formatear_pesos
        self.tree.delete(*self.tree.get_children())
        for t in listar_torneos():
            tag = "pos" if (t["ganancia"] or 0) >= 0 else "neg"
            self.tree.insert("", "end", iid=str(t["id"]), values=(
                t["id"], (t["fecha"] or "")[:16], t["nombre"], t["juego"] or "—",
                t.get("num_inscritos") or 0,
                formatear_pesos(t["recaudado"] or 0),
                formatear_pesos(t["costo_premios"] or 0),
                formatear_pesos(t["ganancia"] or 0),
            ), tags=(tag,))

    def _cerrar_modal(self):
        if self._modal is not None:
            try:
                self._modal.cerrar()
            except tk.TclError:
                pass
            self._modal = None

    def _cerrar_ventana(self):
        if self._win is not None:
            try:
                self._win.grab_release()
            except tk.TclError:
                pass
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None

    # ══════════════════════════════════════════════════════════
    # VENTANA GRANDE — NUEVO TORNEO
    # ══════════════════════════════════════════════════════════

    def _ventana_torneo(self):
        from modules.validaciones import aplicar_validacion
        from modules.inventario import listar_productos
        from modules.caja import get_sesion_activa

        self._inscritos = []
        self._premios = []
        self._insc_cli_id = None

        top = self.winfo_toplevel()
        win = tk.Toplevel(top, bg=COLORS["bg"])
        win.withdraw()
        self._win = win
        win.title("Nuevo torneo")
        win.transient(top)
        win.protocol("WM_DELETE_WINDOW", self._cerrar_ventana)
        win.resizable(True, True)

        # ── Encabezado ─────────────────────────────────────────────────────
        head = tk.Frame(win, bg=COLORS["surface"])
        head.pack(fill="x")
        tk.Frame(head, bg=COLORS["accent"], height=3).pack(fill="x")
        hi = tk.Frame(head, bg=COLORS["surface"])
        hi.pack(fill="x", padx=20, pady=10)
        tk.Label(hi, text="Nuevo torneo", font=("Segoe UI", 15, "bold"),
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(side="left")
        ses = get_sesion_activa()
        tk.Label(hi, text=("Caja abierta" if ses else "⚠ Sin caja abierta"),
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["success"] if ses else COLORS["warning"]).pack(side="right")

        # ── Pie (botones) ──────────────────────────────────────────────────
        footer = tk.Frame(win, bg=COLORS["surface"])
        footer.pack(side="bottom", fill="x")
        tk.Frame(footer, bg=COLORS["border"], height=1).pack(fill="x")
        fb = tk.Frame(footer, bg=COLORS["surface"])
        fb.pack(fill="x", padx=20, pady=12)
        self._btn_primary(fb, "Guardar torneo", self._guardar_torneo).pack(
            side="right", ipady=6, ipadx=18)
        self._btn_secondary(fb, "Cancelar", self._cerrar_ventana).pack(
            side="left", ipady=6, ipadx=14)

        # ── Cuerpo: dos columnas ───────────────────────────────────────────
        body = tk.Frame(win, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=16, pady=16)

        left = tk.Frame(body, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        right = tk.Frame(body, bg=COLORS["bg"], width=440)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)

        self._construir_col_izquierda(left, aplicar_validacion)
        self._construir_col_derecha(right, aplicar_validacion, listar_productos)

        self._filtrar_prods()
        self._refrescar_inscritos()
        self._refrescar_premios()

        # Tamaño grande centrado, ajustado a la pantalla.
        win.update_idletasks()
        w = min(1200, win.winfo_screenwidth() - 40)
        h = min(760, win.winfo_screenheight() - 70)
        x = (win.winfo_screenwidth() - w) // 2
        y = max((win.winfo_screenheight() - h) // 2, 0)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.deiconify()
        win.grab_set()
        self._t_nombre.focus_set()

    def _construir_col_izquierda(self, left, aplicar_validacion):
        # ── Datos del torneo ────────────────────────────────────────────────
        card = self._card(left)
        card.pack(fill="x")
        tk.Label(card, text="Datos del torneo", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=14, pady=(12, 6))

        fila = tk.Frame(card, bg=COLORS["surface"])
        fila.pack(fill="x", padx=14, pady=(0, 12))
        tk.Label(fila, text="Nombre *", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).grid(row=0, column=0, sticky="w")
        tk.Label(fila, text="Juego / TCG", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).grid(row=0, column=1, sticky="w", padx=(10, 0))
        self._t_nombre = self._input(fila)
        self._t_nombre.grid(row=1, column=0, sticky="ew", ipady=5, pady=(2, 0))
        self._t_juego = ttk.Combobox(fila, values=_JUEGOS, state="readonly", font=FONT_LABEL)
        self._t_juego.set("Torneo genérico")
        self._t_juego.grid(row=1, column=1, sticky="ew", padx=(10, 0), pady=(2, 0))
        fila.columnconfigure(0, weight=2)
        fila.columnconfigure(1, weight=1)

        # ── Inscripciones ───────────────────────────────────────────────────
        tk.Label(left, text="Inscripciones por jugador", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(14, 4))

        add = self._card(left)
        add.pack(fill="x")
        inner = tk.Frame(add, bg=COLORS["surface"])
        inner.pack(fill="x", padx=14, pady=12)

        tk.Label(inner, text="Jugador — escribe un nombre libre, o busca un cliente registrado (obligatorio para crédito)",
                 font=("Segoe UI", 8), bg=COLORS["surface"], fg=COLORS["text_dim"],
                 justify="left").pack(anchor="w", pady=(0, 4))

        self._t_jugador = self._input(inner)
        self._t_jugador.pack(fill="x", ipady=5)
        self._t_jugador.bind("<KeyRelease>", self._buscar_jugador)

        self._lst_jug = tk.Listbox(
            inner, font=FONT_SMALL, height=4,
            bg=COLORS["surface2"], fg=COLORS["text"], selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1, highlightbackground=COLORS["border"])
        self._lst_jug.bind("<<ListboxSelect>>", self._sel_jugador)
        # oculto hasta escribir

        self._lbl_insc_cli = tk.Label(
            inner, text="Nombre libre (sin cliente)", font=("Segoe UI", 8),
            bg=COLORS["surface"], fg=COLORS["text_dim"], anchor="w")
        self._lbl_insc_cli.pack(fill="x", pady=(4, 6))

        rowm = tk.Frame(inner, bg=COLORS["surface"])
        rowm.pack(fill="x")
        tk.Label(rowm, text="Monto $", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self._t_monto = self._input(rowm, width=10)
        self._t_monto.pack(side="left", padx=(4, 12), ipady=4)
        aplicar_validacion(self._t_monto, "monto")
        tk.Label(rowm, text="Método", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self._t_metodo = ttk.Combobox(rowm, values=_METODOS, state="readonly",
                                      font=FONT_SMALL, width=13)
        self._t_metodo.set("efectivo")
        self._t_metodo.pack(side="left", padx=(4, 12))
        self._btn_primary(rowm, "+ Agregar", self._agregar_inscrito).pack(
            side="left", ipady=3, ipadx=6)

        # Tabla de inscritos
        insc_wrap = tk.Frame(left, bg=COLORS["bg"])
        insc_wrap.pack(fill="both", expand=True, pady=(8, 0))
        self._tree_insc = self._tabla(insc_wrap, ("jugador", "metodo", "monto"), alto=7)
        self._tree_insc.heading("jugador", text="Jugador")
        self._tree_insc.heading("metodo", text="Método")
        self._tree_insc.heading("monto", text="Monto")
        self._tree_insc.column("jugador", width=240, anchor="w")
        self._tree_insc.column("metodo", width=120, anchor="center")
        self._tree_insc.column("monto", width=110, anchor="e")
        self._tree_insc.tag_configure("cred", foreground=COLORS["warning"])
        self._tree_insc.bind("<Double-1>", lambda e: self._quitar_inscrito_sel())
        tk.Label(left, text="Doble clic en un jugador para quitarlo.",
                 font=("Segoe UI", 8), bg=COLORS["bg"], fg=COLORS["text_dim"]).pack(anchor="w", pady=(2, 0))

    def _construir_col_derecha(self, right, aplicar_validacion, listar_productos):
        tk.Label(right, text="Premios entregados (salen del inventario)", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 4))

        card = self._card(right)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=COLORS["surface"])
        inner.pack(fill="x", padx=14, pady=12)

        self._prods_tienda = listar_productos(tipo="tienda")
        self._prods_map = {p["nombre"]: p for p in self._prods_tienda}

        tk.Label(inner, text="Buscar producto (sobres, etc.)", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        self._t_buscar = self._input(inner)
        self._t_buscar.pack(fill="x", pady=(2, 4), ipady=5)
        self._t_buscar.bind("<KeyRelease>", self._filtrar_prods)

        self._lst_prods = tk.Listbox(
            inner, font=FONT_SMALL, height=5,
            bg=COLORS["surface2"], fg=COLORS["text"], selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1, highlightbackground=COLORS["border"])
        self._lst_prods.pack(fill="x", pady=(0, 6))

        rowp = tk.Frame(inner, bg=COLORS["surface"])
        rowp.pack(fill="x")
        tk.Label(rowp, text="Cantidad", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")
        self._t_cant = self._input(rowp, width=6)
        self._t_cant.insert(0, "1")
        self._t_cant.pack(side="left", padx=(6, 12), ipady=4)
        aplicar_validacion(self._t_cant, "entero")
        self._btn_primary(rowp, "+ Agregar premio", self._agregar_premio).pack(
            side="left", ipady=3, ipadx=6)

        prem_wrap = tk.Frame(right, bg=COLORS["bg"])
        prem_wrap.pack(fill="both", expand=True, pady=(8, 0))
        self._tree_prem = self._tabla(prem_wrap, ("producto", "cant", "costo"), alto=6)
        self._tree_prem.heading("producto", text="Producto")
        self._tree_prem.heading("cant", text="Cant")
        self._tree_prem.heading("costo", text="Costo")
        self._tree_prem.column("producto", width=210, anchor="w")
        self._tree_prem.column("cant", width=55, anchor="center")
        self._tree_prem.column("costo", width=100, anchor="e")
        self._tree_prem.tag_configure("exceso", foreground=COLORS["danger"])
        self._tree_prem.bind("<Double-1>", lambda e: self._quitar_premio_sel())
        tk.Label(right, text="Doble clic en un premio para quitarlo.",
                 font=("Segoe UI", 8), bg=COLORS["bg"], fg=COLORS["text_dim"]).pack(anchor="w", pady=(2, 0))

        # ── Resumen P&L ─────────────────────────────────────────────────────
        res = self._card(right)
        res.pack(fill="x", pady=(10, 0))
        ri = tk.Frame(res, bg=COLORS["surface"])
        ri.pack(fill="x", padx=14, pady=12)
        self._lbl_res_recaudado = self._fila_resumen(ri, "Recaudado")
        self._lbl_res_credito   = self._fila_resumen(ri, "  · a crédito")
        self._lbl_res_costo     = self._fila_resumen(ri, "Costo premios")
        self._lbl_res_ganancia  = self._fila_resumen(ri, "Ganancia", grande=True)

    def _fila_resumen(self, parent, label, grande=False):
        f = tk.Frame(parent, bg=COLORS["surface"])
        f.pack(fill="x", pady=(3 if not grande else 6, 0))
        tk.Label(f, text=label, font=FONT_BOLD if grande else FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text"] if grande else COLORS["text_muted"]).pack(side="left")
        val = tk.Label(f, text="$0", font=FONT_BOLD,
                       bg=COLORS["surface"], fg=COLORS["accent"])
        val.pack(side="right")
        return val

    # ── Buscador de cliente (estilo Ventas) ──────────────────────────────────

    def _buscar_jugador(self, event=None):
        from modules.clientes import buscar_clientes
        texto = self._t_jugador.get().strip()
        # al escribir se deselecciona el cliente (queda como nombre libre)
        self._insc_cli_id = None
        self._lbl_insc_cli.config(text="Nombre libre (sin cliente)", fg=COLORS["text_dim"])
        self._lst_jug.delete(0, "end")
        self._jug_result = []
        if not texto:
            self._lst_jug.pack_forget()
            return
        res = buscar_clientes(texto)[:6]
        if not res:
            self._lst_jug.pack_forget()
            return
        self._jug_result = res
        for c in res:
            self._lst_jug.insert("end", f"  {c['nombre']}  —  {c.get('documento','') or ''}")
        self._lst_jug.pack(fill="x", after=self._t_jugador, pady=(2, 0))

    def _sel_jugador(self, event=None):
        from modules.creditos import get_info_credito, migrar
        from modules.caja import formatear_pesos
        idx = self._lst_jug.curselection()
        if not idx or idx[0] >= len(getattr(self, "_jug_result", [])):
            return
        c = self._jug_result[idx[0]]
        self._insc_cli_id = c["id"]
        self._t_jugador.delete(0, "end")
        self._t_jugador.insert(0, c["nombre"])
        self._lst_jug.pack_forget()
        try:
            migrar()
            info = get_info_credito(c["id"])
            self._lbl_insc_cli.config(
                text=f"Cliente: {c['nombre']}  ·  crédito disponible {formatear_pesos(info['disponible'])}",
                fg=COLORS["accent"])
        except Exception:
            self._lbl_insc_cli.config(text=f"Cliente: {c['nombre']}", fg=COLORS["accent"])

    # ── Inscripciones ────────────────────────────────────────────────────────

    def _agregar_inscrito(self):
        from modules.validaciones import leer_entero
        nombre = self._t_jugador.get().strip()
        metodo = self._t_metodo.get()
        monto  = leer_entero(self._t_monto, default=0)
        cliente_id = self._insc_cli_id

        if not nombre:
            messagebox.showwarning("Falta el jugador", "Escribe el nombre del jugador o elige un cliente.", parent=self._win)
            return
        if monto <= 0:
            messagebox.showwarning("Monto inválido", "Ingresa el monto de la inscripción.", parent=self._win)
            return
        if metodo == "credito" and not cliente_id:
            messagebox.showwarning(
                "Crédito",
                "Para inscribir a crédito debes BUSCAR y seleccionar un cliente "
                "registrado (no un nombre libre).", parent=self._win)
            return

        self._inscritos.append({
            "nombre": nombre, "monto": monto,
            "metodo_pago": metodo, "cliente_id": cliente_id,
        })
        # limpiar fila
        self._t_jugador.delete(0, "end")
        self._t_monto.delete(0, "end")
        self._t_metodo.set("efectivo")
        self._insc_cli_id = None
        self._lbl_insc_cli.config(text="Nombre libre (sin cliente)", fg=COLORS["text_dim"])
        self._refrescar_inscritos()
        self._t_jugador.focus_set()

    def _quitar_inscrito_sel(self):
        sel = self._tree_insc.focus()
        if sel == "":
            return
        try:
            idx = int(sel)
        except ValueError:
            return
        if 0 <= idx < len(self._inscritos):
            self._inscritos.pop(idx)
            self._refrescar_inscritos()

    def _refrescar_inscritos(self):
        from modules.caja import formatear_pesos
        self._tree_insc.delete(*self._tree_insc.get_children())
        for idx, p in enumerate(self._inscritos):
            es_cred = p["metodo_pago"] == "credito"
            self._tree_insc.insert("", "end", iid=str(idx), values=(
                p["nombre"], p["metodo_pago"], formatear_pesos(p["monto"]),
            ), tags=("cred",) if es_cred else ())
        self._actualizar_pnl()

    # ── Premios ──────────────────────────────────────────────────────────────

    def _filtrar_prods(self, event=None):
        texto = self._t_buscar.get().strip().lower()
        self._lst_prods.delete(0, "end")
        for p in self._prods_tienda:
            if not texto or texto in p["nombre"].lower():
                stk = int(p["stock"]) if p["stock"] == int(p["stock"]) else p["stock"]
                self._lst_prods.insert("end", f"{p['nombre']}  (stock {stk})")

    def _agregar_premio(self):
        from modules.validaciones import leer_entero
        sel = self._lst_prods.curselection()
        if not sel:
            messagebox.showwarning("Sin selección", "Selecciona un producto de la lista.", parent=self._win)
            return
        nombre = self._lst_prods.get(sel[0]).split("  (stock")[0].strip()
        prod = self._prods_map.get(nombre)
        if not prod:
            return
        cant = leer_entero(self._t_cant, default=1)
        if cant <= 0:
            cant = 1
        # Si el sobre ya está en la lista, SUMA la cantidad (no la reemplaza),
        # para que agregar los sobres uno por uno cuente todos.
        existente = next((l for l in self._premios
                          if l["producto_id"] == prod["id"]), None)
        if existente:
            existente["cantidad"] += cant
        else:
            self._premios.append({
                "producto_id": prod["id"], "nombre": prod["nombre"],
                "cantidad": cant, "costo_unit": prod["precio_costo"] or 0,
                "stock": prod["stock"],
            })
        self._t_cant.delete(0, "end")
        self._t_cant.insert(0, "1")
        self._refrescar_premios()

    def _quitar_premio_sel(self):
        sel = self._tree_prem.focus()
        if sel == "":
            return
        try:
            pid = int(sel)
        except ValueError:
            return
        self._premios = [l for l in self._premios if l["producto_id"] != pid]
        self._refrescar_premios()

    def _refrescar_premios(self):
        from modules.caja import formatear_pesos
        self._tree_prem.delete(*self._tree_prem.get_children())
        for l in self._premios:
            cant = int(l["cantidad"]) if l["cantidad"] == int(l["cantidad"]) else l["cantidad"]
            exceso = l["cantidad"] > l["stock"]
            self._tree_prem.insert("", "end", iid=str(l["producto_id"]), values=(
                l["nombre"], f"×{cant}", formatear_pesos(l["costo_unit"] * l["cantidad"]),
            ), tags=("exceso",) if exceso else ())
        self._actualizar_pnl()

    def _actualizar_pnl(self):
        from modules.caja import formatear_pesos
        if not hasattr(self, "_lbl_res_ganancia"):
            return
        recaudado = sum(p["monto"] for p in self._inscritos)
        credito   = sum(p["monto"] for p in self._inscritos if p["metodo_pago"] == "credito")
        costo     = sum(l["costo_unit"] * l["cantidad"] for l in self._premios)
        ganancia  = recaudado - costo
        self._lbl_res_recaudado.config(text=formatear_pesos(recaudado))
        self._lbl_res_credito.config(text=formatear_pesos(credito),
                                     fg=COLORS["warning"] if credito else COLORS["text_muted"])
        self._lbl_res_costo.config(text=formatear_pesos(costo))
        self._lbl_res_ganancia.config(
            text=formatear_pesos(ganancia),
            fg=COLORS["success"] if ganancia >= 0 else COLORS["danger"])

    # ── Guardar ───────────────────────────────────────────────────────────────

    def _guardar_torneo(self):
        from modules.torneos import registrar_torneo

        nombre = self._t_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Campo vacío", "El torneo necesita un nombre.", parent=self._win)
            return
        if not self._inscritos and not self._premios:
            messagebox.showwarning("Torneo vacío", "Agrega al menos una inscripción o un premio.", parent=self._win)
            return

        try:
            res = registrar_torneo(
                nombre=nombre,
                participantes=self._inscritos,
                premios=[{"producto_id": l["producto_id"], "cantidad": l["cantidad"]}
                         for l in self._premios],
                juego=self._t_juego.get().strip() or None,
            )
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self._win)
            return

        from modules.caja import formatear_pesos
        msg = (f"Torneo '{nombre}' guardado.\n\n"
               f"Inscritos: {len(res['participantes'])}\n"
               f"Recaudado: {formatear_pesos(res['recaudado'])}\n"
               f"Costo de premios: {formatear_pesos(res['costo_premios'])}\n"
               f"Ganancia: {formatear_pesos(res['ganancia'])}")
        n_cred = sum(1 for p in res["participantes"] if p["metodo_pago"] == "credito")
        if n_cred:
            msg += f"\n\n{n_cred} inscripción(es) a crédito cargadas a su cliente."
        if res["premios"]:
            msg += f"\n{len(res['premios'])} premio(s) descontados del inventario."
        if res["venta_id"] and not res["sesion_id"]:
            msg += "\n\n⚠ Sin caja abierta: el ingreso quedó fuera de un turno."
        messagebox.showinfo("Torneo registrado", msg, parent=self._win)
        self._cargar_torneos()
        self._cerrar_ventana()

    # ══════════════════════════════════════════════════════════
    # DETALLE (modal)
    # ══════════════════════════════════════════════════════════

    def _ver_detalle(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showinfo("Selecciona un torneo",
                                "Elige un torneo de la tabla para ver el detalle.")
            return
        from modules.torneos import obtener_torneo
        from modules.caja import formatear_pesos
        t = obtener_torneo(int(sel))
        if not t:
            return

        m = ModalForm(self, f"Torneo — {t['nombre']}", ancho=450)
        self._modal = m
        body = m.body

        def info(label, valor, color=None):
            f = tk.Frame(body, bg=COLORS["surface"])
            f.pack(fill="x", padx=16, pady=(6, 0))
            tk.Label(f, text=label, font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(side="left")
            tk.Label(f, text=valor, font=FONT_BOLD, bg=COLORS["surface"],
                     fg=color or COLORS["text"]).pack(side="right")

        info("Fecha:", (t["fecha"] or "")[:16])
        if t.get("juego"):
            info("Juego:", t["juego"])
        info("Cajero:", t.get("cajero") or "—")
        info("Recaudado:", formatear_pesos(t["recaudado"] or 0), COLORS["accent"])
        info("Costo premios:", formatear_pesos(t["costo_premios"] or 0))
        info("Ganancia:", formatear_pesos(t["ganancia"] or 0),
             COLORS["success"] if (t["ganancia"] or 0) >= 0 else COLORS["danger"])

        tk.Frame(body, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=10)
        tk.Label(body, text="Inscripciones", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 6))
        if not t.get("participantes"):
            tk.Label(body, text="Sin inscripciones", font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_dim"]).pack(anchor="w", padx=16)
        else:
            for p in t["participantes"]:
                fila = tk.Frame(body, bg=COLORS["surface2"],
                                highlightbackground=COLORS["border"], highlightthickness=1)
                fila.pack(fill="x", padx=16, pady=2, ipady=3)
                nom = p["nombre"] + (f"  ({p['cliente_nombre']})"
                                     if p.get("cliente_nombre") and p["cliente_nombre"] != p["nombre"] else "")
                tk.Label(fila, text=nom, font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["text"], anchor="w").pack(side="left", padx=(8, 0), fill="x", expand=True)
                es_cred = p["metodo_pago"] == "credito"
                tk.Label(fila, text=p["metodo_pago"], font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["warning"] if es_cred else COLORS["text_muted"]).pack(side="left", padx=6)
                tk.Label(fila, text=formatear_pesos(p["monto"]), font=FONT_SMALL,
                         bg=COLORS["surface2"], fg=COLORS["accent"]).pack(side="right", padx=8)

        tk.Frame(body, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=10)
        tk.Label(body, text="Premios entregados", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 6))
        if not t["premios"]:
            tk.Label(body, text="Sin premios registrados", font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_dim"]).pack(anchor="w", padx=16, pady=(0, 8))
        else:
            for p in t["premios"]:
                fila = tk.Frame(body, bg=COLORS["surface2"],
                                highlightbackground=COLORS["border"], highlightthickness=1)
                fila.pack(fill="x", padx=16, pady=2, ipady=3)
                cant = int(p["cantidad"]) if p["cantidad"] == int(p["cantidad"]) else p["cantidad"]
                tk.Label(fila, text=p["nombre"], font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["text"], anchor="w").pack(side="left", padx=(8, 0), fill="x", expand=True)
                tk.Label(fila, text=f"×{cant}", font=FONT_SMALL, bg=COLORS["surface2"],
                         fg=COLORS["accent"]).pack(side="left", padx=6)
                tk.Label(fila, text=formatear_pesos(p["subtotal_costo"]),
                         font=FONT_SMALL, bg=COLORS["surface2"], fg=COLORS["text_muted"]).pack(side="right", padx=8)

        if t.get("notas"):
            tk.Label(body, text=f"Notas: {t['notas']}", font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"],
                     wraplength=410, justify="left").pack(anchor="w", padx=16, pady=(8, 12))

        self._btn_secondary(m.footer, "Cerrar", m.cerrar).pack(side="right", ipady=6, ipadx=16)
        m.mostrar()
