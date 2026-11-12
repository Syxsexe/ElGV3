import { useEffect, useState } from "react";
import { api } from "../api";
import { fmt, fmtCant } from "../format";
import Modal, { ErrorBanner } from "./Modal";

// Cuántas unidades hay de una opción: el stock en la tienda, los platos que
// alcanzan en la cocina; null = sin límite.
const disponibles = (o) => (o.disponibles == null ? null : Number(o.disponibles));
// Lo de tienda se exige al cobrar: sin stock para un combo, no se ofrece.
// La cocina vende y avisa (como los platos sueltos).
const alcanzaPara = (o, grupo) => o.categoria_tipo !== "tienda" || disponibles(o) >= Number(grupo.cantidad);

// "Coca-Cola, 2 × Papas" a partir de lo elegido.
function textoElecciones(grupos, elegido) {
  return grupos.map((g) => {
    const o = g.opciones.find((x) => x.producto_id === elegido[g.id]);
    if (!o) return "";
    return Number(g.cantidad) === 1 ? o.nombre : `${fmtCant(g.cantidad)} × ${o.nombre}`;
  }).filter(Boolean).join(", ");
}

// Ventana para elegir una opción de cada grupo de un combo (ej. la bebida)
// antes de agregarlo. onElegir recibe {elecciones: [{grupo_id, producto_id}],
// recargo, texto, firma}: firma identifica lo elegido (para juntar líneas iguales).
export default function ElegirCombo({ combo, onElegir, onClose }) {
  const [datos, setDatos] = useState(null);
  const [elegido, setElegido] = useState({});
  const [error, setError] = useState("");

  useEffect(() => {
    let vigente = true;
    api.opcionesCombo(combo.id).then((d) => {
      if (!vigente) return;
      setDatos(d);
      // Un grupo con una sola opción posible queda elegido de una vez.
      const inicial = {};
      for (const g of d.grupos) {
        const posibles = g.opciones.filter((o) => alcanzaPara(o, g));
        if (posibles.length === 1) inicial[g.id] = posibles[0].producto_id;
      }
      setElegido(inicial);
    }).catch((err) => vigente && setError(err.message));
    return () => { vigente = false; };
  }, [combo.id]);

  if (!datos) {
    return <Modal titulo={combo.nombre} onClose={onClose}>{error ? <ErrorBanner mensaje={error} /> : <div className="muted">Cargando…</div>}</Modal>;
  }

  const recargo = datos.grupos.reduce((s, g) => {
    const o = g.opciones.find((x) => x.producto_id === elegido[g.id]);
    return s + Number(o?.recargo || 0);
  }, 0);
  const faltan = datos.grupos.filter((g) => !elegido[g.id]);
  const precio = Number(datos.precio_venta) + recargo;

  const agregar = (e) => {
    e.preventDefault();
    if (faltan.length) return;
    const elecciones = datos.grupos.map((g) => ({ grupo_id: g.id, producto_id: elegido[g.id] }));
    onElegir({
      elecciones, recargo, texto: textoElecciones(datos.grupos, elegido),
      firma: elecciones.map((x) => `${x.grupo_id}:${x.producto_id}`).join("|"),
    });
  };

  return (
    <Modal titulo={datos.nombre} onClose={onClose} ancho={520}>
      <form onSubmit={agregar} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {datos.grupos.map((g) => (
          <div key={g.id} role="radiogroup" aria-label={g.nombre} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <span className="lbl">
              {g.nombre}{Number(g.cantidad) !== 1 && <span className="muted"> · {fmtCant(g.cantidad)} unidades</span>}
            </span>
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))" }}>
              {g.opciones.map((o) => {
                const activa = elegido[g.id] === o.producto_id;
                const hay = disponibles(o);
                const puede = alcanzaPara(o, g);
                return (
                  <button key={o.producto_id} type="button" role="radio" aria-checked={activa} className="prod"
                    disabled={!puede} onClick={() => setElegido((x) => ({ ...x, [g.id]: o.producto_id }))}
                    style={{ minHeight: 72, ...(activa ? { borderColor: "var(--accent)", boxShadow: "0 0 0 2px var(--accent)" } : {}) }}>
                    <span style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3, overflowWrap: "anywhere" }}>{o.nombre}</span>
                    <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6, marginTop: "auto", flexWrap: "wrap" }}>
                      <span className="num" style={{ fontSize: 13, fontWeight: 700, color: "var(--accent-hover)" }}>
                        {Number(o.recargo) > 0 ? `+ ${fmt(o.recargo)}` : ""}
                      </span>
                      {!puede ? <span className="chip bad">Agotado</span>
                        : hay != null && (
                          <span className={`chip num ${hay <= 3 ? "warn" : "neu"}`}
                            title={o.categoria_tipo === "tienda" ? "Unidades en stock" : "Platos que alcanzan con sus ingredientes"}>
                            {o.categoria_tipo === "tienda" ? fmtCant(hay) : hay === 0 ? "Sin insumos" : `Alcanza ${fmtCant(hay)}`}
                          </span>
                        )}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", alignItems: "center", flexWrap: "wrap" }}>
          {faltan.length > 0 && <span className="muted" style={{ fontSize: 13, marginRight: "auto" }}>Elige {faltan.map((g) => g.nombre).join(", ")}.</span>}
          <button type="button" className="btn btn-s" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-p" disabled={faltan.length > 0}>Agregar {fmt(precio)}</button>
        </div>
      </form>
    </Modal>
  );
}
