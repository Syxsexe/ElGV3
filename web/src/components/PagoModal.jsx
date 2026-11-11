import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { centavos, fmt } from "../format";
import BuscarTercero from "./BuscarTercero";
import Modal, { Campo, ErrorBanner, Seccion } from "./Modal";

const FIADO = "fiado";
const DIVIDIR = "dividir";
const BILLETES = [2000, 5000, 10000, 20000, 50000, 100000];

const num = (v) => centavos(Number(v) || 0);

// Billetes con los que suelen pagar: el total exacto y los que lo cubren.
function sugerencias(total) {
  const mayores = BILLETES.filter((b) => b > total).slice(0, 2);
  const redondeado = Math.ceil(total / 10000) * 10000;
  return [...new Set([total, redondeado, ...mayores])].filter((v) => v >= total).slice(0, 4);
}

// Cobrar un total: todo con un método (con cálculo del cambio en efectivo),
// todo fiado al cliente, o dividido entre varios métodos y fiado.
// onCobrar({pagos, fiado, cliente_id}, {cambio}) debe devolver una promesa:
// si falla, el error se muestra aquí y el modal sigue abierto. cajas: las del
// turno (solo se ofrecen los métodos que caen en ellas).
export default function PagoModal({ total, cliente, cajas, onCobrar, onClose }) {
  const [todos, setTodos] = useState(null);
  const [modoElegido, setModo] = useState(null);
  const [recibido, setRecibido] = useState("");
  const [filas, setFilas] = useState([]);
  const [clienteFiado, setClienteFiado] = useState(cliente || null);
  const [cupo, setCupo] = useState(null); // {cliente_id, disponible, ...}
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api.metodosPago()
      .then(setTodos)
      .catch((err) => setError(err.message));
  }, []);

  // Sin elegir, el primer método (el efectivo va primero); sin métodos, fiado.
  const metodos = todos && (cajas ? todos.filter((m) => cajas.includes(m.caja_id)) : todos);
  const modo = modoElegido ?? metodos?.[0]?.id ?? (metodos ? FIADO : null);

  const metodo = metodos?.find((m) => m.id === modo);
  const efectivo = metodo?.usa_denominaciones;

  // Lo que se manda al servidor según el modo.
  const { pagos, fiado } = useMemo(() => {
    if (modo === FIADO) return { pagos: [], fiado: total };
    if (modo === DIVIDIR) {
      return {
        pagos: filas.filter((f) => f.metodo !== FIADO && num(f.monto) > 0)
          .map((f) => ({ metodo_pago_id: f.metodo, monto: num(f.monto) })),
        fiado: centavos(filas.filter((f) => f.metodo === FIADO).reduce((a, f) => a + num(f.monto), 0)),
      };
    }
    return { pagos: total > 0 && modo ? [{ metodo_pago_id: modo, monto: total }] : [], fiado: 0 };
  }, [modo, filas, total]);

  const cubierto = pagos.reduce((a, p) => a + p.monto, 0) + fiado;
  const pendiente = centavos(total - cubierto);
  const cambio = efectivo && recibido !== "" ? num(recibido) - total : 0;
  const cupoActual = clienteFiado && cupo?.cliente_id === clienteFiado.id ? cupo : null;

  // El cupo se consulta al elegir a quién fiar (no con cada peso que se teclea).
  const fiando = fiado > 0;
  const idFiado = clienteFiado?.id;
  useEffect(() => {
    if (!fiando || !idFiado) return undefined;
    let vigente = true;
    api.cupoCliente(idFiado)
      .then((c) => vigente && setCupo(c))
      .catch((err) => vigente && setError(err.message));
    return () => { vigente = false; };
  }, [fiando, idFiado]);

  let bloqueo = "";
  if (pendiente > 0) bloqueo = `Falta asignar ${fmt(pendiente)}.`;
  else if (pendiente < 0) bloqueo = `Sobran ${fmt(-pendiente)}: los pagos suman más que el total.`;
  else if (efectivo && recibido !== "" && cambio < 0) bloqueo = `Con ${fmt(num(recibido))} faltan ${fmt(-cambio)}.`;
  else if (fiado > 0 && !clienteFiado) bloqueo = "Elige a quién se le da el crédito.";
  else if (fiado > 0 && cupoActual && fiado > Number(cupoActual.disponible)) {
    bloqueo = `${cupoActual.nombre} solo tiene ${fmt(cupoActual.disponible)} disponibles de crédito.`;
  }

  const elegirModo = (m) => {
    setError("");
    if (m === DIVIDIR && modo !== DIVIDIR) {
      setFilas([{ metodo: modo && modo !== FIADO ? modo : metodos?.[0]?.id ?? FIADO, monto: String(total) }]);
    }
    setModo(m);
  };

  const cambiarFila = (i, cambios) => setFilas((fs) => fs.map((f, j) => (j === i ? { ...f, ...cambios } : f)));

  const confirmar = async (e) => {
    e.preventDefault();
    if (bloqueo || enviando) return;
    setError("");
    setEnviando(true);
    try {
      await onCobrar({ pagos, fiado, cliente_id: fiado > 0 ? clienteFiado.id : cliente?.id ?? null },
        { cambio: Math.max(cambio, 0) });
    } catch (err) {
      setError(err.message || "No se pudo cobrar.");
      setEnviando(false);
    }
  };

  const opciones = [
    ...(metodos || []).map((m) => [m.id, m.nombre]),
    [FIADO, "Crédito"],
    [DIVIDIR, "Dividir"],
  ];

  return (
    <Modal titulo="Cobrar" onClose={() => !enviando && onClose()} ancho={480}>
      <form onSubmit={confirmar} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: -8 }}>
          <span className="muted">Total</span>
          <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 30, fontWeight: 700 }}>
            {fmt(total)}
          </span>
        </div>

        {!metodos && !error && <div className="muted">Cargando métodos de pago…</div>}
        {metodos && (
          <div role="radiogroup" aria-label="Forma de pago" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
            {opciones.map(([id, nombre]) => (
              <button key={id} type="button" role="radio" aria-checked={modo === id}
                className={`pay${modo === id ? " on" : ""}`} onClick={() => elegirModo(id)}>
                {nombre}
              </button>
            ))}
          </div>
        )}

        {efectivo && total > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <Campo etiqueta="Recibe (opcional)">
              <input className="inp num" type="number" min="0" step="any" inputMode="decimal" value={recibido}
                placeholder={String(total)} onChange={(e) => setRecibido(e.target.value)} />
            </Campo>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {sugerencias(total).map((v) => (
                <button key={v} type="button" className="btn btn-s" style={{ height: 34, fontSize: 13 }}
                  onClick={() => setRecibido(String(v))}>
                  {v === total ? "Exacto" : fmt(v)}
                </button>
              ))}
            </div>
            {recibido !== "" && cambio >= 0 && (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <span style={{ fontWeight: 600 }}>Cambio</span>
                <span className="num" style={{ fontSize: 24, fontWeight: 700, color: "var(--accent-hover)" }}>{fmt(cambio)}</span>
              </div>
            )}
          </div>
        )}

        {modo === DIVIDIR && (
          <Seccion etiqueta="Pagos">
            {filas.map((f, i) => (
              <div key={i} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 120px auto", gap: 8 }}>
                <select className="inp" aria-label={`Método del pago ${i + 1}`} value={f.metodo}
                  onChange={(e) => cambiarFila(i, { metodo: e.target.value })}>
                  {metodos.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
                  <option value={FIADO}>Crédito</option>
                </select>
                <input className="inp num" type="number" min="0" step="any" inputMode="decimal" aria-label={`Monto del pago ${i + 1}`}
                  value={f.monto} onChange={(e) => cambiarFila(i, { monto: e.target.value })} />
                <button type="button" className="btn btn-g" aria-label={`Quitar el pago ${i + 1}`} disabled={filas.length === 1}
                  onClick={() => setFilas((fs) => fs.filter((_, j) => j !== i))}>✕</button>
              </div>
            ))}
            <button type="button" className="btn btn-s" style={{ alignSelf: "flex-start" }} disabled={pendiente <= 0}
              onClick={() => setFilas((fs) => [...fs, {
                metodo: metodos.find((m) => !fs.some((x) => x.metodo === m.id))?.id ?? FIADO,
                monto: String(pendiente),
              }])}>
              Agregar pago
            </button>
          </Seccion>
        )}

        {fiado > 0 && (
          <Seccion etiqueta={`Crédito a (${fmt(fiado)})`}>
            {clienteFiado ? (
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                  <strong style={{ overflow: "hidden", textOverflow: "ellipsis" }}>{clienteFiado.nombre}</strong>
                  {cupoActual && (
                    <span className="muted num" style={{ fontSize: 13 }}>
                      Disponible {fmt(cupoActual.disponible)} de {fmt(cupoActual.limite_credito)}
                      {Number(cupoActual.cargos_vencidos) > 0 && ` · ${cupoActual.cargos_vencidos} cargo(s) vencido(s)`}
                    </span>
                  )}
                </div>
                <button type="button" className="btn btn-g" onClick={() => setClienteFiado(null)}>Cambiar</button>
              </div>
            ) : (
              <BuscarTercero rol="cliente" placeholder="Buscar cliente por nombre o documento"
                onElegir={(t) => setClienteFiado({ id: t.id, nombre: t.nombre })} />
            )}
          </Seccion>
        )}

        {bloqueo && metodos && <div className="muted" role="status" style={{ fontSize: 14 }}>{bloqueo}</div>}
        <ErrorBanner mensaje={error} />

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-p" disabled={!metodos || !!bloqueo || enviando}>
            {enviando ? "Cobrando…" : `Cobrar ${fmt(total)}`}
          </button>
        </div>
      </form>
    </Modal>
  );
}
