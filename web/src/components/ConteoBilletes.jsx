import { totalConteo } from "../conteo";
import { fmt } from "../format";

const GRANDE = { fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontWeight: 700 };

function Grupo({ titulo, denominaciones, cantidades, cambiar }) {
  if (denominaciones.length === 0) return null;
  const subtotal = totalConteo(denominaciones, cantidades);
  return (
    <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", paddingBottom: 6, borderBottom: "1px solid var(--border)" }}>
        <span className="lbl">{titulo}</span>
        <span className="num muted" style={{ fontSize: 13 }}>{fmt(subtotal)}</span>
      </div>
      {denominaciones.map((d) => {
        const n = cantidades[d.id] || 0;
        return (
          <div key={d.id} style={{
            display: "grid", gridTemplateColumns: "minmax(64px, 1fr) auto minmax(70px, 1fr)", alignItems: "center", gap: 8,
            padding: "6px 0", borderBottom: "1px solid var(--border-2)",
          }}>
            <span className="num" style={{ fontWeight: 600, fontSize: 15, whiteSpace: "nowrap" }}>{fmt(d.valor)}</span>
            <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <button type="button" className="step" aria-label={`Quitar uno de ${fmt(d.valor)}`} onClick={() => cambiar(d.id, n - 1)} disabled={n === 0}>−</button>
              <input className="inp num" type="number" min="0" inputMode="numeric" aria-label={`Cantidad de ${fmt(d.valor)}`}
                value={n || ""} placeholder="0" onChange={(e) => cambiar(d.id, e.target.value)}
                style={{ width: 60, height: 34, padding: "0 6px", textAlign: "center" }} />
              <button type="button" className="step" aria-label={`Agregar uno de ${fmt(d.valor)}`} onClick={() => cambiar(d.id, n + 1)}>+</button>
            </span>
            <span className={`num${n ? "" : " muted"}`} style={{ textAlign: "right", fontSize: 14, whiteSpace: "nowrap", fontWeight: n ? 600 : 400 }}>
              {fmt(d.valor * n)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

// Conteo de billetes y monedas: un renglón por denominación con su subtotal,
// billetes y monedas en grupos aparte (lado a lado en pantallas anchas).
export default function ConteoBilletes({ titulo = "Conteo de billetes y monedas", denominaciones, cantidades, setCantidades, pie }) {
  const cambiar = (id, valor) => setCantidades((c) => ({ ...c, [id]: Math.max(0, Math.floor(Number(valor) || 0)) }));
  const billetes = denominaciones.filter((d) => d.tipo === "billete");
  const monedas = denominaciones.filter((d) => d.tipo !== "billete");
  const total = totalConteo(denominaciones, cantidades);
  const hayAlgo = Object.values(cantidades).some((n) => n > 0);
  return (
    <div className="card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14, minWidth: 0 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <h2 style={{ fontSize: 18 }}>{titulo}</h2>
        {hayAlgo && <button type="button" className="btn btn-g" style={{ height: 30, fontSize: 13 }} onClick={() => setCantidades({})}>Borrar conteo</button>}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 255px), 1fr))", columnGap: 24, rowGap: 16, alignItems: "start" }}>
        <Grupo titulo="Billetes" denominaciones={billetes} cantidades={cantidades} cambiar={cambiar} />
        <Grupo titulo="Monedas" denominaciones={monedas} cantidades={cantidades} cambiar={cambiar} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 10, padding: "12px 14px", borderRadius: 12, background: "var(--surface-2)", border: "1px solid var(--border-2)" }}>
        <span style={{ fontWeight: 600 }}>Total contado</span>
        <span className="num" style={{ ...GRANDE, fontSize: 26 }}>{fmt(total)}</span>
      </div>
      {pie}
    </div>
  );
}
