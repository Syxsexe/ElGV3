"""
ui/fiscal.py — El G POS
Fiscal documents and DIAN electronic invoicing management.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import FrameBase, COLORS, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_SUB


class FrameFiscal(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Documentos Fiscales",
                         "Facturación electrónica DIAN — estado, reenvío y notas")
        self._build()

    def _build(self):
        from modules.sync import get_sync_manager
        self.sync_mgr = get_sync_manager()

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # ── Top bar: status + actions ──────────────────────────────────────
        top = tk.Frame(main, bg=COLORS["bg"])
        top.pack(fill="x", pady=(0, 12))

        self.lbl_conexion = tk.Label(
            top, text="Verificando conexión...", font=FONT_BOLD,
            bg=COLORS["bg"], fg=COLORS["text_muted"]
        )
        self.lbl_conexion.pack(side="left")

        self._btn_primary(top, "⟳ Verificar conexión", self._check_connection).pack(
            side="right", padx=(6, 0), ipady=4)

        self._btn_primary(top, "↻ Reintentar fallidos", self._retry_failed).pack(
            side="right", padx=(6, 0), ipady=4)

        self._btn_primary(top, "⚙ Configurar DIAN", self._open_config).pack(
            side="right", padx=(6, 0), ipady=4)

        # ── Notebook: Facturas / Cola de sincronización ────────────────────
        notebook = ttk.Notebook(main)
        notebook.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=COLORS["surface2"],
                        foreground=COLORS["text_muted"],
                        font=FONT_BOLD, padding=[14, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", COLORS["surface"])],
                  foreground=[("selected", COLORS["text"])])

        # ── Tab: Facturas emitidas ─────────────────────────────────────────
        facturas_frame = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(facturas_frame, text="Facturas emitidas")

        cols_fact = (
            "ID", "Venta", "Cliente", "Documento", "Total",
            "Estado DIAN", "CUFE", "UUID"
        )
        self.tree_facturas = self._tabla(facturas_frame, cols_fact, alto=14)
        self.tree_facturas.column("ID", width=40)
        self.tree_facturas.column("Venta", width=50)
        self.tree_facturas.column("Cliente", width=160, anchor="w")
        self.tree_facturas.column("Documento", width=120)
        self.tree_facturas.column("Total", width=90)
        self.tree_facturas.column("Estado DIAN", width=110)
        self.tree_facturas.column("CUFE", width=260, anchor="w")
        self.tree_facturas.column("UUID", width=200, anchor="w")
        self.tree_facturas.bind("<Button-3>", self._context_menu_factura)
        self.tree_facturas.pack(fill="both", expand=True, pady=(0, 8))

        btn_frame = tk.Frame(facturas_frame, bg=COLORS["bg"])
        btn_frame.pack(fill="x")

        self._btn_primary(btn_frame, "⟳ Actualizar", self._cargar_facturas).pack(
            side="left", ipady=6, padx=(0, 6))
        self._btn_primary(btn_frame, "☰ Nota crédito", self._crear_nota_credito).pack(
            side="left", ipady=6)

        # ── Tab: Cola de sincronización ────────────────────────────────────
        sync_frame = tk.Frame(notebook, bg=COLORS["bg"])
        notebook.add(sync_frame, text="Cola de sincronización")

        cols_sync = (
            "UUID", "Tipo", "ID local", "Acción", "Estado",
            "Intentos", "Error"
        )
        self.tree_sync = self._tabla(sync_frame, cols_sync, alto=12)
        self.tree_sync.column("UUID", width=210, anchor="w")
        self.tree_sync.column("Tipo", width=80)
        self.tree_sync.column("ID local", width=70)
        self.tree_sync.column("Acción", width=70)
        self.tree_sync.column("Estado", width=100)
        self.tree_sync.column("Intentos", width=70)
        self.tree_sync.column("Error", width=250, anchor="w")
        self.tree_sync.pack(fill="both", expand=True, pady=(0, 8))

        btn_sync = tk.Frame(sync_frame, bg=COLORS["bg"])
        btn_sync.pack(fill="x")

        self._btn_primary(btn_sync, "⟳ Actualizar cola", self._cargar_sync_queue).pack(
            side="left", ipady=6, padx=(0, 6))
        self._btn_danger(btn_sync, "✕ Limpiar sincronizados",
                         self._clear_synced).pack(side="left", ipady=6)

        # ── Load data ──────────────────────────────────────────────────────
        self._cargar_facturas()
        self._cargar_sync_queue()
        self._check_connection()

    # ── Facturas ───────────────────────────────────────────────────────────

    def _cargar_facturas(self):
        from modules.caja import formatear_pesos
        from database import get_connection

        self.tree_facturas.delete(*self.tree_facturas.get_children())
        conn = get_connection()
        filas = conn.execute(
            "SELECT f.*, v.total as venta_total, c.nombre as cliente_nombre"
            " FROM facturas f"
            " JOIN ventas v ON v.id = f.venta_id"
            " LEFT JOIN clientes c ON c.id = f.cliente_id"
            " ORDER BY f.id DESC LIMIT 100"
        ).fetchall()
        conn.close()

        for f in filas:
            status = f["dian_status"] or "pendiente"
            status_text = {
                "aceptada": "✓ Aceptada",
                "rechazada": "✗ Rechazada",
                "contingencia": "⚠ Contingencia",
                "pendiente": "○ Pendiente",
                "error": "✗ Error",
            }.get(status, status)

            self.tree_facturas.insert("", "end", iid=str(f["id"]), values=(
                f["id"],
                f["venta_id"],
                f["cliente_nombre"] or (f["documento"] or "")[:12],
                f["documento"] or "",
                formatear_pesos(f["total"]),
                status_text,
                (f["dian_cufe"] or "")[:40] + "..." if f["dian_cufe"] else "",
                f["dian_uuid"] or "",
            ))

    def _context_menu_factura(self, event):
        sel = self.tree_facturas.focus()
        if not sel:
            return

        menu = tk.Menu(self, tearoff=0, bg=COLORS["surface"],
                       fg=COLORS["text"], font=FONT_SMALL)
        menu.add_command(label="Ver CUFE completo", command=lambda: self._ver_cufe(sel))
        menu.add_command(label="Consultar estado en DIAN",
                         command=lambda: self._consultar_estado_dian(sel))
        menu.add_separator()
        menu.add_command(label="Generar nota crédito",
                         command=lambda: self._crear_nota_credito(sel))
        menu.add_command(label="Reenviar a DIAN",
                         command=lambda: self._reenviar_factura(sel))
        menu.post(event.x_root, event.y_root)

    def _ver_cufe(self, factura_id):
        from database import get_connection
        conn = get_connection()
        f = conn.execute(
            "SELECT dian_cufe, dian_qr, numero FROM facturas WHERE id = ?",
            (factura_id,)
        ).fetchone()
        conn.close()
        if not f or not f["dian_cufe"]:
            messagebox.showinfo("CUFE", "Esta factura no tiene CUFE asignado.")
            return

        DialogVerCufe(self, f["dian_cufe"], f.get("dian_qr"), f["numero"])

    def _consultar_estado_dian(self, factura_id):
        from database import get_connection
        from modules.dian_client import sync_health_check
        conn = get_connection()
        f = conn.execute(
            "SELECT dian_uuid FROM facturas WHERE id = ?", (factura_id,)
        ).fetchone()
        conn.close()
        if not f or not f["dian_uuid"]:
            messagebox.showinfo("Estado", "UUID no disponible para consulta.")
            return
        messagebox.showinfo("Consulta", "Funcionalidad de consulta DIAN en desarrollo.")

    def _reenviar_factura(self, factura_id):
        from database import get_connection
        from modules.sync import get_sync_manager
        from modules.fiscal_documents import preparar_venta_para_dian
        from modules.clientes import obtener_cliente

        conn = get_connection()
        f = conn.execute("SELECT * FROM facturas WHERE id = ?", (factura_id,)).fetchone()
        if not f:
            conn.close()
            return
        venta = conn.execute("SELECT * FROM ventas WHERE id = ?", (f["venta_id"],)).fetchone()
        detalle = conn.execute(
            "SELECT * FROM detalle_venta WHERE venta_id = ?", (f["venta_id"],)
        ).fetchall()
        conn.close()
        if not venta:
            return

        venta_data = dict(venta)
        venta_data["detalle"] = [dict(d) for d in detalle]
        cliente = obtener_cliente(f["cliente_id"]) if f["cliente_id"] else None
        payload = preparar_venta_para_dian(venta_data, cliente)

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if not loop.is_running():
            result = loop.run_until_complete(
                get_sync_manager().process_venta(payload)
            )
            if result.get("estado") == "sincronizado":
                messagebox.showinfo("Reenvío", "Factura reenviada exitosamente.")
            else:
                msg = result.get("error", "Error desconocido")
                messagebox.showwarning("Reenvío", f"Error: {msg}")
        self._cargar_facturas()
        self._cargar_sync_queue()

    # ── Nota crédito ───────────────────────────────────────────────────────

    def _crear_nota_credito(self, factura_id=None):
        if not factura_id:
            sel = self.tree_facturas.focus()
            if not sel:
                messagebox.showwarning("Seleccionar", "Selecciona una factura.")
                return
            factura_id = int(sel)
        DialogNotaCredito(self, factura_id)

    # ── Sync queue ─────────────────────────────────────────────────────────

    def _cargar_sync_queue(self):
        self.tree_sync.delete(*self.tree_sync.get_children())
        for entry in self.sync_mgr.get_all():
            self.tree_sync.insert("", "end", values=(
                entry["uuid"][:18] + "...",
                entry["entidad_tipo"],
                entry["entidad_id_local"],
                entry["accion"],
                entry["estado"],
                entry["intentos"],
                (entry["ultimo_error"] or "")[:40],
            ))

    def _clear_synced(self):
        self.sync_mgr.clear_synced()
        self._cargar_sync_queue()
        messagebox.showinfo("Cola", "Elementos sincronizados eliminados.")

    def _retry_failed(self):
        pending = self.sync_mgr.retry_failed()
        self._cargar_sync_queue()
        messagebox.showinfo("Reintento", f"{len(pending)} operaciones marcadas para reintento.")

    # ── Connection ─────────────────────────────────────────────────────────

    def _check_connection(self):
        from modules.dian_client import sync_health_check, is_configured

        if not is_configured():
            self.lbl_conexion.config(text="⚠ DIAN no configurado", fg=COLORS["warning"])
            return

        try:
            result = sync_health_check()
            if result.get("status") == "ok":
                self.lbl_conexion.config(text="✓ Conectado con el backend", fg=COLORS["success"])
            else:
                self.lbl_conexion.config(text="✗ Backend no responde", fg=COLORS["danger"])
        except Exception:
            self.lbl_conexion.config(text="✗ Error de conexión", fg=COLORS["danger"])

        # Also show pending count
        pending = self.sync_mgr.pending_count()
        if pending:
            self.lbl_conexion.config(
                text=self.lbl_conexion.cget("text") + f" | {pending} pendiente(s)"
            )

    # ── Config ─────────────────────────────────────────────────────────────

    def _open_config(self):
        DialogDianConfig(self, self._check_connection)


# ── Dialogs ───────────────────────────────────────────────────────────────────

class DialogVerCufe(tk.Toplevel):
    def __init__(self, parent, cufe, qr_b64, numero):
        super().__init__(parent)
        self.title(f"CUFE — Factura {numero}")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)

        card = tk.Frame(self, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"],
                        highlightthickness=1)
        card.pack(padx=20, pady=20, ipadx=16, ipady=16)

        tk.Label(card, text=f"Factura N° {numero}", font=FONT_SUB,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(0, 8))

        tk.Label(card, text="CUFE", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        txt_cufe = tk.Text(card, height=4, width=50, font=("Courier", 9),
                           bg=COLORS["surface2"], fg=COLORS["text"],
                           relief="flat", bd=0, wrap="word")
        txt_cufe.insert("1.0", cufe)
        txt_cufe.configure(state="disabled")
        txt_cufe.pack(fill="x", pady=(4, 8))

        from modules.validaciones import copiar_al_portapapeles
        tk.Button(card, text="Copiar CUFE", font=FONT_SMALL,
                  bg=COLORS["surface2"], fg=COLORS["accent"],
                  relief="flat", cursor="hand2",
                  command=lambda: copiar_al_portapapeles(cufe)).pack(pady=(0, 8))

        if qr_b64:
            try:
                import base64, io
                from PIL import Image, ImageTk
                img_data = base64.b64decode(qr_b64)
                img = Image.open(io.BytesIO(img_data))
                img = img.resize((100, 100), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                lbl_qr = tk.Label(card, image=photo, bg=COLORS["surface"])
                lbl_qr.image = photo
                lbl_qr.pack(pady=8)
            except Exception:
                pass

        tk.Button(card, text="Cerrar", font=FONT_BOLD,
                  bg=COLORS["accent"], fg=COLORS["on_accent"],
                  relief="flat", cursor="hand2",
                  command=self.destroy).pack(pady=(8, 0), ipadx=20, ipady=6)

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.grab_set()


class DialogNotaCredito(tk.Toplevel):
    def __init__(self, parent, factura_id):
        super().__init__(parent)
        self.factura_id = factura_id
        self.result = None
        self.title("Nota Crédito")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)

        from database import get_connection
        conn = get_connection()
        f = conn.execute(
            "SELECT f.*, v.total FROM facturas f"
            " JOIN ventas v ON v.id = f.venta_id"
            " WHERE f.id = ?", (factura_id,)
        ).fetchone()
        conn.close()

        card = tk.Frame(self, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"],
                        highlightthickness=1)
        card.pack(padx=20, pady=20, ipadx=16, ipady=16)

        tk.Label(card, text="Generar Nota Crédito", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(0, 8))

        if f:
            info = f"Factura N° {f['numero']} — Venta #{f['venta_id']} — ${f['total']:,.0f}"
            tk.Label(card, text=info, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(pady=(0, 12))

        tk.Label(card, text="Motivo", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        self.txt_motivo = tk.Text(card, height=4, width=40, font=FONT_LABEL,
                                  bg=COLORS["surface2"], fg=COLORS["text"],
                                  relief="flat", bd=0,
                                  highlightthickness=1,
                                  highlightbackground=COLORS["border"])
        self.txt_motivo.pack(fill="x", pady=(4, 12))

        self.var_anulacion_total = tk.BooleanVar(value=True)
        tk.Checkbutton(card, text="Anulación total de la factura",
                       variable=self.var_anulacion_total,
                       font=FONT_SMALL,
                       bg=COLORS["surface"], fg=COLORS["text"],
                       selectcolor=COLORS["surface2"],
                       activebackground=COLORS["surface"],
                       cursor="hand2").pack(anchor="w")

        btn_frame = tk.Frame(card, bg=COLORS["surface"])
        btn_frame.pack(fill="x", pady=(12, 0))

        tk.Button(btn_frame, text="Cancelar", font=FONT_BOLD,
                  bg=COLORS["surface2"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=self.destroy).pack(side="left", ipadx=16, ipady=6, padx=(0, 8))

        tk.Button(btn_frame, text="Crear Nota Crédito", font=FONT_BOLD,
                  bg=COLORS["accent"], fg=COLORS["on_accent"],
                  relief="flat", cursor="hand2",
                  command=self._confirmar).pack(side="right", ipadx=16, ipady=6)

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.grab_set()

    def _confirmar(self):
        from modules.fiscal_documents import crear_nota_credito
        from modules.sync import get_sync_manager
        from database import get_connection

        motivo = self.txt_motivo.get("1.0", "end").strip()
        if not motivo:
            messagebox.showwarning("Motivo", "Ingresa el motivo de la nota crédito.")
            return

        conn = get_connection()
        f = conn.execute("SELECT venta_id FROM facturas WHERE id = ?",
                         (self.factura_id,)).fetchone()
        conn.close()
        if not f:
            messagebox.showerror("Error", "Factura no encontrada.")
            return

        try:
            nc_data = crear_nota_credito(
                venta_id=f["venta_id"],
                motivo=motivo,
                items_anular=None if self.var_anulacion_total.get() else [],
            )
            sync_mgr = get_sync_manager()
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            if not loop.is_running():
                result = loop.run_until_complete(
                    sync_mgr.process_venta(nc_data)
                )
                if result.get("estado") == "sincronizado":
                    messagebox.showinfo("Nota Crédito", "Nota crédito creada y enviada a DIAN.")
                else:
                    messagebox.showwarning("Nota Crédito",
                                           "Nota crédito creada localmente. "
                                           "Pendiente de sincronización con DIAN.")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))


class DialogDianConfig(tk.Toplevel):
    def __init__(self, parent, on_save_callback=None):
        super().__init__(parent)
        self.on_save = on_save_callback
        self.title("Configuración DIAN")
        self.configure(bg=COLORS["bg"])
        self.resizable(False, False)

        from modules.dian_client import load_config
        cfg = load_config()

        card = tk.Frame(self, bg=COLORS["surface"],
                        highlightbackground=COLORS["border"],
                        highlightthickness=1)
        card.pack(padx=20, pady=20, ipadx=20, ipady=20)

        tk.Label(card, text="Configuración del Backend DIAN", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(pady=(0, 16))

        fields = [
            ("URL del Backend", "entry_url", cfg.get("backend_url", "http://localhost:8000")),
            ("Client ID", "entry_client_id", cfg.get("client_id", "")),
            ("Client Secret", "entry_secret", cfg.get("client_secret", "")),
        ]

        for lbl, attr, default in fields:
            tk.Label(card, text=lbl, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
            e = tk.Entry(card, font=FONT_LABEL,
                         bg=COLORS["surface2"], fg=COLORS["text"],
                         insertbackground=COLORS["accent"],
                         relief="flat", bd=0,
                         highlightthickness=1,
                         highlightbackground=COLORS["border"])
            e.insert(0, default)
            e.pack(fill="x", pady=(2, 12), ipady=5)
            setattr(self, attr, e)

        btn_frame = tk.Frame(card, bg=COLORS["surface"])
        btn_frame.pack(fill="x", pady=(8, 0))

        tk.Button(btn_frame, text="Cancelar", font=FONT_BOLD,
                  bg=COLORS["surface2"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=self.destroy).pack(side="left", ipadx=16, ipady=6, padx=(0, 8))

        self._btn_save = tk.Button(btn_frame, text="Guardar", font=FONT_BOLD,
                                   bg=COLORS["accent"], fg=COLORS["on_accent"],
                                   relief="flat", cursor="hand2",
                                   command=self._guardar)
        self._btn_save.pack(side="right", ipadx=16, ipady=6)

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.grab_set()

    def _guardar(self):
        from modules.dian_client import set_backend_url, set_credentials
        url = self.entry_url.get().strip()
        cid = self.entry_client_id.get().strip()
        secret = self.entry_secret.get().strip()

        if not url or not cid or not secret:
            messagebox.showwarning("Campos vacíos", "Completa todos los campos.")
            return

        set_backend_url(url)
        set_credentials(cid, secret)
        messagebox.showinfo("Configuración", "Configuración DIAN guardada.")
        if self.on_save:
            self.on_save()
        self.destroy()
