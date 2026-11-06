import { useEffect, useState } from "react";
import { api } from "../api";
import { documento } from "../format";

// Elegir un tercero existente (por nombre o documento). rol opcional.
export default function BuscarTercero({ rol, onElegir, placeholder = "Buscar persona por nombre o documento" }) {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState([]);

  useEffect(() => {
    if (q.trim().length < 2) return undefined;
    let vigente = true;
    const t = setTimeout(() => api.terceros({ rol, q: q.trim(), limite: 15 })
      .then((r) => vigente && setResultados(r)).catch(() => {}), 250);
    return () => {
      vigente = false;
      clearTimeout(t);
    };
  }, [q, rol]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <input className="inp" placeholder={placeholder} value={q} onChange={(e) => setQ(e.target.value)} />
      {q.trim().length >= 2 && resultados.length > 0 && (
        <div className="card" style={{ maxHeight: 200, overflowY: "auto" }}>
          {resultados.map((t) => (
            <button key={t.id} type="button" className="tr" onClick={() => { onElegir(t); setQ(""); setResultados([]); }}
              style={{ width: "100%", background: "none", border: 0, textAlign: "left", cursor: "pointer", gridTemplateColumns: "1fr auto" }}>
              <span>{t.nombre}</span>
              <span className="muted num">{documento(t)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
