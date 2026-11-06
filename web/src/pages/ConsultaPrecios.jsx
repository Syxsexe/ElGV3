import { useEffect, useState } from "react";
import { api } from "../api";
import { ErrorBanner } from "../components/Modal";
import { fmt, fmtCant } from "../format";

// Para el mostrador: buscar un artículo y ver su precio (y el stock en tienda).
export default function ConsultaPrecios() {
  const [q, setQ] = useState("");
  const [resultados, setResultados] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    // vigente: si el texto cambió antes de que llegue la respuesta, se ignora.
    let vigente = true;
    const t = setTimeout(() => {
      api.vendibles(q.trim())
        .then((r) => {
          if (!vigente) return;
          setError("");
          setResultados(r);
        })
        .catch((err) => vigente && setError(err.message));
    }, 200);
    return () => {
      vigente = false;
      clearTimeout(t);
    };
  }, [q]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h1 style={{ fontSize: 28 }}>Consulta de precios</h1>
      <input className="inp" autoFocus placeholder="Nombre o código de barras" value={q}
        onChange={(e) => setQ(e.target.value)} style={{ height: 48, fontSize: 16, maxWidth: 520 }} />
      <ErrorBanner mensaje={error} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 12 }}>
        {resultados.map((a) => {
          const bajo = a.categoria_tipo === "tienda" && a.tipo === "producto" && Number(a.stock) <= Number(a.stock_minimo);
          return (
            <div key={a.id} className="prod" style={{ cursor: "default" }}>
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                <strong style={{ fontSize: 15 }}>{a.nombre}</strong>
                <span className="muted" style={{ fontSize: 12 }}>{a.categoria}{a.codigo ? ` · ${a.codigo}` : ""}</span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "auto" }}>
                <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 22, fontWeight: 700 }}>
                  {fmt(a.precio_venta)}
                </span>
                {a.tipo === "producto" && a.categoria_tipo === "tienda" && (
                  <span className={`chip num ${bajo ? "bad" : "ok"}`}>Stock {fmtCant(a.stock)}</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {resultados.length === 0 && <div className="muted">Sin resultados.</div>}
    </div>
  );
}
