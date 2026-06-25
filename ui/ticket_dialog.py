"""
ui/ticket_dialog.py — El G POS
Diálogo de previsualización e impresión de tickets.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ui.base import COLORS, FONT_BOLD, FONT_SMALL, FONT_LABEL, _add_hover


class DialogTicket(tk.Toplevel):
    """
    Muestra el ticket generado con opciones de imprimir, guardar y cerrar.
    """

    def __init__(self, parent, texto: str, titulo: str = "Ticket"):
        super().__init__(parent)
        self.title(titulo)
        self.configure(bg=COLORS["bg"])
        self.resizable(True, True)
        self.grab_set()
        self.focus_force()
        self._texto = texto
        self._build()
        self._centrar(520, 620)
        self.bind("<Escape>", lambda e: self.destroy())

    def _centrar(self, w, h):
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build(self):
        from modules.ticket import listar_impresoras

        outer = tk.Frame(self, bg=COLORS["bg"])
        outer.pack(fill="both", expand=True, padx=20, pady=20)

        # ── Cabecera ──────────────────────────────────────────────────────────
        header_card = tk.Frame(outer, bg=COLORS["surface"],
                               highlightbackground=COLORS["border"],
                               highlightthickness=1)
        header_card.pack(fill="x", pady=(0, 14))

        tk.Frame(header_card, bg=COLORS["accent"], height=3).pack(fill="x")

        header_inner = tk.Frame(header_card, bg=COLORS["surface"])
        header_inner.pack(fill="x", padx=16, pady=10)

        tk.Label(header_inner, text="Vista previa del ticket",
                 font=FONT_BOLD, bg=COLORS["surface"],
                 fg=COLORS["text"]).pack(side="left")

        tk.Label(header_inner, text="Monospace · Solo lectura",
                 font=FONT_SMALL, bg=COLORS["surface"],
                 fg=COLORS["text_dim"]).pack(side="right")

        # ── Vista previa ──────────────────────────────────────────────────────
        preview_wrap = tk.Frame(outer, bg=COLORS["surface"],
                                highlightbackground=COLORS["border"],
                                highlightthickness=1)
        preview_wrap.pack(fill="both", expand=True, pady=(0, 14))

        self._txt = tk.Text(
            preview_wrap,
            font=("Courier New", 9),
            bg=COLORS["surface"], fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            selectbackground=COLORS["accent"],
            selectforeground=COLORS["text"],
            relief="flat", bd=0,
            highlightthickness=0,
            wrap="none",
            padx=14, pady=12,
        )
        scroll_y = ttk.Scrollbar(preview_wrap, orient="vertical",
                                  command=self._txt.yview)
        scroll_x = ttk.Scrollbar(preview_wrap, orient="horizontal",
                                  command=self._txt.xview)
        self._txt.configure(yscrollcommand=scroll_y.set,
                             xscrollcommand=scroll_x.set)

        scroll_y.pack(side="right", fill="y")
        scroll_x.pack(side="bottom", fill="x")
        self._txt.pack(fill="both", expand=True)

        self._txt.insert("1.0", self._texto)
        self._txt.config(state="disabled")

        # ── Panel inferior: impresora + botones ───────────────────────────────
        bottom = tk.Frame(outer, bg=COLORS["surface"],
                          highlightbackground=COLORS["border"],
                          highlightthickness=1)
        bottom.pack(fill="x")

        tk.Frame(bottom, bg=COLORS["border"], height=1).pack(fill="x")

        controls = tk.Frame(bottom, bg=COLORS["surface"])
        controls.pack(fill="x", padx=16, pady=12)

        # Impresora
        imp_row = tk.Frame(controls, bg=COLORS["surface"])
        imp_row.pack(fill="x", pady=(0, 10))

        tk.Label(imp_row, text="Impresora", font=FONT_SMALL,
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(side="left")

        impresoras = listar_impresoras()
        self._imp_var = tk.StringVar()

        if impresoras:
            imp_menu = tk.OptionMenu(imp_row, self._imp_var, *impresoras)
            imp_menu.config(
                bg=COLORS["surface2"], fg=COLORS["text"],
                activebackground=COLORS["accent"],
                activeforeground=COLORS["text"],
                highlightthickness=1,
                highlightbackground=COLORS["border"],
                relief="flat", font=FONT_LABEL, anchor="w",
                bd=0,
            )
            imp_menu["menu"].config(
                bg=COLORS["surface2"], fg=COLORS["text"],
                activebackground=COLORS["accent"],
                activeforeground=COLORS["text"],
                font=FONT_LABEL,
            )
            self._imp_var.set(impresoras[0])
            imp_menu.pack(side="left", padx=(8, 0))
        else:
            tk.Label(imp_row, text="Sin impresoras detectadas",
                     font=FONT_SMALL, bg=COLORS["surface"],
                     fg=COLORS["text_dim"]).pack(side="left", padx=(8, 0))
            self._imp_var.set("")

        # Botones
        btn_row = tk.Frame(controls, bg=COLORS["surface"])
        btn_row.pack(fill="x")

        btn_imprimir = tk.Button(
            btn_row, text="Imprimir",
            font=FONT_BOLD,
            bg=COLORS["accent"] if impresoras else COLORS["surface2"],
            fg=COLORS["text"] if impresoras else COLORS["text_dim"],
            activebackground=COLORS["accent_hover"],
            activeforeground=COLORS["text"],
            relief="flat", cursor="hand2" if impresoras else "arrow",
            state="normal" if impresoras else "disabled",
            command=self._imprimir,
        )
        btn_imprimir.pack(side="left", ipady=8, ipadx=16)
        if impresoras:
            _add_hover(btn_imprimir, COLORS["accent"], COLORS["accent_hover"])

        btn_guardar = tk.Button(
            btn_row, text="Guardar .txt",
            font=FONT_BOLD,
            bg=COLORS["surface2"], fg=COLORS["text"],
            activebackground=COLORS["border"],
            activeforeground=COLORS["text"],
            relief="flat", cursor="hand2",
            command=self._guardar,
        )
        btn_guardar.pack(side="left", padx=(8, 0), ipady=8, ipadx=16)
        _add_hover(btn_guardar, COLORS["surface2"], COLORS["border"])

        btn_cerrar = tk.Button(
            btn_row, text="Cerrar",
            font=FONT_SMALL,
            bg=COLORS["surface"], fg=COLORS["text_muted"],
            activebackground=COLORS["surface2"],
            activeforeground=COLORS["text"],
            relief="flat", cursor="hand2",
            command=self.destroy,
        )
        btn_cerrar.pack(side="right", ipady=6, ipadx=12)
        _add_hover(btn_cerrar, COLORS["surface"], COLORS["surface2"])

    def _imprimir(self):
        from modules.ticket import imprimir_ticket
        impresora = self._imp_var.get()
        if not impresora:
            messagebox.showwarning(
                "Sin impresora",
                "No se detectaron impresoras.\n"
                "La impresión directa requiere Windows con pywin32.",
                parent=self)
            return
        try:
            imprimir_ticket(self._texto, impresora)
            messagebox.showinfo("Impreso", "Ticket enviado a la impresora.", parent=self)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error al imprimir", str(e), parent=self)

    def _guardar(self):
        from modules.ticket import guardar_ticket
        ruta = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Texto", "*.txt")],
            initialfile="ticket.txt",
            parent=self,
        )
        if ruta:
            guardar_ticket(self._texto, ruta)
            messagebox.showinfo("Guardado", f"Ticket guardado en:\n{ruta}", parent=self)


def mostrar_ticket_venta(parent, venta_id: int):
    from modules.ticket import generar_ticket_venta
    try:
        texto = generar_ticket_venta(venta_id)
        DialogTicket(parent, texto, f"Ticket — Venta #{venta_id}")
    except Exception as e:
        messagebox.showerror("Error", str(e), parent=parent)


def mostrar_ticket_cuenta(parent, cuenta_id: int, venta_id: int = None):
    from modules.ticket import generar_ticket_cuenta
    try:
        texto = generar_ticket_cuenta(cuenta_id, venta_id)
        DialogTicket(parent, texto, f"Ticket — Mesa #{cuenta_id}")
    except Exception as e:
        messagebox.showerror("Error", str(e), parent=parent)


def mostrar_ticket_pedido(parent, pedido_id: int):
    from modules.ticket import generar_ticket_pedido
    try:
        texto = generar_ticket_pedido(pedido_id)
        DialogTicket(parent, texto, f"Ticket — Pedido #{pedido_id}")
    except Exception as e:
        messagebox.showerror("Error", str(e), parent=parent)
