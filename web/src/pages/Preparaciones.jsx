import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import EditorLineas from "../components/EditorLineas";
import Modal, { Campo, ErrorBanner, Seccion } from "../components/Modal";
import { fmtCant, fmtCosto } from "../format";

// Preparaciones: insumos que se fabrican con otros (salsas, adobo, rellenos).
// Su costo por unidad = costo de la receta ÷ rendimiento; los platos que las
// usan se recalculan solos.
function ModalPreparacion({ prep, insumos, unidades, onClose, onGuardado }) {
  const nueva = !prep;
  const [f, setF] = useState({
    nombre: "", unidad_medida_id: unidades[0]?.id || "",
    rendimiento: prep ? String(prep.rendimiento) : "",
    receta: (prep?.receta || []).map((r) => ({ id: r.insumo_id, cantidad: String(r.cantidad) })),
  });
  const [error, setError] = useState("");
  const opciones = insumos.filter((i) => i.id !== prep?.id);
  const unidadDe = (id) => insumos.find((i) => i.id === id)?.unidad || "";
  const unidadProducida = prep ? prep.unidad : unidades.find((u) => u.id === f.unidad_medida_id)?.simbolo;

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    const receta = f.receta.map((r) => ({ insumo_id: r.id, cantidad: r.cantidad }));
    try {
      if (nueva) {
        await api.crearPreparacion({ nombre: f.nombre, unidad_medida_id: f.unidad_medida_id, rendimiento: f.rendimiento, receta });
      } else {
        await api.guardarPreparacion(prep.id, { rendimiento: f.rendimiento, receta });
      }
      onGuardado();
    } catch (err) {
      setError(err.message);
    }
  };

  const quitar = async () => {
    setError("");
    try {
      await api.quitarPreparacion(prep.id);
      onGuardado();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Modal titulo={nueva ? "Nueva preparación" : prep.nombre} onClose={onClose} ancho={540}>
      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {nueva && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 140px", gap: 12 }}>
            <Campo etiqueta="Nombre">
              <input className="inp" required value={f.nombre} onChange={(e) => setF((x) => ({ ...x, nombre: e.target.value }))} />
            </Campo>
            <Campo etiqueta="Unidad">
              <select className="inp" value={f.unidad_medida_id} onChange={(e) => setF((x) => ({ ...x, unidad_medida_id: e.target.value }))}>
                {unidades.map((u) => <option key={u.id} value={u.id}>{u.simbolo}</option>)}
              </select>
            </Campo>
          </div>
        )}
        <Campo etiqueta={`Rendimiento por lote (${unidadProducida || ""})`} ayuda="Cuánto produce un lote de esta receta.">
          <input className="inp num" inputMode="decimal" required value={f.rendimiento}
            onChange={(e) => setF((x) => ({ ...x, rendimiento: e.target.value }))} style={{ maxWidth: 180 }} />
        </Campo>
        <Seccion etiqueta="Receta de un lote">
          <EditorLineas opciones={opciones} lineas={f.receta} unidad={unidadDe}
            onChange={(receta) => setF((x) => ({ ...x, receta }))} />
        </Seccion>
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", flexWrap: "wrap" }}>
          {!nueva && (
            <button type="button" className="btn btn-d" style={{ marginRight: "auto" }} onClick={quitar}
              title="Vuelve a ser un insumo comprado, con costo a mano">Quitar receta</button>
          )}
          <button type="button" className="btn btn-s" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-p">Guardar</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Preparaciones() {
  const [preps, setPreps] = useState([]);
  const [insumos, setInsumos] = useState([]);
  const [unidades, setUnidades] = useState([]);
  const [editando, setEditando] = useState(null); // {prep} | {nueva: true}
  const [error, setError] = useState("");

  const cargar = useCallback(() => Promise.all([api.preparaciones(), api.insumos(), api.unidades()])
    .then(([p, i, u]) => {
      setPreps(p);
      setInsumos(i);
      setUnidades(u);
    })
    .catch((err) => setError(err.message)), []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h1 style={{ fontSize: 28, marginRight: "auto" }}>Preparaciones</h1>
        <button type="button" className="btn btn-p" onClick={() => setEditando({ nueva: true })}>+ Nueva preparación</button>
      </div>
      <p className="muted" style={{ margin: 0 }}>
        Salsas, adobos y rellenos que se hacen con otros insumos. Su costo sale de la receta y el rendimiento, y
        actualiza solo el costo de los platos que las usan.
      </p>
      <ErrorBanner mensaje={error} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
        {preps.map((p) => (
          <button key={p.id} type="button" className="mesa" onClick={() => setEditando({ prep: p })}>
            <div style={{ display: "flex", justifyContent: "space-between", width: "100%", gap: 8 }}>
              <strong style={{ fontSize: 16 }}>{p.nombre}</strong>
              <span className="chip neu num">{fmtCosto(p.costo)}/{p.unidad}</span>
            </div>
            <span className="muted" style={{ fontSize: 13 }}>Rinde {fmtCant(p.rendimiento)} {p.unidad} por lote</span>
            <span style={{ fontSize: 13 }}>{p.receta.map((r) => `${r.nombre} ${fmtCant(r.cantidad)} ${r.unidad}`).join(" · ")}</span>
          </button>
        ))}
        {preps.length === 0 && <div className="muted">Todavía no hay preparaciones.</div>}
      </div>
      {editando && (
        <ModalPreparacion prep={editando.prep} insumos={insumos} unidades={unidades}
          onClose={() => setEditando(null)} onGuardado={() => { setEditando(null); cargar(); }} />
      )}
    </div>
  );
}
