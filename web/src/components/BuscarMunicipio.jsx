import { useEffect, useState } from "react";
import { api } from "../api";

// Buscador de municipios DIVIPOLA (por nombre sin tildes o por código).
export default function BuscarMunicipio({ id, actual, onElegir }) {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState([]);

  useEffect(() => {
    if (q.trim().length < 2) return undefined;
    let vigente = true; // una respuesta de un texto anterior se ignora
    const t = setTimeout(() => api.municipios(q).then((r) => vigente && setResultados(r)).catch(() => {}), 250);
    return () => {
      vigente = false;
      clearTimeout(t);
    };
  }, [q]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <input id={id} className="inp" placeholder={actual || "Escribe para buscar…"} value={q} onChange={(e) => setQ(e.target.value)} />
      {q.trim().length >= 2 && resultados.length > 0 && (
        <div className="card" style={{ maxHeight: 200, overflowY: "auto" }}>
          {resultados.map((m) => (
            <button key={m.id} type="button" className="tr" onClick={() => { onElegir(m); setQ(""); setResultados([]); }}
              style={{ width: "100%", background: "none", border: 0, textAlign: "left", cursor: "pointer", gridTemplateColumns: "1fr auto" }}>
              <span>{m.nombre} <span className="muted">({m.departamento})</span></span>
              <span className="muted num">{m.codigo}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
