import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import Modal, { Campo, ErrorBanner, Seccion } from "../components/Modal";
import { centavos, documento, fmt, fmtFecha as fecha, fmtFechaHora } from "../format";
import { useIsMobile } from "../useMediaQuery";
import { useTurno } from "../useTurno";

const GRANDE = { fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontWeight: 700 };

const origen = (c) => (c.venta_numero ? `Venta #${c.venta_numero}` : c.notas || "Cargo manual");

// Reparte un monto entre los cargos pendientes en el orden en que vienen (el
// mismo con que los paga el servidor: el que vence primero).
function repartir(cargos, monto) {
  let resto = centavos(monto);
  return Object.fromEntries(cargos.map((c) => {
    const parte = Math.min(Number(c.pendiente), Math.max(resto, 0));
    resto = centavos(resto - parte);
    return [c.id, parte];
  }));
}

function ModalAbono({ detalle, turno, onClose, onHecho, onFallo }) {
  const pendientes = detalle.cargos.filter((c) => Number(c.pendiente) > 0);
  const saldo = Number(detalle.cliente.saldo);
  const [metodos, setMetodos] = useState(null);
  const [metodoId, setMetodoId] = useState(null);
  const [monto, setMonto] = useState("");
  const [recibido, setRecibido] = useState("");
  const [elegir, setElegir] = useState(false);
  const [partes, setPartes] = useState({}); // {cargo_id: "monto"} al elegir cargos
  const [notas, setNotas] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api.metodosPago().then(setMetodos).catch((err) => setError(err.message));
  }, []);

  const disponibles = (metodos || []).filter((m) => turno.cajas.includes(m.caja_id));
  const metodo = disponibles.find((m) => m.id === metodoId) || disponibles[0];
  const valor = centavos(Number(monto) || 0);
  const automatico = repartir(pendientes, valor);
  const repartido = centavos(pendientes.reduce((a, c) => a + Math.max(Number(partes[c.id]) || 0, 0), 0));
  const cambio = metodo?.usa_denominaciones && recibido !== "" ? Number(recibido) - valor : 0;

  let bloqueo = "";
  if (valor <= 0) bloqueo = "Escribe cuánto abona.";
  else if (valor > saldo) bloqueo = `Debe ${fmt(saldo)}: el abono no puede ser mayor.`;
  else if (!metodo) bloqueo = "No hay métodos de pago en las cajas del turno.";
  else if (elegir && pendientes.some((c) => Number(partes[c.id]) < 0)) bloqueo = "Un monto repartido es negativo.";
  else if (elegir && repartido !== valor) bloqueo = `Lo repartido (${fmt(repartido)}) debe sumar el abono (${fmt(valor)}).`;
  else if (elegir && pendientes.some((c) => Number(partes[c.id]) > Number(c.pendiente))) bloqueo = "Un cargo recibe más de lo que debe.";
  else if (cambio < 0) bloqueo = `Con ${fmt(Number(recibido))} faltan ${fmt(-cambio)}.`;

  const alternarElegir = () => {
    // Al pasar a elegir, se parte del reparto automático del monto escrito.
    if (!elegir) setPartes(Object.fromEntries(Object.entries(automatico).map(([id, m]) => [id, m ? String(m) : ""])));
    setElegir(!elegir);
  };

  const abonar = async (e) => {
    e.preventDefault();
    if (bloqueo) return;
    setEnviando(true);
    setError("");
    // Se manda el reparto que se ve (también el automático): si mientras tanto
    // los cargos cambiaron, el servidor lo rechaza en vez de repartir distinto.
    const elegidos = elegir ? Object.fromEntries(pendientes.map((c) => [c.id, centavos(Number(partes[c.id]) || 0)])) : automatico;
    const aplicaciones = Object.entries(elegidos).filter(([, m]) => m > 0).map(([id, m]) => ({ cargo_id: id, monto: m }));
    try {
      const r = await api.abonar(detalle.cliente.cliente_id, {
        sesion_id: turno.id, metodo_pago_id: metodo.id, monto: valor, aplicaciones, notas: notas.trim() || null,
      });
      onHecho(r, `Abono de ${fmt(valor)} registrado.${cambio > 0 ? ` Cambio ${fmt(cambio)}.` : ""}`);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
      onFallo();
    }
  };

  return (
    <Modal titulo={`Abono de ${detalle.cliente.nombre}`} onClose={() => !enviando && onClose()} ancho={560}>
      <form onSubmit={abonar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <span className="muted">Debe <strong className="num">{fmt(saldo)}</strong> · entra al turno #{turno.numero}</span>
        <Campo etiqueta="Monto del abono">
          <input className="inp num" type="number" min="0" step="any" inputMode="decimal" autoFocus value={monto}
            onChange={(e) => setMonto(e.target.value)} />
        </Campo>
        <button type="button" className="btn btn-s" style={{ alignSelf: "flex-start", height: 34, fontSize: 13, marginTop: -6 }}
          onClick={() => setMonto(String(saldo))}>Todo lo que debe ({fmt(saldo)})</button>

        {metodos && (
          <div role="radiogroup" aria-label="Método de pago" style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
            {disponibles.map((m) => (
              <button key={m.id} type="button" role="radio" aria-checked={metodo?.id === m.id}
                className={`pay${metodo?.id === m.id ? " on" : ""}`} onClick={() => setMetodoId(m.id)}>{m.nombre}</button>
            ))}
          </div>
        )}
        {metodo?.usa_denominaciones && valor > 0 && (
          <div style={{ display: "flex", gap: 12, alignItems: "flex-end", flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 160px" }}>
              <Campo etiqueta="Recibe (opcional)">
                <input className="inp num" type="number" min="0" step="any" inputMode="decimal" value={recibido}
                  placeholder={String(valor)} onChange={(e) => setRecibido(e.target.value)} />
              </Campo>
            </div>
            {recibido !== "" && cambio >= 0 && (
              <span className="num" style={{ fontSize: 20, fontWeight: 700, color: "var(--accent-hover)", paddingBottom: 8 }}>Cambio {fmt(cambio)}</span>
            )}
          </div>
        )}

        <Seccion etiqueta="A qué cargos se aplica">
          <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
            <input type="checkbox" checked={elegir} onChange={alternarElegir} />
            Elegir los cargos (si no, paga primero lo que vence antes)
          </label>
          <div className="card" style={{ padding: "4px 12px" }}>
            {pendientes.map((c) => (
              <div key={c.id} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) auto", gap: 10, alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--border-2)" }}>
                <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                  <span style={{ fontWeight: 600, overflowWrap: "anywhere" }}>{origen(c)}</span>
                  <span className="muted num" style={{ fontSize: 12 }}>
                    Debe {fmt(c.pendiente)} · vence {fecha(c.vence_en)}{c.vencido ? " (vencido)" : ""}
                  </span>
                </div>
                {elegir ? (
                  <input className="inp num" type="number" min="0" step="any" inputMode="decimal" style={{ width: 120 }}
                    aria-label={`Abono a ${origen(c)}`} value={partes[c.id] ?? ""}
                    onChange={(e) => setPartes((p) => ({ ...p, [c.id]: e.target.value }))} />
                ) : (
                  <span className="num" style={{ fontWeight: 700, color: automatico[c.id] ? "var(--accent-hover)" : "var(--text-muted)" }}>
                    {automatico[c.id] ? fmt(automatico[c.id]) : "—"}
                  </span>
                )}
              </div>
            ))}
          </div>
        </Seccion>
        <Campo etiqueta="Notas (opcional)">
          <input className="inp" value={notas} onChange={(e) => setNotas(e.target.value)} />
        </Campo>
        {bloqueo && monto !== "" && <div className="muted" role="status" style={{ fontSize: 14 }}>{bloqueo}</div>}
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-p" disabled={!!bloqueo || enviando}>
            {enviando ? "Registrando…" : `Abonar ${fmt(valor)}`}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function ModalCargo({ detalle, onClose, onHecho }) {
  const [monto, setMonto] = useState("");
  const [notas, setNotas] = useState("");
  const [vence, setVence] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const guardar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    try {
      const r = await api.cargoManual(detalle.cliente.cliente_id, { monto: Number(monto), notas, vence_en: vence || null });
      onHecho(r, `Cargo de ${fmt(Number(monto))} registrado.`);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <Modal titulo={`Cargo manual a ${detalle.cliente.nombre}`} onClose={onClose}>
      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <span className="muted" style={{ fontSize: 14 }}>
          Deuda que no viene de una venta: un saldo del sistema anterior, un préstamo… No pasa por caja ni revisa el cupo.
        </span>
        <Campo etiqueta="Monto">
          <input className="inp num" type="number" min="0.01" step="any" inputMode="decimal" required autoFocus value={monto} onChange={(e) => setMonto(e.target.value)} />
        </Campo>
        <Campo etiqueta="De qué es">
          <input className="inp" required value={notas} placeholder="Ej.: saldo del cuaderno" onChange={(e) => setNotas(e.target.value)} />
        </Campo>
        <Campo etiqueta="Vence" ayuda={`Si lo dejas vacío, en ${detalle.cliente.dias_credito} días (sus días de crédito).`}>
          <input className="inp" type="date" value={vence} onChange={(e) => setVence(e.target.value)} />
        </Campo>
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-p" disabled={enviando || !(Number(monto) > 0) || !notas.trim()}>Registrar cargo</button>
        </div>
      </form>
    </Modal>
  );
}

function ModalCondonar({ cargo, onClose, onHecho }) {
  const [monto, setMonto] = useState(String(Number(cargo.pendiente)));
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const valor = Number(monto) || 0;

  const condonar = async (e) => {
    e.preventDefault();
    setEnviando(true);
    try {
      const r = await api.condonar(cargo.id, valor, motivo);
      onHecho(r, `Se condonaron ${fmt(valor)}.`);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <Modal titulo="Condonar deuda" onClose={onClose}>
      <form onSubmit={condonar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <span>
          <strong>{origen(cargo)}</strong> · debe <span className="num">{fmt(cargo.pendiente)}</span> de {fmt(cargo.monto)}.
          <span className="muted"> Se perdona sin pasar por caja y queda en auditoría.</span>
        </span>
        <Campo etiqueta="Monto a condonar">
          <input className="inp num" type="number" min="0.01" step="any" max={Number(cargo.pendiente)} inputMode="decimal" value={monto} onChange={(e) => setMonto(e.target.value)} />
        </Campo>
        <Campo etiqueta="Motivo">
          <input className="inp" autoFocus value={motivo} placeholder="Ej.: error al cargar, descuento acordado" onChange={(e) => setMotivo(e.target.value)} />
        </Campo>
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-d"
            disabled={enviando || valor <= 0 || valor > Number(cargo.pendiente) || !motivo.trim()}>Condonar {fmt(valor)}</button>
        </div>
      </form>
    </Modal>
  );
}

function Dato({ etiqueta, valor, color }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 110 }}>
      <span className="muted" style={{ fontSize: 12, fontWeight: 600 }}>{etiqueta}</span>
      <span className="num" style={{ ...GRANDE, fontSize: 22, color }}>{valor}</span>
    </div>
  );
}

function DetalleCredito({ detalle, turno, isMobile, onCambio, onRecargar, onVolver }) {
  const { puede } = useAuth();
  const [modal, setModal] = useState(null); // {tipo: "abono"|"cargo"|"condonar", cargo?}
  const [aviso, setAviso] = useState("");
  const c = detalle.cliente;
  const pendientes = detalle.cargos.filter((x) => Number(x.pendiente) > 0);
  const pagados = detalle.cargos.filter((x) => Number(x.pendiente) === 0);
  const hecho = (r, mensaje) => {
    setModal(null);
    setAviso(mensaje);
    onCambio(r);
  };

  return (
    <section className="card" aria-label={`Crédito de ${c.nombre}`} style={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <div style={{ padding: 18, display: "flex", gap: 10, alignItems: "flex-start", borderBottom: "1px solid var(--border-2)" }}>
        {isMobile && (
          <button type="button" onClick={onVolver} aria-label="Volver a la lista" className="btn btn-g" style={{ width: 40, height: 40, padding: 0, flexShrink: 0 }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M15 5l-7 7 7 7" /></svg>
          </button>
        )}
        <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
          <h2 style={{ fontSize: isMobile ? 20 : 24, overflowWrap: "anywhere" }}>{c.nombre}</h2>
          <span className="muted" style={{ fontSize: 13 }}>
            {[documento(c), c.telefono, `${c.dias_credito} días de crédito`, !c.activo && "cliente desactivado"].filter(Boolean).join(" · ")}
          </span>
        </div>
      </div>

      <div style={{ padding: 18, display: "flex", gap: 20, flexWrap: "wrap", borderBottom: "1px solid var(--border-2)" }}>
        <Dato etiqueta="Debe" valor={fmt(c.saldo)} />
        <Dato etiqueta="Vencido" valor={fmt(c.vencido)} color={Number(c.vencido) > 0 ? "var(--danger)" : undefined} />
        <Dato etiqueta="Disponible" valor={Number(c.limite_credito) > 0 ? fmt(c.disponible) : "Sin cupo"} />
        <Dato etiqueta="Cupo" valor={fmt(c.limite_credito)} />
      </div>

      <div style={{ padding: "12px 18px", display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", background: "var(--surface-2)", borderBottom: "1px solid var(--border-2)" }}>
        <button type="button" className="btn btn-p" disabled={!turno || Number(c.saldo) === 0} onClick={() => setModal({ tipo: "abono" })}>
          Registrar abono
        </button>
        {puede("clientes.editar") && (
          <button type="button" className="btn btn-s" onClick={() => setModal({ tipo: "cargo" })}>Cargo manual</button>
        )}
        {turno === null && <span className="muted" style={{ fontSize: 13 }}>Para recibir abonos abre el turno en <Link to="/caja">Caja</Link>.</span>}
      </div>
      {aviso && <div role="status" style={{ margin: "12px 18px 0", fontWeight: 600, color: "var(--accent-hover)" }}>{aviso}</div>}

      <div style={{ padding: 18, display: "flex", flexDirection: "column", gap: 18 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <h3 style={{ fontSize: 16 }}>Lo que debe</h3>
          {pendientes.length === 0 && <span className="muted">No tiene deudas pendientes.</span>}
          {pendientes.map((x) => (
            <div key={x.id} style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", padding: "10px 0", borderBottom: "1px solid var(--border-2)" }}>
              <div style={{ flex: "1 1 200px", minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                <span style={{ fontWeight: 600, overflowWrap: "anywhere" }}>{origen(x)}</span>
                <span className="muted" style={{ fontSize: 12 }}>
                  {fecha(x.creado_en)} · {fmt(x.monto)}
                  {Number(x.abonado) > 0 && ` · abonado ${fmt(x.abonado)}`}
                  {Number(x.condonado) > 0 && ` · condonado ${fmt(x.condonado)}`}
                </span>
              </div>
              <span className={`chip ${x.vencido ? "bad" : "neu"}`}>{x.vencido ? "Venció" : "Vence"} {fecha(x.vence_en)}</span>
              <span className="num" style={{ fontWeight: 700, minWidth: 90, textAlign: "right" }}>{fmt(x.pendiente)}</span>
              {puede("creditos.condonar") && (
                <button type="button" className="btn btn-g" style={{ height: 32, fontSize: 13 }} aria-label={`Condonar ${origen(x)}`}
                  onClick={() => setModal({ tipo: "condonar", cargo: x })}>Condonar</button>
              )}
            </div>
          ))}
        </div>

        {detalle.abonos.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <h3 style={{ fontSize: 16 }}>
              Abonos{detalle.totales.abonos > detalle.abonos.length && <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}> (los {detalle.abonos.length} más recientes de {detalle.totales.abonos})</span>}
            </h3>
            {detalle.abonos.map((a) => (
              <div key={a.id} style={{ display: "flex", gap: 10, justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--border-2)", opacity: a.vigente ? 1 : 0.6 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                  <span style={{ fontSize: 14 }}>
                    {a.cruce ? "Cruce de cuentas" : `${a.metodo} · turno #${a.turno}`}{!a.vigente && " · anulado"}
                  </span>
                  <span className="muted" style={{ fontSize: 12, overflowWrap: "anywhere" }}>
                    {fmtFechaHora(a.creado_en)} · {a.usuario}{a.notas ? ` · ${a.notas}` : ""}
                  </span>
                </div>
                <span className="num" style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{fmt(a.monto)}</span>
              </div>
            ))}
          </div>
        )}

        {detalle.condonaciones.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <h3 style={{ fontSize: 16 }}>
              Condonaciones{detalle.totales.condonaciones > detalle.condonaciones.length && <span className="muted" style={{ fontSize: 13, fontWeight: 400 }}> (las {detalle.condonaciones.length} más recientes de {detalle.totales.condonaciones})</span>}
            </h3>
            {detalle.condonaciones.map((x) => (
              <div key={x.id} style={{ display: "flex", gap: 10, justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--border-2)" }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                  <span style={{ fontSize: 14, overflowWrap: "anywhere" }}>{x.motivo}</span>
                  <span className="muted" style={{ fontSize: 12 }}>{fmtFechaHora(x.creado_en)} · {x.autorizada_por}</span>
                </div>
                <span className="num" style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{fmt(x.monto)}</span>
              </div>
            ))}
          </div>
        )}

        {pagados.length > 0 && (
          <details>
            <summary className="lbl" style={{ cursor: "pointer" }}>
              Cargos ya pagados ({detalle.totales.cargos_pagados}{detalle.totales.cargos_pagados > pagados.length ? `, se ven los ${pagados.length} más recientes` : ""})
            </summary>
            {pagados.map((x) => (
              <div key={x.id} style={{ display: "flex", justifyContent: "space-between", gap: 10, padding: "8px 0", borderBottom: "1px solid var(--border-2)", fontSize: 14 }}>
                <span style={{ overflowWrap: "anywhere" }}>{origen(x)} <span className="muted">· {fecha(x.creado_en)}</span></span>
                <span className="num muted">{fmt(x.monto)}</span>
              </div>
            ))}
          </details>
        )}
      </div>

      {modal?.tipo === "abono" && <ModalAbono detalle={detalle} turno={turno} onClose={() => setModal(null)} onHecho={hecho} onFallo={onRecargar} />}
      {modal?.tipo === "cargo" && <ModalCargo detalle={detalle} onClose={() => setModal(null)} onHecho={hecho} />}
      {modal?.tipo === "condonar" && <ModalCondonar cargo={modal.cargo} onClose={() => setModal(null)} onHecho={hecho} />}
    </section>
  );
}

// Fiado: quién debe, cuánto y desde cuándo; abonos, cargos y condonaciones.
// ?cliente=<id> abre directamente el crédito de ese cliente (desde Clientes).
export default function Creditos() {
  const isMobile = useIsMobile();
  const { turno, error: errorTurno, recargar: recargarTurno } = useTurno();
  const [params, setParams] = useSearchParams();
  const clienteId = params.get("cliente");
  const [q, setQ] = useState("");
  const [clientes, setClientes] = useState(null);
  const [cartera, setCartera] = useState(null); // solo llega sin búsqueda: se conserva al buscar
  const [detalle, setDetalle] = useState(null);
  const [error, setError] = useState("");
  const [errorDetalle, setErrorDetalle] = useState("");
  const [vistaDetalle, setVistaDetalle] = useState(0); // cambiarla vuelve a pedir el detalle
  const ultima = useRef(0);

  const cargar = useCallback((texto) => {
    const mia = ++ultima.current; // una respuesta de una búsqueda anterior se descarta
    return api.creditos(texto)
      .then((r) => {
        if (mia !== ultima.current) return;
        setError("");
        setClientes(r.clientes);
        if (r.cartera) setCartera(r.cartera);
      })
      .catch((err) => mia === ultima.current && setError(err.message));
  }, []);

  useEffect(() => {
    const t = setTimeout(() => cargar(q.trim()), 200);
    return () => clearTimeout(t);
  }, [q, cargar]);

  useEffect(() => {
    if (!clienteId) return undefined;
    let vigente = true;
    api.credito(clienteId)
      .then((d) => { if (vigente) { setErrorDetalle(""); setDetalle(d); } })
      .catch((err) => vigente && setErrorDetalle(err.message));
    return () => { vigente = false; };
  }, [clienteId, vistaDetalle]);

  const elegir = (id) => {
    setErrorDetalle("");
    setParams(id ? { cliente: id } : {});
  };
  const actual = clienteId && detalle?.cliente.cliente_id === clienteId ? detalle : null;
  const mostrarLista = !isMobile || !clienteId;

  return (
    <>
      <header style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Créditos</h1>
        {cartera && (
          <div className="muted num" style={{ fontSize: 14 }}>
            Cartera {fmt(cartera.total)} · vencida{" "}
            <span style={{ color: Number(cartera.vencido) > 0 ? "var(--danger)" : undefined, fontWeight: 600 }}>{fmt(cartera.vencido)}</span>
            {" "}· {cartera.clientes} {Number(cartera.clientes) === 1 ? "cliente" : "clientes"}
          </div>
        )}
      </header>
      {error && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>{error}</span>
          <button type="button" className="btn btn-s" onClick={() => cargar(q.trim())}>Reintentar</button>
        </div>
      )}
      {errorTurno && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>No se pudo revisar el turno de caja (para abonos): {errorTurno}</span>
          <button type="button" className="btn btn-s" onClick={recargarTurno}>Reintentar</button>
        </div>
      )}
      {clienteId && errorDetalle && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <span>No se pudo abrir el crédito del cliente: {errorDetalle}</span>
          <span style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn btn-s" onClick={() => setVistaDetalle((v) => v + 1)}>Reintentar</button>
            <button type="button" className="btn btn-s" onClick={() => elegir(null)}>Volver a la lista</button>
          </span>
        </div>
      )}

      <div style={{ display: "flex", gap: 20, alignItems: "flex-start" }}>
        {mostrarLista && (
          <section aria-label="Clientes con crédito" style={{ width: isMobile ? "100%" : 440, flexShrink: 0, display: "flex", flexDirection: "column", gap: 12 }}>
            <input className="inp" type="search" placeholder="Buscar cliente por nombre o documento" value={q} onChange={(e) => setQ(e.target.value)} />
            <span className="muted" style={{ fontSize: 13 }}>
              {q.trim() ? "Clientes que coinciden, deban o no." : "Clientes que deben, primero los que tienen deuda vencida."}
            </span>
            {!clientes && !error && <div className="muted">Cargando…</div>}
            <div className="card" style={{ overflow: "hidden" }}>
              {(clientes || []).map((c) => (
                <button key={c.cliente_id} type="button" onClick={() => elegir(c.cliente_id)}
                  aria-current={c.cliente_id === clienteId ? "true" : undefined}
                  style={{
                    width: "100%", border: 0, borderBottom: "1px solid var(--border-2)", textAlign: "left", cursor: "pointer",
                    font: "inherit", color: "inherit", padding: "12px 16px", display: "flex", gap: 10, alignItems: "center",
                    background: c.cliente_id === clienteId ? "var(--accent-soft)" : "#fff",
                  }}>
                  <span style={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                    <strong style={{ overflowWrap: "anywhere" }}>{c.nombre}</strong>
                    <span className="muted" style={{ fontSize: 12 }}>
                      {Number(c.vencido) > 0
                        ? <span style={{ color: "var(--danger)", fontWeight: 600 }}>Vencido {fmt(c.vencido)}</span>
                        : c.proximo_vencimiento ? `Vence ${fecha(c.proximo_vencimiento)}` : documento(c) || "Al día"}
                    </span>
                  </span>
                  <span className="num" style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{fmt(c.saldo)}</span>
                </button>
              ))}
              {clientes?.length === 0 && (
                <div className="muted" style={{ padding: 16 }}>{q.trim() ? "Ningún cliente con esa búsqueda." : "Nadie debe nada."}</div>
              )}
            </div>
          </section>
        )}

        {actual && (
          <DetalleCredito key={actual.cliente.cliente_id} detalle={actual} turno={turno} isMobile={isMobile}
            onCambio={(d) => { setDetalle(d); cargar(q.trim()); }}
            onRecargar={() => { setVistaDetalle((v) => v + 1); recargarTurno(); }}
            onVolver={() => elegir(null)} />
        )}
        {!clienteId && !isMobile && (
          <div className="muted" style={{ alignSelf: "center", flexGrow: 1, textAlign: "center" }}>Elige un cliente para ver su crédito.</div>
        )}
      </div>
    </>
  );
}
