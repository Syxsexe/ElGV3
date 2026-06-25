"""
ui/clientes.py — El G POS
Gestión de clientes para facturación y clientes frecuentes.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import FrameBase, COLORS, FONT_LABEL, FONT_BOLD, FONT_SMALL, FONT_TITLE

from modules.clientes import TIPOS_DOCUMENTO

REGIMENES = [
    "Régimen Común",
    "Régimen Simplificado",
    "Gran Contribuyente",
    "No Responsable",
    "Consumidor Final",
]
RESPONSABILIDADES = [
    "R-99-PN (No responsable)",
    "O-13 (Gran contribuyente)",
    "O-15 (Autorretenedor)",
    "O-23 (Agente retención IVA)",
    "ZZ (No aplica)",
]


# ── Helper: OptionMenu con estilo oscuro ──────────────────────────────────────

def _make_optmenu(parent, variable, options):
    """tk.OptionMenu con colores del tema oscuro."""
    m = tk.OptionMenu(parent, variable, *options)
    m.config(
        bg=COLORS["surface2"], fg=COLORS["text"],
        activebackground=COLORS["accent"], activeforeground=COLORS["text"],
        highlightthickness=1, highlightbackground=COLORS["border"],
        relief="flat", font=FONT_LABEL, anchor="w",
    )
    m["menu"].config(
        bg=COLORS["surface2"], fg=COLORS["text"],
        activebackground=COLORS["accent"], activeforeground=COLORS["text"],
        font=FONT_LABEL,
    )
    return m


class FrameClientes(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Clientes", "Registro de clientes y datos fiscales")
        self._cliente_sel_id = None
        self._build()

    def _build(self):
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # ── Tabla izquierda ───────────────────────────────────────────────────
        left = tk.Frame(main, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        tk.Label(left, text="Clientes registrados", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))

        tabla_wrap = tk.Frame(left, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)

        cols = ("ID", "Nombre", "Documento", "Tipo", "Régimen", "Activo")
        self.tree = self._tabla(tabla_wrap, cols, alto=18)
        self.tree.column("ID",        width=40)
        self.tree.column("Nombre",    width=200, anchor="w")
        self.tree.column("Documento", width=120)
        self.tree.column("Tipo",      width=90)
        self.tree.column("Régimen",   width=130)
        self.tree.column("Activo",    width=60)
        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar)

        self._cargar_clientes()

        # ── Panel derecho: formulario scrollable ──────────────────────────────
        panel = self._card(main, width=340)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)

        canvas = tk.Canvas(panel, bg=COLORS["surface"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        sf = tk.Frame(canvas, bg=COLORS["surface"])   # scroll_frame

        win_id = canvas.create_window((0, 0), window=sf, anchor="nw")

        # Rellena el ancho del canvas y actualiza scroll region
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        sf.bind("<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Scroll con rueda del mouse
        def _wheel(e):
            if e.num == 4:   canvas.yview_scroll(-1, "units")
            elif e.num == 5: canvas.yview_scroll(1,  "units")
            else:            canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _wheel)
        canvas.bind_all("<Button-4>",   _wheel)
        canvas.bind_all("<Button-5>",   _wheel)

        # ── Encabezado del formulario ─────────────────────────────────────────
        self._lbl_form_titulo = tk.Label(sf, text="Nuevo cliente", font=FONT_BOLD,
                                          bg=COLORS["surface"], fg=COLORS["text"])
        self._lbl_form_titulo.pack(anchor="w", padx=16, pady=(16, 12))

        # ── Campos del formulario ─────────────────────────────────────────────
        # Orden: Nombre → Tipo doc → N° doc → Dirección → Teléfono → Email
        #        → Régimen → Responsabilidad → Municipio

        def field_label(texto):
            tk.Label(sf, text=texto, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(
                         anchor="w", padx=16)

        def entry_field(attr):
            e = self._input(sf)
            e.pack(fill="x", padx=16, pady=(3, 10), ipady=5)
            setattr(self, attr, e)

        def select_field(attr, var, options):
            m = _make_optmenu(sf, var, options)
            m.pack(fill="x", padx=16, pady=(3, 10), ipady=2)
            setattr(self, attr, var)   # guarda el StringVar

        field_label("Nombre *")
        entry_field("entry_nombre")

        self._var_tipo = tk.StringVar(value=TIPOS_DOCUMENTO[0])
        field_label("Tipo de documento *")
        select_field("combo_tipo", self._var_tipo, TIPOS_DOCUMENTO)

        field_label("Número de documento *")
        entry_field("entry_documento")

        field_label("Dirección")
        entry_field("entry_direccion")

        field_label("Teléfono")
        entry_field("entry_telefono")

        field_label("Email")
        entry_field("entry_email")

        self._var_regimen = tk.StringVar(value=REGIMENES[0])
        field_label("Régimen fiscal")
        select_field("combo_regimen", self._var_regimen, REGIMENES)

        self._var_resp = tk.StringVar(value=RESPONSABILIDADES[0])
        field_label("Responsabilidad fiscal")
        select_field("combo_responsabilidad", self._var_resp, RESPONSABILIDADES)

        field_label("Municipio")
        entry_field("entry_municipio")

        # ── Botones ───────────────────────────────────────────────────────────
        tk.Frame(sf, bg=COLORS["border"], height=1).pack(
            fill="x", padx=16, pady=(4, 12))

        self._btn_crear = self._btn_primary(sf, "Crear cliente", self._crear_cliente)
        self._btn_crear.pack(fill="x", padx=16, ipady=10)

        self._btn_editar = self._btn_primary(sf, "Guardar cambios", self._editar_cliente)
        self._btn_editar.pack(fill="x", padx=16, ipady=10, pady=(6, 0))
        self._btn_editar.pack_forget()  # solo visible al seleccionar un cliente

        tk.Button(sf, text="Nuevo (limpiar)", font=FONT_SMALL,
                  bg=COLORS["surface"], fg=COLORS["text_muted"],
                  relief="flat", cursor="hand2",
                  command=self._limpiar_form).pack(pady=(8, 16))

    # ── Tabla ─────────────────────────────────────────────────────────────────

    def _cargar_clientes(self):
        from modules.clientes import listar_clientes
        self.tree.delete(*self.tree.get_children())
        for c in listar_clientes():
            self.tree.insert("", "end", iid=str(c["id"]), values=(
                c["id"], c["nombre"], c["documento"], c["tipo_documento"],
                c.get("regimen") or "—",
                "Sí" if c["activo"] else "No",
            ))

    def _al_seleccionar(self, event=None):
        from modules.clientes import obtener_cliente
        sel = self.tree.focus()
        if not sel:
            return
        c = obtener_cliente(int(sel))
        if not c:
            return
        self._cliente_sel_id = c["id"]
        self._lbl_form_titulo.config(text=f"Editar — {c['nombre']}")

        self.entry_nombre.delete(0, "end")
        self.entry_nombre.insert(0, c["nombre"])

        self.combo_tipo.set(c.get("tipo_documento") or TIPOS_DOCUMENTO[0])

        self.entry_documento.delete(0, "end")
        self.entry_documento.insert(0, c.get("documento") or "")

        self.entry_direccion.delete(0, "end")
        self.entry_direccion.insert(0, c.get("direccion") or "")

        self.entry_telefono.delete(0, "end")
        self.entry_telefono.insert(0, c.get("telefono") or "")

        self.entry_email.delete(0, "end")
        self.entry_email.insert(0, c.get("email") or "")

        self.combo_regimen.set(c.get("regimen") or REGIMENES[0])
        self.combo_responsabilidad.set(
            c.get("responsabilidad_fiscal") or RESPONSABILIDADES[0])

        self.entry_municipio.delete(0, "end")
        self.entry_municipio.insert(0, c.get("municipio") or "")

        self._btn_crear.pack_forget()
        self._btn_editar.pack(fill="x", padx=16, ipady=10)

    def _limpiar_form(self):
        self._cliente_sel_id = None
        self._lbl_form_titulo.config(text="Nuevo cliente")
        for attr in ("entry_nombre", "entry_documento", "entry_direccion",
                     "entry_telefono", "entry_email", "entry_municipio"):
            getattr(self, attr).delete(0, "end")
        self.combo_tipo.set(TIPOS_DOCUMENTO[0])
        self.combo_regimen.set(REGIMENES[0])
        self.combo_responsabilidad.set(RESPONSABILIDADES[0])
        self._btn_editar.pack_forget()
        self._btn_crear.pack(fill="x", padx=16, ipady=10)

    # ── Acciones ──────────────────────────────────────────────────────────────

    def _crear_cliente(self):
        from modules.clientes import crear_cliente
        nombre    = self.entry_nombre.get().strip()
        tipo_doc  = self.combo_tipo.get()
        documento = self.entry_documento.get().strip()

        if not nombre or not documento:
            messagebox.showwarning("Campos vacíos", "Completa nombre y número de documento.")
            return

        try:
            crear_cliente(
                nombre=nombre,
                tipo_documento=tipo_doc,
                documento=documento,
                direccion=self.entry_direccion.get().strip() or None,
                telefono=self.entry_telefono.get().strip() or None,
                email=self.entry_email.get().strip() or None,
                regimen=self.combo_regimen.get() or None,
                responsabilidad_fiscal=self.combo_responsabilidad.get() or None,
                municipio=self.entry_municipio.get().strip() or None,
            )
            messagebox.showinfo("Éxito", f"Cliente '{nombre}' creado correctamente.")
            self._limpiar_form()
            self._cargar_clientes()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _editar_cliente(self):
        from modules.clientes import editar_cliente
        if not self._cliente_sel_id:
            return
        nombre    = self.entry_nombre.get().strip()
        tipo_doc  = self.combo_tipo.get()
        documento = self.entry_documento.get().strip()

        if not nombre or not documento:
            messagebox.showwarning("Campos vacíos", "Completa nombre y número de documento.")
            return

        try:
            editar_cliente(
                self._cliente_sel_id,
                nombre=nombre,
                tipo_documento=tipo_doc,
                documento=documento,
                direccion=self.entry_direccion.get().strip() or None,
                telefono=self.entry_telefono.get().strip() or None,
                email=self.entry_email.get().strip() or None,
                regimen=self.combo_regimen.get() or None,
                responsabilidad_fiscal=self.combo_responsabilidad.get() or None,
                municipio=self.entry_municipio.get().strip() or None,
            )
            messagebox.showinfo("Éxito", "Cliente actualizado correctamente.")
            self._limpiar_form()
            self._cargar_clientes()
        except Exception as e:
            messagebox.showerror("Error", str(e))
