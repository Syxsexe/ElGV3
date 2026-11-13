import { useEffect, useState } from "react";
import { api } from "../api";
import { fmt } from "../format";
import Modal, { ErrorBanner } from "./Modal";

// Ventana para marcar los toppings de un plato antes de agregarlo (ninguno,
// uno o varios; una vez cada uno). onElegir recibe null si no se marcó nada,
// o {toppings: [adicional_id], recargo, texto, firma}: firma identifica lo
// marcado (para juntar líneas iguales); texto es "con Huevo duro, Queso".
// Si el plato trae toppings incluidos, van sin costo los más baratos de los
// marcados (a igual precio, el orden del plato), igual que en el servidor.
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
  const incluidos = datos.toppings_incluidos || 0;
  // Los incluidos de una selección (en el orden del plato) y lo que se cobra.
  const sinCostoDe = (lista) => new Set(lista.map((t, i) => [t, i])
    .sort((a, b) => Number(a[0].precio) - Number(b[0].precio) || a[1] - b[1])
    .slice(0, incluidos).map(([t]) => t.adicional_id));
  const cobrado = (lista) => {
    const sinCosto = sinCostoDe(lista);
    return lista.reduce((s, t) => s + (sinCosto.has(t.adicional_id) ? 0 : Number(t.precio)), 0);
  };
  const gratis = sinCostoDe(elegidos);
  const recargo = cobrado(elegidos);
  // Cuánto sube el total si se marca uno más (puede desplazar a un incluido).
  const extraSi = (t) => cobrado(datos.toppings.filter((x) => marcados.has(x.adicional_id) || x.adicional_id === t.adicional_id)) - recargo;
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
          <span className="lbl">Toppings <span className="muted">
            · {incluidos > 0 ? `${incluidos === 1 ? "1 incluido" : `${incluidos} incluidos`}; de más se cobran los más caros` : "opcionales, marca los que quiera"}
          </span></span>
          {datos.toppings.length === 0 && <span className="muted" style={{ fontSize: 14 }}>Este plato no tiene toppings disponibles ahora.</span>}
          <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))" }}>
            {datos.toppings.map((t) => {
              const activo = marcados.has(t.adicional_id);
              // Marcado: incluido o con su precio. Sin marcar: lo que sumaría marcarlo.
              const extra = activo ? (gratis.has(t.adicional_id) ? 0 : Number(t.precio)) : extraSi(t);
              const sinCosto = extra === 0;
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
                  <span className="num" style={{ fontSize: 13, color: sinCosto ? "var(--ok-text)" : "var(--accent-hover)", fontWeight: 600 }}>
                    {sinCosto ? <><s style={{ fontWeight: 400, color: "var(--text-muted)" }}>{fmt(t.precio)}</s> Incluido</> : `+ ${fmt(extra)}`}
                  </span>
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
