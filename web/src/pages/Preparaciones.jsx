import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import EditorLineas from "../components/EditorLineas";
import Modal, { Campo, ErrorBanner, Seccion } from "../components/Modal";
import { fmtCant, fmtCosto, fmtFechaHora } from "../format";

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

// Producir lotes: descuenta los ingredientes (receta × lotes) y suma lo
// producido al stock de la preparación. Si algo no alcanza, se produce igual
// y queda en negativo (se ve en rojo para ajustarlo).
function ModalProducir({ prep, onClose, onProducido }) {
  const [lotes, setLotes] = useState("1");
  const [notas, setNotas] = useState("");
  const [hechas, setHechas] = useState(null);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const n = Number(lotes) || 0;

  useEffect(() => { api.producciones(prep.id).then(setHechas).catch(() => setHechas([])); }, [prep.id]);

  const producir = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError("");
    try {
      onProducido(await api.producir(prep.id, lotes, notas.trim() || null));
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <Modal titulo={`Producir ${prep.nombre}`} onClose={() => !enviando && onClose()} ancho={540}>
      <form onSubmit={producir} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
          <Campo etiqueta="Lotes">
            <input className="inp num" type="number" min="0" step="any" inputMode="decimal" autoFocus required value={lotes}
              onChange={(e) => setLotes(e.target.value)} style={{ width: 110 }} />
          </Campo>
          <div style={{ paddingBottom: 10, fontSize: 15 }}>
            = <strong className="num">{fmtCant(n * Number(prep.rendimiento))} {prep.unidad}</strong>
            <span className="muted"> (hay {fmtCant(prep.stock)} {prep.unidad})</span>
          </div>
        </div>
        <Seccion etiqueta="Se descuenta">
          <div className="tabla">
            {prep.receta.map((r) => {
              const usa = n * Number(r.cantidad);
              const queda = Number(r.stock) - usa;
              return (
                <div key={r.insumo_id} className="tr" style={{ gridTemplateColumns: "minmax(0, 1fr) 100px 120px" }}>
                  <span style={{ overflowWrap: "anywhere" }}>{r.nombre}</span>
                  <span className="r num">{fmtCant(usa)} {r.unidad}</span>
                  <span className="r num" style={{ fontSize: 13, color: queda < 0 ? "var(--danger)" : "var(--text-muted)" }}>
                    queda {fmtCant(queda)}
                  </span>
                </div>
              );
            })}
          </div>
        </Seccion>
        {prep.receta.some((r) => Number(r.stock) - n * Number(r.cantidad) < 0) && (
          <div className="muted" role="status" style={{ fontSize: 13 }}>
            Algún ingrediente queda en negativo según el sistema: se produce igual; revisa su stock con un ajuste.
          </div>
        )}
        <Campo etiqueta="Notas (opcional)">
          <input className="inp" value={notas} onChange={(e) => setNotas(e.target.value)} />
        </Campo>
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-p" disabled={!(n > 0) || enviando}>{enviando ? "Produciendo…" : "Producir"}</button>
        </div>
        {hechas?.length > 0 && (
          <Seccion etiqueta="Últimas producciones">
            {hechas.map((h) => (
              <div key={h.id} style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 13, padding: "4px 0", borderBottom: "1px solid var(--border-2)" }}>
                <span className="muted">{fmtFechaHora(h.creada_en)} · {h.usuario}{h.notas && ` · ${h.notas}`}</span>
                <span className="num">{fmtCant(h.lotes)} lote(s) · {fmtCant(h.cantidad)} {prep.unidad}</span>
              </div>
            ))}
          </Seccion>
        )}
      </form>
    </Modal>
  );
}

export default function Preparaciones() {
  const [preps, setPreps] = useState([]);
  const [insumos, setInsumos] = useState([]);
  const [unidades, setUnidades] = useState([]);
  const [editando, setEditando] = useState(null); // {prep} | {nueva: true}
  const [produciendo, setProduciendo] = useState(null);
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
        Salsas, adobos y rellenos que se hacen por lotes con otros insumos. Su costo sale de la receta y el
        rendimiento. Al producir un lote se descuentan sus ingredientes y se suma lo preparado; los platos que la
        usan la descuentan al venderse.
      </p>
      <ErrorBanner mensaje={error} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
        {preps.map((p) => {
          const bajo = Number(p.stock) < 0 || (Number(p.stock_minimo) > 0 && Number(p.stock) <= Number(p.stock_minimo));
          return (
            <div key={p.id} className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", width: "100%", gap: 8 }}>
                <strong style={{ fontSize: 16 }}>{p.nombre}</strong>
                <span className="chip neu num">{fmtCosto(p.costo)}/{p.unidad}</span>
              </div>
              <span style={{ fontSize: 14 }}>
                Hay <strong className="num" style={{ color: bajo ? "var(--danger)" : undefined }}>{fmtCant(p.stock)} {p.unidad}</strong>
                <span className="muted"> · rinde {fmtCant(p.rendimiento)} {p.unidad} por lote</span>
              </span>
              <span className="muted" style={{ fontSize: 13 }}>{p.receta.map((r) => `${r.nombre} ${fmtCant(r.cantidad)} ${r.unidad}`).join(" · ")}</span>
              <div style={{ display: "flex", gap: 8, marginTop: "auto", paddingTop: 4 }}>
                <button type="button" className="btn btn-p" style={{ flexGrow: 1, height: 38 }} disabled={!p.activo}
                  onClick={() => setProduciendo(p)}>Producir</button>
                <button type="button" className="btn btn-s" style={{ height: 38 }} onClick={() => setEditando({ prep: p })}
                  aria-label={`Editar receta de ${p.nombre}`}>Editar receta</button>
              </div>
            </div>
          );
        })}
        {preps.length === 0 && <div className="muted">Todavía no hay preparaciones.</div>}
      </div>
      {produciendo && (
        <ModalProducir prep={produciendo} onClose={() => setProduciendo(null)}
          onProducido={() => { setProduciendo(null); cargar(); }} />
      )}
      {editando && (
        <ModalPreparacion prep={editando.prep} insumos={insumos} unidades={unidades}
          onClose={() => setEditando(null)} onGuardado={() => { setEditando(null); cargar(); }} />
      )}
    </div>
  );
}
