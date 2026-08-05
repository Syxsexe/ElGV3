"""
ui/preparaciones.py — El G POS
Preparaciones de cocina como recetas de COSTO.

Lista las preparaciones (rellenos, salsas, masa, adobo…) con su rendimiento por
lote y su costo (por lote y por unidad), calculado a partir de los insumos que
las componen. No se lleva stock ni producción: los insumos son ilimitados y lo
que importa es el costo, que sube en cascada hasta el costo de cada plato.
"""
import tkinter as tk
from tkinter import ttk, messagebox

import auth
from ui.base import FrameBase, COLORS, FONT_LABEL, FONT_BOLD, FONT_SMALL
from ui.modal import ModalForm

_UNIDADES = ["g", "ml", "unidad"]


def _fmt(n) -> str:
    """Muestra un número sin decimales si es entero."""
    try:
        n = float(n)
    except (TypeError, ValueError):
        return str(n)
    return f"{int(n)}" if n == int(n) else f"{n:g}"


class FramePreparaciones(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Preparaciones",
                         "Recetas de cocina y su costo (a partir de los insumos)")
        self._modal = None
        self._preps = []
        self._build()

    # ── Layout principal ──────────────────────────────────────────────────────

    def _build(self):
        acciones = tk.Frame(self, bg=COLORS["bg"])
        acciones.pack(fill="x", padx=32, pady=(0, 8))
        if auth.es_admin():
            self._btn_primary(acciones, "+ Nueva preparación",
                              lambda: self._modal_prep(None)).pack(
                side="right", padx=(0, 8), ipady=4, ipadx=12)
            self._btn_secondary(acciones, "✎ Editar receta", self._editar_sel).pack(
                side="right", padx=(0, 8), ipady=4, ipadx=12)
        self._btn_secondary(acciones, "↻ Actualizar", self._cargar).pack(
            side="right", ipady=4, ipadx=12)

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        tk.Label(main, text="Las preparaciones (adobo, salsas, rellenos, masa) son recetas "
                            "que aportan costo. El costo por lote y por unidad sale de los "
                            "insumos que las componen.",
                 font=FONT_SMALL, bg=COLORS["bg"], fg=COLORS["text_muted"],
                 wraplength=900, justify="left").pack(anchor="w", pady=(0, 6))

        tabla_wrap = tk.Frame(main, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)
        cols = ("nombre", "unidad", "rendimiento", "costo_lote", "costo_unidad", "comps")
        self.tree = self._tabla(tabla_wrap, cols, alto=14)
        textos = {"nombre": "Preparación", "unidad": "Unidad", "rendimiento": "Rinde x lote",
                  "costo_lote": "Costo x lote", "costo_unidad": "Costo x unidad",
                  "comps": "Ingredientes"}
        anchos = {"nombre": 240, "unidad": 80, "rendimiento": 110,
                  "costo_lote": 120, "costo_unidad": 130, "comps": 100}
        for c in cols:
            self.tree.heading(c, text=textos[c])
            anchor = "w" if c == "nombre" else ("center" if c in ("unidad", "comps") else "e")
            self.tree.column(c, width=anchos[c], anchor=anchor)
        if auth.es_admin():
            self.tree.bind("<Double-1>", lambda e: self._editar_sel())

        self._cargar()

    def _cargar(self):
        from modules.preparaciones import listar_preparaciones
        from modules.inventario import costo_insumo
        from modules.caja import formatear_pesos
        self._preps = listar_preparaciones()
        self.tree.delete(*self.tree.get_children())
        for p in self._preps:
            costo_unit = costo_insumo(p["id"])
            costo_lote = costo_unit * (p["rendimiento"] or 0)
            costo_unit_txt = f"{formatear_pesos(costo_unit)} /{p['unidad']}" if costo_unit else "—"
            costo_lote_txt = formatear_pesos(costo_lote) if costo_lote else "—"
            self.tree.insert("", "end", iid=str(p["id"]), values=(
                p["nombre"], p["unidad"], _fmt(p["rendimiento"]),
                costo_lote_txt, costo_unit_txt, p["num_componentes"],
            ))

    def _cerrar_modal(self):
        if self._modal is not None:
            try:
                self._modal.cerrar()
            except tk.TclError:
                pass
            self._modal = None

    # ══════════════════════════════════════════════════════════
    # MODAL — CREAR / EDITAR PREPARACIÓN (rendimiento + receta)
    # ══════════════════════════════════════════════════════════

    def _editar_sel(self):
        sel = self.tree.focus()
        if not sel:
            messagebox.showinfo("Selecciona una preparación",
                                "Elige una preparación de la lista para editar su receta.")
            return
        self._modal_prep(int(sel))

    def _modal_prep(self, prep_id=None):
        """Crear una preparación nueva o editar el rendimiento y la receta de una."""
        from modules.inventario import listar_insumos, obtener_insumo
        from modules.preparaciones import obtener_receta_prep

        editar = prep_id is not None
        self._pr_edit_id = prep_id
        self._pr_lineas = []          # [{insumo_id, nombre, unidad, cantidad}]
        nombre_actual = ""

        if editar:
            prep = obtener_receta_prep(prep_id)
            if not prep:
                return
            nombre_actual = prep["nombre"]
            self._pr_lineas = [{
                "insumo_id": c["insumo_id"], "nombre": c["nombre"],
                "unidad": c["unidad"], "cantidad": c["cantidad"],
            } for c in prep["componentes"]]

        # Insumos disponibles como componentes (no la preparación misma).
        self._pr_insumos = [i for i in listar_insumos() if i["id"] != prep_id]
        self._pr_insumos_map = {i["nombre"]: i for i in self._pr_insumos}

        m = ModalForm(self, "Editar preparación" if editar else "Nueva preparación",
                      ancho=470)
        self._modal = m
        body = m.body

        def etiqueta(txt):
            tk.Label(body, text=txt, font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(8, 0))

        etiqueta("Nombre de la preparación *")
        self._pr_nombre = self._input(body)
        self._pr_nombre.pack(fill="x", padx=16, pady=(2, 0), ipady=5)
        if editar:
            self._pr_nombre.insert(0, nombre_actual)

        fila = tk.Frame(body, bg=COLORS["surface"])
        fila.pack(fill="x", padx=16, pady=(8, 0))
        colu = tk.Frame(fila, bg=COLORS["surface"]); colu.pack(side="left")
        tk.Label(colu, text="Unidad", font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w")
        self._pr_unidad = ttk.Combobox(colu, values=_UNIDADES, state="readonly",
                                       font=FONT_LABEL, width=8)
        self._pr_unidad.set(prep["unidad"] if editar else "g")
        self._pr_unidad.pack()
        colr = tk.Frame(fila, bg=COLORS["surface"]); colr.pack(side="left", padx=(16, 0))
        tk.Label(colr, text="Rinde por lote *", font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(anchor="w")
        self._pr_rend = self._input(colr, width=12)
        self._pr_rend.pack(ipady=3)
        if editar:
            self._pr_rend.insert(0, _fmt(prep["rendimiento"]))

        tk.Label(body, text="Rinde = cuánto produce UN lote en esa unidad "
                            "(p. ej. un lote de masa rinde 1220 g).",
                 font=FONT_SMALL, bg=COLORS["surface"], fg=COLORS["text_dim"],
                 wraplength=430, justify="left").pack(anchor="w", padx=16, pady=(4, 0))

        tk.Frame(body, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=10)

        # ── Ingredientes del lote ──────────────────────────────────────────
        tk.Label(body, text="Ingredientes del lote (crudos u otras preparaciones)",
                 font=FONT_BOLD, bg=COLORS["surface"], fg=COLORS["text"]).pack(
                     anchor="w", padx=16, pady=(0, 6))
        etiqueta("Buscar insumo")
        self._pr_buscar = self._input(body)
        self._pr_buscar.pack(fill="x", padx=16, pady=(2, 4), ipady=5)
        self._pr_buscar.bind("<KeyRelease>", lambda e: self._pr_filtrar())

        lst_wrap = tk.Frame(body, bg=COLORS["surface"])
        lst_wrap.pack(fill="x", padx=16, pady=(0, 6))
        self._pr_lst = tk.Listbox(
            lst_wrap, font=FONT_SMALL, height=5,
            bg=COLORS["surface2"], fg=COLORS["text"], selectbackground=COLORS["accent"],
            relief="flat", activestyle="none",
            highlightthickness=1, highlightbackground=COLORS["border"])
        self._pr_lst.pack(fill="x")

        cf = tk.Frame(body, bg=COLORS["surface"])
        cf.pack(fill="x", padx=16, pady=(0, 6))
        tk.Label(cf, text="Cantidad:", font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_muted"]).pack(side="left")
        self._pr_cant = self._input(cf, width=8)
        self._pr_cant.insert(0, "1")
        self._pr_cant.pack(side="left", padx=(6, 0), ipady=4)
        self._btn_primary(body, "+ Agregar ingrediente", self._pr_agregar).pack(
            fill="x", padx=16, ipady=6)

        tk.Frame(body, bg=COLORS["border"], height=1).pack(fill="x", padx=16, pady=10)
        tk.Label(body, text="Receta de producción", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(0, 6))
        self._pr_tabla = tk.Frame(body, bg=COLORS["surface"])
        self._pr_tabla.pack(fill="x", padx=16, pady=(0, 12))

        self._btn_secondary(m.footer, "Cancelar", m.cerrar).pack(side="left", ipady=6, ipadx=14)
        self._btn_primary(m.footer, "Guardar preparación", self._pr_guardar).pack(
            side="right", ipady=6, ipadx=16)

        self._pr_filtrar()
        self._pr_refrescar()
        m.mostrar()

    def _pr_filtrar(self):
        texto = (self._pr_buscar.get() or "").strip().lower()
        self._pr_lst.delete(0, "end")
        for i in self._pr_insumos:
            if not texto or texto in i["nombre"].lower():
                self._pr_lst.insert("end", f"{i['nombre']}  ({i['unidad']})")

    def _pr_agregar(self):
        sel = self._pr_lst.curselection()
        if not sel:
            messagebox.showwarning("Sin selección",
                                   "Elige un insumo de la lista.", parent=self._modal)
            return
        nombre = self._pr_lst.get(sel[0]).rsplit("  (", 1)[0].strip()
        ins = self._pr_insumos_map.get(nombre)
        if not ins:
            return
        try:
            cant = float((self._pr_cant.get() or "").strip().replace(",", "."))
        except ValueError:
            cant = 0
        if cant <= 0:
            messagebox.showwarning("Cantidad inválida",
                                   "Escribe una cantidad mayor que 0.", parent=self._modal)
            return
        existe = next((l for l in self._pr_lineas if l["insumo_id"] == ins["id"]), None)
        if existe:
            existe["cantidad"] += cant
        else:
            self._pr_lineas.append({
                "insumo_id": ins["id"], "nombre": ins["nombre"],
                "unidad": ins["unidad"], "cantidad": cant,
            })
        self._pr_cant.delete(0, "end"); self._pr_cant.insert(0, "1")
        self._pr_refrescar()

    def _pr_quitar(self, insumo_id):
        self._pr_lineas = [l for l in self._pr_lineas if l["insumo_id"] != insumo_id]
        self._pr_refrescar()

    def _pr_refrescar(self):
        for w in self._pr_tabla.winfo_children():
            w.destroy()
        if not self._pr_lineas:
            tk.Label(self._pr_tabla, text="Aún sin ingredientes.", font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_dim"]).pack(anchor="w")
            return
        for l in self._pr_lineas:
            fila = tk.Frame(self._pr_tabla, bg=COLORS["surface2"],
                            highlightbackground=COLORS["border"], highlightthickness=1)
            fila.pack(fill="x", pady=2, ipady=3)
            tk.Button(fila, text="✕", font=FONT_SMALL, bg=COLORS["surface2"],
                      fg=COLORS["danger"], relief="flat", bd=0, cursor="hand2",
                      command=lambda i=l["insumo_id"]: self._pr_quitar(i)).pack(side="left", padx=(6, 2))
            tk.Label(fila, text=l["nombre"], font=FONT_SMALL, bg=COLORS["surface2"],
                     fg=COLORS["text"], anchor="w").pack(side="left", fill="x", expand=True)
            tk.Label(fila, text=f"{_fmt(l['cantidad'])} {l['unidad']}", font=FONT_SMALL,
                     bg=COLORS["surface2"], fg=COLORS["accent"]).pack(side="right", padx=8)

    def _pr_guardar(self):
        from modules.inventario import crear_insumo, editar_insumo
        from modules.preparaciones import guardar_receta_prep

        nombre = (self._pr_nombre.get() or "").strip()
        if not nombre:
            messagebox.showwarning("Falta el nombre",
                                   "La preparación necesita un nombre.", parent=self._modal)
            return
        try:
            rend = float((self._pr_rend.get() or "").strip().replace(",", "."))
        except ValueError:
            rend = 0
        if rend <= 0:
            messagebox.showwarning("Rendimiento inválido",
                                   "Indica cuánto rinde un lote (mayor que 0).",
                                   parent=self._modal)
            return
        if not self._pr_lineas:
            messagebox.showwarning("Sin receta",
                                   "Agrega al menos un ingrediente.", parent=self._modal)
            return
        unidad = self._pr_unidad.get() or "g"

        try:
            if self._pr_edit_id is not None:
                prep_id = self._pr_edit_id
                editar_insumo(prep_id, nombre=nombre, unidad=unidad)
            else:
                # Nueva: si ya existe un insumo con ese nombre, se reutiliza
                # (se convierte en preparación); si no, se crea.
                existente = next((i for i in self._pr_insumos
                                  if i["nombre"].lower() == nombre.lower()), None)
                if existente:
                    prep_id = existente["id"]
                    editar_insumo(prep_id, unidad=unidad)
                else:
                    prep_id = crear_insumo(nombre, unidad=unidad)
            guardar_receta_prep(
                prep_id, rend,
                [{"insumo_id": l["insumo_id"], "cantidad": l["cantidad"]}
                 for l in self._pr_lineas])
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self._modal)
            return

        messagebox.showinfo(
            "Preparación guardada",
            f"'{nombre}' quedó lista.\nRinde {_fmt(rend)} {unidad} por lote, "
            f"{len(self._pr_lineas)} ingrediente(s).\n\n"
            "Su costo se calcula solo a partir de los insumos.",
            parent=self._modal)
        self._cerrar_modal()
        self._cargar()
