import { useEffect, useState } from "react";
import { api } from "../api";
import { fmt } from "../format";
import Modal, { ErrorBanner } from "./Modal";

// Ventana para marcar los toppings de un plato antes de agregarlo (ninguno,
// uno o varios; una vez cada uno). onElegir recibe null si no se marcó nada,
// o {toppings: [adicional_id], recargo, texto, firma}: firma identifica lo
// marcado (para juntar líneas iguales); texto es "con Huevo duro, Queso".
export default function ElegirToppings({ plato, onElegir, onClose }) {
  const [datos, setDatos] = useState(null);
  const [marcados, setMarcados] = useState(() => new Set());
  const [error, setError] = useState("");

  useEffect(() => {
    let vigente = true;
    api.toppingsPlato(plato.id).then((d) => vigente && setDatos(d)).catch((err) => vigente && setError(err.message));
    return () => { vigente = false; };
  }, [plato.id]);

  if (!datos) {
    return <Modal titulo={plato.nombre} onClose={onClose}>{error ? <ErrorBanner mensaje={error} /> : <div className="muted">Cargando…</div>}</Modal>;
  }

  const elegidos = datos.toppings.filter((t) => marcados.has(t.adicional_id));
  const recargo = elegidos.reduce((s, t) => s + Number(t.precio), 0);
  const cambiar = (id) => setMarcados((m) => {
    const n = new Set(m);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });
  const agregar = (e) => {
    e.preventDefault();
    if (!elegidos.length) {
      onElegir(null);
      return;
    }
    const ids = elegidos.map((t) => t.adicional_id);
    onElegir({
      toppings: ids, recargo, texto: `con ${elegidos.map((t) => t.nombre).join(", ")}`,
      firma: [...ids].sort().join("|"),
    });
  };

  return (
    <Modal titulo={datos.nombre} onClose={onClose} ancho={520}>
      <form onSubmit={agregar} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div role="group" aria-label="Toppings" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span className="lbl">Toppings <span className="muted">· opcionales, marca los que quiera</span></span>
          {datos.toppings.length === 0 && <span className="muted" style={{ fontSize: 14 }}>Este plato no tiene toppings disponibles ahora.</span>}
          <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))" }}>
            {datos.toppings.map((t) => {
              const activo = marcados.has(t.adicional_id);
              return (
                <button key={t.adicional_id} type="button" role="checkbox" aria-checked={activo} onClick={() => cambiar(t.adicional_id)}
                  className={`mesa${activo ? " on" : ""}`} style={{ padding: activo ? 11 : 12, gap: 6, minHeight: 72 }}>
                  <span style={{ display: "flex", justifyContent: "space-between", gap: 6, width: "100%", alignItems: "flex-start" }}>
                    <span style={{ fontSize: 14, fontWeight: 600, overflowWrap: "break-word", minWidth: 0 }}>{t.nombre}</span>
                    <span aria-hidden="true" style={{
                      width: 20, height: 20, borderRadius: 6, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
                      border: `2px solid ${activo ? "var(--accent)" : "var(--border-input)"}`, background: activo ? "var(--accent)" : "#fff",
                    }}>
                      {activo && <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>}
                    </span>
                  </span>
                  <span className="num" style={{ fontSize: 13, color: "var(--accent-hover)", fontWeight: 600 }}>+ {fmt(t.precio)}</span>
                </button>
              );
            })}
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", flexWrap: "wrap" }}>
          <button type="button" className="btn btn-s" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-p">
            {elegidos.length ? `Agregar con ${elegidos.length} · ${fmt(Number(datos.precio_venta) + recargo)}` : `Agregar sin toppings · ${fmt(datos.precio_venta)}`}
          </button>
        </div>
      </form>
    </Modal>
  );
}
