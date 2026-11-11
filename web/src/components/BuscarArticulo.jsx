import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { fmt } from "../format";

// Buscar un artículo vendible y elegirlo de una lista desplegable.
// tipo / filtros: los de api.vendibles (ej. tipo "producto", {categoria_tipo: "tienda"}).
// derecha(a): lo que se muestra a la derecha de cada resultado (por defecto, el precio).
// buscar(q): otra fuente de resultados en vez de api.vendibles (ej. premios con costo).
export default function BuscarArticulo({ onElegir, tipo, filtros, etiqueta, placeholder, derecha = (a) => fmt(a.precio_venta), buscar }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const ultima = useRef(0);
  const clave = JSON.stringify(filtros ?? {}); // los filtros llegan como objeto nuevo en cada render
  const fuente = useRef(buscar);
  useEffect(() => { fuente.current = buscar; }, [buscar]);

  useEffect(() => {
    if (q.trim().length < 2) return undefined;
    const mia = ++ultima.current; // una respuesta de una búsqueda anterior se descarta
    const t = setTimeout(() => (fuente.current ? fuente.current(q.trim()) : api.vendibles(q.trim(), tipo, JSON.parse(clave)))
      .then((r) => mia === ultima.current && setItems(r)).catch(() => {}), 200);
    return () => clearTimeout(t);
  }, [q, tipo, clave]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, flexGrow: 1 }}>
      <input className="inp" aria-label={etiqueta} placeholder={placeholder} value={q} onChange={(e) => setQ(e.target.value)} />
      {q.trim().length >= 2 && items.length > 0 && (
        <div className="card" style={{ maxHeight: 200, overflowY: "auto" }}>
          {items.map((a) => (
            <button key={a.id} type="button" onClick={() => { onElegir(a); setQ(""); setItems([]); }}
              style={{ width: "100%", border: 0, borderBottom: "1px solid var(--border-2)", background: "#fff", textAlign: "left",
                font: "inherit", color: "inherit", cursor: "pointer", padding: "10px 14px", display: "flex", justifyContent: "space-between", gap: 10 }}>
              <span style={{ overflowWrap: "anywhere" }}>{a.nombre}</span>
              <span className="muted num" style={{ whiteSpace: "nowrap" }}>{derecha(a)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
