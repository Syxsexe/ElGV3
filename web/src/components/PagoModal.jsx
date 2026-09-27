import { useState } from "react";

const METODOS = [
  ["efectivo", "Efectivo"],
  ["tarjeta", "Tarjeta"],
  ["nequi", "Nequi"],
  ["daviplata", "Daviplata"],
  ["transferencia", "Transferencia"],
  ["mixto", "Mixto"],
];

const fmt = (n) => "$ " + Math.round(n).toLocaleString("es-CO");

export default function PagoModal({ total, onConfirm, onCancel }) {
  const [modo, setModo] = useState("efectivo");
  const [lineas, setLineas] = useState([]);
  const [nuevoMetodo, setNuevoMetodo] = useState("efectivo");
  const [nuevoMonto, setNuevoMonto] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const pagado = lineas.reduce((a, l) => a + l.monto, 0);
  const pendiente = Math.max(0, total - pagado);

  const agregarLinea = () => {
    const monto = Number(nuevoMonto);
    if (!monto || monto <= 0) return;
    setLineas((ls) => [...ls, { metodo: nuevoMetodo, monto: Math.min(monto, pendiente) || monto }]);
    setNuevoMonto("");
  };

  const quitarLinea = (i) => setLineas((ls) => ls.filter((_, idx) => idx !== i));

  const confirmar = async () => {
    setError("");
    setEnviando(true);
    try {
      const pagos = modo === "mixto" ? lineas : [{ metodo: modo, monto: total }];
      await onConfirm(pagos);
    } catch (err) {
      setError(err.message || "No se pudo procesar el cobro.");
    } finally {
      setEnviando(false);
    }
  };

  const puedeConfirmar = modo === "mixto" ? pagado >= total && lineas.length > 0 : true;

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(42,38,34,.45)", display: "flex",
      alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16,
    }}>
      <div className="card" style={{ width: 420, maxWidth: "100%", padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <h2 style={{ fontSize: 22 }}>Cobrar</h2>
          <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 26, fontWeight: 700 }}>
            {fmt(total)}
          </span>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
          {METODOS.map(([k, label]) => (
            <button key={k} type="button" className={`pay${modo === k ? " on" : ""}`} onClick={() => setModo(k)}>
              {label}
            </button>
          ))}
        </div>

        {modo === "mixto" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            <div style={{ display: "flex", gap: 8 }}>
              <select className="inp" style={{ width: 140 }} value={nuevoMetodo} onChange={(e) => setNuevoMetodo(e.target.value)}>
                {METODOS.filter(([k]) => k !== "mixto").map(([k, label]) => (
                  <option key={k} value={k}>{label}</option>
                ))}
              </select>
              <input className="inp num" type="number" placeholder="Monto" value={nuevoMonto}
                onChange={(e) => setNuevoMonto(e.target.value)} />
              <button type="button" className="btn btn-s" onClick={agregarLinea}>Agregar</button>
            </div>
            {lineas.map((l, i) => (
              <div key={i} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 14 }}>
                <span>{METODOS.find(([k]) => k === l.metodo)?.[1]}</span>
                <span className="num">{fmt(l.monto)}</span>
                <button type="button" className="btn btn-g" style={{ height: 28, padding: "0 10px" }} onClick={() => quitarLinea(i)}>Quitar</button>
              </div>
            ))}
            <div className="muted num" style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <span>Pagado: {fmt(pagado)}</span>
              <span>Pendiente: {fmt(pendiente)}</span>
            </div>
          </div>
        )}

        {error && <div className="error-banner">{error}</div>}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onCancel} disabled={enviando}>Cancelar</button>
          <button type="button" className="btn btn-p" onClick={confirmar} disabled={!puedeConfirmar || enviando}>
            {enviando ? "Procesando…" : `Confirmar cobro`}
          </button>
        </div>
      </div>
    </div>
  );
}
