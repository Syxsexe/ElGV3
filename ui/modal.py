"""
ui/modal.py — El G POS
Ventana modal reutilizable para formularios.

Pensada para pantallas de BAJA RESOLUCIÓN (1366x768):
  • El cuerpo es scrollable y se limita a un porcentaje del alto de la pantalla,
    así el formulario nunca se sale de la pantalla.
  • El pie con los botones de acción (Guardar/Cancelar) es FIJO: siempre visible
    abajo, aunque el cuerpo tenga scroll.

Uso típico:
    m = ModalForm(self, "Nuevo producto", ancho=440)
    # ... construir campos dentro de m.body (bg = surface) ...
    # ... botones dentro de m.footer ...
    m.mostrar()
"""
import tkinter as tk

from ui.base import COLORS, FONT_BOLD


class ModalForm(tk.Toplevel):
    def __init__(self, parent, titulo, ancho=440, alto_max_frac=0.9):
        super().__init__(parent.winfo_toplevel(), bg=COLORS["surface"])
        self.withdraw()  # ocultar mientras se arma (evita parpadeo)
        self._parent = parent.winfo_toplevel()
        self._ancho = ancho
        self._alto_max_frac = alto_max_frac

        self.title(titulo)
        self.transient(self._parent)
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.cerrar)

        # ── Encabezado ─────────────────────────────────────────────────────
        head = tk.Frame(self, bg=COLORS["surface"])
        head.pack(fill="x", padx=20, pady=(16, 10))
        tk.Label(head, text=titulo, font=("Segoe UI", 14, "bold"),
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(side="left")
        tk.Button(head, text="✕", font=FONT_BOLD, bg=COLORS["surface"],
                  fg=COLORS["text_muted"], activebackground=COLORS["surface"],
                  activeforeground=COLORS["text"], relief="flat", bd=0,
                  cursor="hand2", command=self.cerrar).pack(side="right")

        tk.Frame(self, bg=COLORS["border"], height=1).pack(fill="x")

        # ── Cuerpo scrollable ──────────────────────────────────────────────
        cuerpo = tk.Frame(self, bg=COLORS["surface"])
        cuerpo.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(cuerpo, bg=COLORS["surface"],
                                 highlightthickness=0, bd=0)
        self._sb = tk.Scrollbar(cuerpo, orient="vertical",
                                command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._sb.set)
        self._canvas.pack(side="left", fill="both", expand=True)

        self.body = tk.Frame(self._canvas, bg=COLORS["surface"])
        self._body_win = self._canvas.create_window(
            (0, 0), window=self.body, anchor="nw")
        self._canvas.bind(
            "<Configure>",
            lambda e: self._canvas.itemconfig(self._body_win, width=e.width))
        self.body.bind("<Configure>", self._on_body_config)

        # ── Pie fijo (botones) ─────────────────────────────────────────────
        tk.Frame(self, bg=COLORS["border"], height=1).pack(fill="x")
        self.footer = tk.Frame(self, bg=COLORS["surface"])
        self.footer.pack(fill="x", padx=20, pady=12)

        # Rueda del mouse: el Toplevel está en los bindtags de todos sus hijos,
        # así que este bind captura la rueda dentro del modal SIN usar bind_all
        # (no contamina el scroll del resto de la app y se limpia al destruir).
        self.bind("<MouseWheel>", self._rueda)
        self.bind("<Button-4>", self._rueda)
        self.bind("<Button-5>", self._rueda)
        self.bind("<Escape>", lambda e: self.cerrar())

    # ── Scroll / geometría ─────────────────────────────────────────────────

    def _rueda(self, event):
        if getattr(self, "_scroll_activo", False) is False:
            return
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        else:
            self._canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_body_config(self, event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._ajustar_geometria()

    def _ajustar_geometria(self):
        self.update_idletasks()
        body_h = self.body.winfo_reqheight()
        # Cromo = todo menos el canvas (encabezado + divisores + pie).
        chrome = self.winfo_reqheight() - self._canvas.winfo_reqheight()
        alto_max = int(self.winfo_screenheight() * self._alto_max_frac)
        disponible = max(alto_max - chrome, 160)
        canvas_h = min(body_h, disponible)
        self._canvas.configure(height=canvas_h, width=self._ancho)
        self._scroll_activo = body_h > canvas_h + 1
        if self._scroll_activo:
            self._sb.pack(side="right", fill="y", before=self._canvas)
        else:
            self._sb.pack_forget()

    def _centrar(self):
        self.update_idletasks()
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        px, py = self._parent.winfo_rootx(), self._parent.winfo_rooty()
        pw, ph = self._parent.winfo_width(), self._parent.winfo_height()
        x = px + max((pw - w) // 2, 0)
        y = py + max((ph - h) // 2, 0)
        # No dejar que se salga por arriba de la pantalla.
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    # ── API ─────────────────────────────────────────────────────────────────

    def mostrar(self):
        self._ajustar_geometria()
        self._centrar()
        self.deiconify()
        self.grab_set()
        self.focus_set()

    def cerrar(self):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
