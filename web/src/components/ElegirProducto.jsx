import { useId, useMemo, useState } from "react";
import { fmt } from "../format";

// Buscar un producto en una lista ya cargada (sin ir al servidor) y elegirlo:
// por nombre o categoría, sin importar tildes ni mayúsculas. Teclado: flechas
// para moverse, Enter para elegir, Escape para cerrar.
//
// productos: [{id, nombre, categoria, activo, costo}]; excluir: Set de ids que
// ya están (no se ofrecen); onElegir(producto); onCerrar(): Escape o "Listo".
const normal = (t) => (t || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const MAX = 8;
const NINGUNO = new Set();

export default function ElegirProducto({ productos, excluir = NINGUNO, onElegir, onCerrar, etiqueta = "Buscar producto" }) {
  const [q, setQ] = useState("");
  const [activo, setActivo] = useState(0);
  const idLista = useId();

  // El texto normalizado de cada producto se calcula una vez por catálogo.
  const indice = useMemo(() => productos.map((p) => ({ p, texto: normal(`${p.nombre} ${p.categoria || ""}`), nombre: normal(p.nombre) })),
    [productos]);
  const { resultados, total } = useMemo(() => {
    const t = normal(q.trim());
    if (!t) return { resultados: [], total: 0 };
    const palabras = t.split(/\s+/);
    const todos = indice
      .filter((x) => x.p.activo && !excluir.has(x.p.id) && palabras.every((w) => x.texto.includes(w)))
      // Primero los que empiezan con lo escrito.
      .sort((a, b) => Number(!a.nombre.startsWith(t)) - Number(!b.nombre.startsWith(t)) || a.p.nombre.localeCompare(b.p.nombre, "es"));
    return { resultados: todos.slice(0, MAX).map((x) => x.p), total: todos.length };
  }, [q, indice, excluir]);
  // Si la lista se achica (se eligió uno, o se escribió más), el resaltado no se sale.
  const resaltado = Math.min(activo, Math.max(resultados.length - 1, 0));

  const elegir = (p) => {
    onElegir(p);
    setQ("");
    setActivo(0);
  };
  const tecla = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setActivo(Math.min(resaltado + 1, Math.max(resultados.length - 1, 0))); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActivo(Math.max(resaltado - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); if (resultados[resaltado]) elegir(resultados[resaltado]); }
    else if (e.key === "Escape" && onCerrar) { e.preventDefault(); e.stopPropagation(); onCerrar(); }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", gap: 8 }}>
        <input className="inp" autoFocus aria-label={etiqueta} placeholder="Escribe parte del nombre o la categoría…"
          role="combobox" aria-expanded={resultados.length > 0} aria-controls={idLista}
          aria-activedescendant={resultados[resaltado] ? `${idLista}-${resultados[resaltado].id}` : undefined}
          value={q} onChange={(e) => { setQ(e.target.value); setActivo(0); }} onKeyDown={tecla} style={{ flexGrow: 1, minWidth: 0 }} />
        {onCerrar && <button type="button" className="btn btn-s" onClick={onCerrar}>Listo</button>}
      </div>
      {q.trim() && (
        <div id={idLista} role="listbox" aria-label="Resultados" className="card" style={{ maxHeight: 280, overflowY: "auto" }}>
          {resultados.length === 0 && <div className="muted" style={{ padding: "10px 14px", fontSize: 14 }}>Ningún producto activo coincide.</div>}
          {resultados.map((p, i) => (
            <button key={p.id} id={`${idLista}-${p.id}`} type="button" role="option" aria-selected={i === resaltado}
              onMouseEnter={() => setActivo(i)} onClick={() => elegir(p)}
              style={{
                width: "100%", border: 0, borderBottom: "1px solid var(--border-2)", textAlign: "left", fontFamily: "inherit",
                color: "inherit", cursor: "pointer", padding: "9px 14px", display: "flex", justifyContent: "space-between", gap: 10,
                background: i === resaltado ? "var(--accent-soft)" : "#fff",
              }}>
              <span style={{ minWidth: 0, display: "flex", flexDirection: "column" }}>
                <span style={{ fontSize: 14, fontWeight: 600, overflowWrap: "break-word" }}>{p.nombre}</span>
                {p.categoria && <span className="muted" style={{ fontSize: 12 }}>{p.categoria}</span>}
              </span>
              <span className="muted num" style={{ fontSize: 12, whiteSpace: "nowrap" }}>costo {fmt(p.costo || 0)}</span>
            </button>
          ))}
          {total > resultados.length && (
            <div className="muted" style={{ padding: "8px 14px", fontSize: 13 }}>
              Y {total - resultados.length} más: escribe más letras para encontrarlo.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
