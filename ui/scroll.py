"""
ui/scroll.py — El G POS
Helper para que la rueda del mouse controle un Canvas concreto SOLO mientras el
puntero está sobre una región dada, sin pelear con el scroll global de main.py.

Usa exclusivamente <Enter> (nunca <Leave>): al entrar a la región, la rueda pasa
a controlar ese canvas; cuando el puntero vuelve al área de contenido, main.py
reclama la rueda con su propio <Enter>. Así se evita el parpadeo por los eventos
de cruce (crossing) entre un contenedor y sus hijos, y se evita el `bind_all`
permanente en construcción que rompía el scroll del resto de la app.
"""


def rueda_al_entrar(canvas, *regiones):
    """Activa el scroll por rueda de `canvas` al entrar el puntero a `regiones`."""
    def _wheel(event):
        if event.num == 4:
            canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            canvas.yview_scroll(1, "units")
        else:
            canvas.yview_scroll(int(-event.delta / 120), "units")

    def _activar(event=None):
        canvas.bind_all("<MouseWheel>", _wheel)
        canvas.bind_all("<Button-4>", _wheel)
        canvas.bind_all("<Button-5>", _wheel)

    for w in regiones:
        w.bind("<Enter>", _activar)
