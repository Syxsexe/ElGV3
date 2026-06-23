"""
ui/clientes.py — El G POS
Gestión de clientes para facturación y clientes frecuentes.
"""
import tkinter as tk
from tkinter import ttk, messagebox
from ui.base import FrameBase, COLORS, FONT_LABEL, FONT_BOLD, FONT_SMALL


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


class FrameClientes(FrameBase):
    def __init__(self, parent):
        super().__init__(parent, "Clientes", "Registro de clientes y datos fiscales")
        self._build()

    def _build(self):
        from modules.clientes import listar_clientes, crear_cliente

        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill="both", expand=True, padx=32, pady=(0, 24))

        # Tabla de clientes
        left = tk.Frame(main, bg=COLORS["bg"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))

        tk.Label(left, text="Clientes registrados", font=FONT_BOLD,
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))

        tabla_wrap = tk.Frame(left, bg=COLORS["bg"])
        tabla_wrap.pack(fill="both", expand=True)

        cols = ("ID", "Nombre", "Documento", "Tipo", "Régimen", "Activo")
        self.tree = self._tabla(tabla_wrap, cols, alto=18)
        self.tree.column("ID", width=40)
        self.tree.column("Nombre", width=200, anchor="w")
        self.tree.column("Documento", width=120)
        self.tree.column("Tipo", width=90)
        self.tree.column("Régimen", width=130)
        self.tree.column("Activo", width=60)

        self._cargar_clientes()

        # Panel de formulario
        panel = self._card(main, width=340)
        panel.pack(side="right", fill="y")
        panel.pack_propagate(False)

        # Canvas + scrollbar for form
        canvas = tk.Canvas(panel, bg=COLORS["surface"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(panel, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=COLORS["surface"])

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        tk.Label(scroll_frame, text="Nuevo cliente", font=FONT_BOLD,
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=16, pady=(16, 12))

        campos = [
            ("Nombre", "entry_nombre", None),
            ("Tipo de documento", "combo_tipo", None),
            ("Número de documento", "entry_documento", None),
            ("Dirección", "entry_direccion", None),
            ("Teléfono", "entry_telefono", None),
            ("Email", "entry_email", None),
            ("Régimen fiscal", "combo_regimen", REGIMENES),
            ("Responsabilidad fiscal", "combo_responsabilidad", RESPONSABILIDADES),
            ("Municipio", "entry_municipio", None),
        ]

        for lbl, attr, opciones in campos:
            tk.Label(scroll_frame, text=lbl, font=FONT_SMALL,
                     bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16)
            if opciones:
                combo = ttk.Combobox(scroll_frame,
                                     values=opciones,
                                     font=FONT_LABEL, state="readonly")
                combo.set(opciones[0])
                combo.pack(fill="x", padx=16, pady=(2, 10), ipady=4)
                setattr(self, attr, combo)
            else:
                e = self._input(scroll_frame)
                e.pack(fill="x", padx=16, pady=(2, 10), ipady=5)
                setattr(self, attr, e)

        self._btn_primary(scroll_frame, "Crear cliente", self._crear_cliente).pack(
            fill="x", padx=16, ipady=10, pady=(0, 16))

    def _cargar_clientes(self):
        from modules.clientes import listar_clientes

        self.tree.delete(*self.tree.get_children())
        for c in listar_clientes():
            regimen = c.get("regimen") or "—"
            self.tree.insert("", "end", iid=str(c["id"]), values=(
                c["id"], c["nombre"], c["documento"], c["tipo_documento"],
                regimen, "Sí" if c["activo"] else "No"
            ))

    def _crear_cliente(self):
        from modules.clientes import crear_cliente

        nombre = self.entry_nombre.get().strip()
        tipo_documento = self.combo_tipo.get()
        documento = self.entry_documento.get().strip()
        direccion = self.entry_direccion.get().strip()
        telefono = self.entry_telefono.get().strip()
        email = self.entry_email.get().strip()
        regimen = self.combo_regimen.get() if hasattr(self, "combo_regimen") else None
        resp_fiscal = self.combo_responsabilidad.get() if hasattr(self, "combo_responsabilidad") else None
        municipio = self.entry_municipio.get().strip() if hasattr(self, "entry_municipio") else None

        if not nombre or not documento:
            messagebox.showwarning("Campos vacíos", "Completa nombre y documento.")
            return

        try:
            crear_cliente(
                nombre=nombre,
                tipo_documento=tipo_documento,
                documento=documento,
                direccion=direccion,
                telefono=telefono,
                email=email,
                regimen=regimen,
                responsabilidad_fiscal=resp_fiscal,
                municipio=municipio,
            )
            messagebox.showinfo("Cliente creado", f"Cliente '{nombre}' creado con éxito.")
            self.entry_nombre.delete(0, "end")
            self.entry_documento.delete(0, "end")
            self.entry_direccion.delete(0, "end")
            self.entry_telefono.delete(0, "end")
            self.entry_email.delete(0, "end")
            self.combo_tipo.set("CC")
            if hasattr(self, "combo_regimen"):
                self.combo_regimen.set(REGIMENES[0])
            if hasattr(self, "combo_responsabilidad"):
                self.combo_responsabilidad.set(RESPONSABILIDADES[0])
            if hasattr(self, "entry_municipio"):
                self.entry_municipio.delete(0, "end")
            self._cargar_clientes()
        except Exception as e:
            messagebox.showerror("Error", str(e))
