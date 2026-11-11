import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { fmt, fmtCant } from "../format";
import { useIsMobile } from "../useMediaQuery";
import { ErrorBanner } from "./Modal";

const PESTANAS = [
  ["todo", "Todo", {}],
  ["tienda", "Tienda", { tipo: "producto", categoria_tipo: "tienda" }],
  ["cocina", "Cocina", { tipo: "producto", categoria_tipo: "cocina" }],
  ["combo", "Combos", { tipo: "combo" }],
  ["adicional", "Extras", { tipo: "adicional" }],
];

const esTienda = (a) => a.tipo === "producto" && a.categoria_tipo === "tienda";
const agotado = (a) => esTienda(a) && Number(a.stock) <= 0;

// Artículos para tocar y agregar (venta directa y consumos de una cuenta).
// cantidades: {articulo_id: n} para marcar lo ya agregado. version: cambiarla
// vuelve a pedir el catálogo (ej. el stock después de vender). onCargados
// recibe cada lista que llega (precios al día). Enter en la búsqueda agrega
// el artículo con ese código, o el único resultado: así funciona el lector
// de códigos, que escribe y da Enter antes de que llegue la búsqueda.
export default function Catalogo({ onElegir, onCargados, cantidades = {}, version = 0, autoFocus = false }) {
  const isMobile = useIsMobile();
  const [pestana, setPestana] = useState("todo");
  const [q, setQ] = useState("");
  const [articulos, setArticulos] = useState([]);
  const [error, setError] = useState("");
  // En una ref: el padre pasa una función nueva en cada render y eso no debe
  // volver a disparar la búsqueda.
  const cargados = useRef(onCargados);
  useEffect(() => { cargados.current = onCargados; });

  useEffect(() => {
    let vigente = true;
    const filtros = { ...PESTANAS.find(([k]) => k === pestana)[2], limite: 200 };
    const t = setTimeout(() => {
      api.vendibles(q.trim(), undefined, filtros)
        .then((r) => {
          if (!vigente) return;
          setError("");
          setArticulos(r);
          cargados.current?.(r);
        })
        .catch((err) => vigente && setError(err.message));
    }, 200);
    return () => {
      vigente = false;
      clearTimeout(t);
    };
  }, [pestana, q, version]);

  // Busca de nuevo con el texto exacto: la lista en pantalla puede ser la de
  // una búsqueda anterior.
  const alEnter = (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    const texto = q.trim();
    if (!texto) return;
    api.vendibles(texto, undefined, { limite: 200 })
      .then((r) => {
        const elegido = r.find((a) => a.codigo === texto) || (r.length === 1 ? r[0] : null);
        if (elegido && agotado(elegido)) {
          setError(`${elegido.nombre} está agotado: no hay stock para venderlo.`);
        } else if (elegido) {
          onElegir(elegido);
          setQ((actual) => (actual.trim() === texto ? "" : actual));
        } else {
          setError(r.length ? `Varios artículos coinciden con "${texto}": tócalo en la lista.` : `No hay artículos con "${texto}".`);
        }
      })
      .catch((err) => setError(err.message));
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <input className="inp" type="search" aria-label="Buscar artículo" placeholder="Buscar por nombre o código"
          autoFocus={autoFocus && !isMobile} value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={alEnter}
          style={{ flex: "1 1 220px", minWidth: 0 }} />
        <div className="seg" role="tablist" aria-label="Tipo de artículo" style={{ maxWidth: "100%", overflowX: "auto" }}>
          {PESTANAS.map(([k, etiqueta]) => (
            <button key={k} type="button" role="tab" aria-selected={pestana === k} className={pestana === k ? "on" : ""}
              onClick={() => setPestana(k)}>{etiqueta}</button>
          ))}
        </div>
      </div>
      <ErrorBanner mensaje={error} />
      <div style={{
        display: "grid", gap: 10, alignContent: "start",
        gridTemplateColumns: isMobile ? "repeat(2, minmax(0, 1fr))" : "repeat(auto-fill, minmax(170px, 1fr))",
      }}>
        {articulos.map((a) => {
          const n = cantidades[a.id] || 0;
          const bajo = esTienda(a) && Number(a.stock) <= Number(a.stock_minimo);
          const sinStock = agotado(a);
          return (
            <button key={a.id} type="button" className="prod" onClick={() => onElegir(a)} disabled={sinStock}
              aria-label={sinStock ? `${a.nombre}, agotado` : `Agregar ${a.nombre}`}>
              {n > 0 && <span className="qty num">{fmtCant(n)}</span>}
              <span style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3, paddingRight: n > 0 ? 26 : 0, overflowWrap: "anywhere" }}>
                {a.nombre}
              </span>
              <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6, marginTop: "auto", flexWrap: "wrap" }}>
                <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 17, fontWeight: 700, color: "var(--accent-hover)", whiteSpace: "nowrap" }}>
                  {fmt(a.precio_venta)}
                </span>
                {sinStock ? <span className="chip bad">Agotado</span>
                  : esTienda(a) ? <span className={`chip num ${bajo ? "warn" : "neu"}`}>{fmtCant(a.stock)}</span>
                  : a.alcanza != null && (
                    // Un plato no se frena: si sus insumos no alcanzan se vende igual y se avisa.
                    <span className={`chip num ${Number(a.alcanza) === 0 ? "bad" : Number(a.alcanza) <= 3 ? "warn" : "neu"}`}
                      title="Platos que alcanzan con el stock de sus ingredientes">
                      {Number(a.alcanza) === 0 ? "Sin insumos" : `Alcanza ${fmtCant(a.alcanza)}`}
                    </span>
                  )}
              </span>
            </button>
          );
        })}
      </div>
      {articulos.length === 0 && !error && <div className="muted">Sin resultados.</div>}
    </div>
  );
}
