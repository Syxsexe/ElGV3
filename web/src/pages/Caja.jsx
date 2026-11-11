import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import ConteoBilletes from "../components/ConteoBilletes";
import { totalConteo } from "../conteo";
import Modal, { Campo, ErrorBanner } from "../components/Modal";
import { fmt, fmtFechaHora } from "../format";
import { useIsMobile } from "../useMediaQuery";

// Conceptos del desglose del esperado (vista v_flujos_caja), en el orden en
// que se muestran: primero lo que entra, después lo que sale.
const CONCEPTOS = [
  ["venta", "Ventas"],
  ["abono", "Abonos de crédito"],
  ["ingreso", "Ingresos"],
  ["traslado_entrada", "Traslados recibidos"],
  ["anulacion_egreso", "Gastos anulados"],
  ["egreso", "Gastos y pagos"],
  ["retiro", "Retiros"],
  ["traslado_salida", "Traslados enviados"],
];

const TIPOS_MOVIMIENTO = [
  ["retiro", "Retiro", "Plata que sale de una caja (ej. el dueño retira efectivo)."],
  ["ingreso", "Ingreso", "Plata que entra sin ser una venta (ej. sencillo que se trae al cajón)."],
  ["traslado", "Traslado", "De una caja a otra: consignar el efectivo al banco es Efectivo → Digital."],
];

const hora = (iso) => new Date(iso).toLocaleTimeString("es-CO", { hour: "2-digit", minute: "2-digit" });
const firmado = (n) => (Number(n) < 0 ? "− " : "") + fmt(Math.abs(Number(n)));

function claseDiferencia(dif) {
  if (dif == null) return "neu";
  return Number(dif) === 0 ? "ok" : Number(dif) < 0 ? "bad" : "warn";
}

function textoDiferencia(dif) {
  if (Number(dif) === 0) return "Cuadra";
  return (Number(dif) > 0 ? "Sobran " : "Faltan ") + fmt(Math.abs(Number(dif)));
}

function Fila({ etiqueta, valor, fuerte, color }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: fuerte ? 16 : 14, fontWeight: fuerte ? 700 : 400, padding: "5px 0" }}>
      <span className={fuerte ? undefined : "muted"}>{etiqueta}</span>
      <span className="num" style={{ color }}>{valor}</span>
    </div>
  );
}

// Base + desglose del esperado de una caja. Con el turno cerrado, también lo contado.
function ResumenCaja({ caja }) {
  return (
    <div className="card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 2 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, gap: 8 }}>
        <h2 style={{ fontSize: 18 }}>{caja.caja}</h2>
        {caja.usa_denominaciones && <span className="chip neu">Billetes y monedas</span>}
      </div>
      <Fila etiqueta="Base inicial" valor={fmt(caja.base)} />
      {CONCEPTOS.filter(([c]) => c === "venta" || caja.flujos[c] != null).map(([c, etiqueta]) => (
        <Fila key={c} etiqueta={etiqueta} valor={firmado(caja.flujos[c] || 0)}
          color={Number(caja.flujos[c]) < 0 ? "#8E2A20" : undefined} />
      ))}
      <div style={{ height: 1, background: "var(--border)", margin: "8px 0" }} />
      <Fila etiqueta="Esperado" valor={fmt(caja.esperado)} fuerte />
      {caja.contado != null && (
        <>
          <Fila etiqueta="Contado" valor={fmt(caja.contado)} />
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: 4 }}>
            <span className="muted" style={{ fontSize: 14 }}>Diferencia</span>
            <span className={`chip ${claseDiferencia(caja.diferencia)} num`}>{textoDiferencia(caja.diferencia)}</span>
          </div>
        </>
      )}
      {caja.diferencia_apertura != null && Number(caja.diferencia_apertura) !== 0 && (
        <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
          La base no coincide con lo contado al cerrar el turno anterior ({firmado(caja.diferencia_apertura)}).
        </div>
      )}
    </div>
  );
}

function BannerDiferencia({ etiqueta, contado, esperado }) {
  const dif = contado - esperado;
  const bg = dif === 0 ? "var(--ok-bg)" : dif < 0 ? "var(--danger-bg)" : "var(--warn-bg)";
  const color = dif === 0 ? "var(--ok-text)" : dif < 0 ? "#8E2A20" : "var(--warn-text)";
  return (
    <div style={{ borderRadius: 12, padding: 14, background: bg, display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 13, fontWeight: 600, color }}>{etiqueta}</span>
      <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 22, fontWeight: 700, color }}>
        {dif === 0 ? "$ 0 · cuadra" : textoDiferencia(dif)}
      </span>
    </div>
  );
}

function ListaMovimientos({ movimientos }) {
  if (movimientos.length === 0) return <div className="muted" style={{ padding: "4px 0" }}>Sin retiros, ingresos ni traslados.</div>;
  return (
    <div className="tabla">
      {movimientos.map((m) => (
        <div key={m.id} className="tr" style={{ gridTemplateColumns: "84px 90px 1fr 110px", minWidth: 500 }}>
          <span className="num muted" style={{ whiteSpace: "nowrap" }}>{hora(m.creado_en)}</span>
          <span><span className="chip neu">{TIPOS_MOVIMIENTO.find(([t]) => t === m.tipo)?.[1]}</span></span>
          <span>
            {m.motivo}
            <span className="muted" style={{ fontSize: 12 }}> · {[m.caja_origen, m.caja_destino].filter(Boolean).join(" → ")} · {m.usuario}</span>
          </span>
          <span className="r num">{fmt(m.monto)}</span>
        </div>
      ))}
    </div>
  );
}

// ── Apertura ───────────────────────────────────────────────────────────────

// La caja de billetes (el cajón) se abre contando billetes y monedas: la
// base es el total contado. Las demás cajas llevan su base escrita.
function Apertura({ cajas, onAbierta }) {
  const isMobile = useIsMobile();
  const [bases, setBases] = useState({});
  const [denominaciones, setDenominaciones] = useState([]);
  const [cantidades, setCantidades] = useState({});
  const [notas, setNotas] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const conBilletes = cajas.find((c) => c.usa_denominaciones);
  const otras = cajas.filter((c) => !c.usa_denominaciones);
  const totalBilletes = totalConteo(denominaciones, cantidades);

  useEffect(() => {
    if (conBilletes) api.denominaciones().then(setDenominaciones).catch((err) => setError(err.message));
  }, [conBilletes]);

  const abrir = async (e) => {
    e.preventDefault();
    setError("");
    setEnviando(true);
    try {
      const montos = Object.fromEntries(cajas.map((c) => [c.id, c.usa_denominaciones ? totalBilletes : Number(bases[c.id]) || 0]));
      onAbierta(await api.abrirTurno(montos, notas || null));
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  if (cajas.length === 0) {
    return <ErrorBanner mensaje="No hay cajas activas: un administrador debe crearlas en Configuración." />;
  }
  const anterior = conBilletes?.contado_anterior;
  return (
    <form onSubmit={abrir} style={{ display: "grid", gap: 16, alignItems: "start",
      gridTemplateColumns: conBilletes && !isMobile ? "minmax(0, 1.6fr) minmax(280px, 1fr)" : "minmax(0, 560px)" }}>
      {conBilletes && (
        <ConteoBilletes titulo={`Base ${conBilletes.nombre}: billetes y monedas`} denominaciones={denominaciones}
          cantidades={cantidades} setCantidades={setCantidades}
          pie={anterior != null && (
            <div className="muted" style={{ fontSize: 13 }}>
              Al cerrar el turno anterior se contaron {fmt(anterior)}.
              {totalBilletes > 0 && totalBilletes !== Number(anterior) && <strong style={{ color: "var(--warn-text)" }}> No coincide con lo que estás contando.</strong>}
            </div>
          )} />
      )}
      <div className="card" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
        <h2 style={{ fontSize: 22 }}>Abrir turno</h2>
        {conBilletes && (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 10 }}>
            <span className="lbl">Base {conBilletes.nombre}</span>
            <span className="num" style={{ fontWeight: 700, fontSize: 18 }}>{fmt(totalBilletes)}</span>
          </div>
        )}
        {otras.map((c) => (
          <Campo key={c.id} etiqueta={`Base ${c.nombre} ($)`}
            ayuda={c.contado_anterior != null ? `Al cerrar el turno anterior se contaron ${fmt(c.contado_anterior)}.` : undefined}>
            <input className="inp num" type="number" min="0" inputMode="numeric"
              value={bases[c.id] ?? ""} onChange={(e) => setBases((b) => ({ ...b, [c.id]: e.target.value }))} />
          </Campo>
        ))}
        <Campo etiqueta="Notas (opcional)">
          <textarea className="inp" style={{ height: 80, padding: "10px 12px", resize: "none" }}
            value={notas} onChange={(e) => setNotas(e.target.value)} />
        </Campo>
        {conBilletes && totalBilletes === 0 && (
          <div className="muted" style={{ fontSize: 13 }}>Sin billetes contados, {conBilletes.nombre} abre en $ 0.</div>
        )}
        <ErrorBanner mensaje={error} />
        <button type="submit" className="btn btn-p" disabled={enviando} style={{ height: 48 }}>
          {enviando ? "Abriendo…" : "Abrir turno"}
        </button>
      </div>
    </form>
  );
}

// ── Movimientos ────────────────────────────────────────────────────────────

function ModalMovimiento({ turnoId, cajas, onClose, onGuardado, onFallo }) {
  const [tipo, setTipo] = useState("retiro");
  // La primera caja es la de billetes (el cajón): retiros e ingresos van ahí
  // por defecto; un traslado sale de ella hacia otra.
  const [origen, setOrigen] = useState(cajas[0]?.caja_id || "");
  const [destino, setDestino] = useState(cajas[0]?.caja_id || "");
  const [monto, setMonto] = useState("");
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const usaOrigen = tipo !== "ingreso";
  const usaDestino = tipo !== "retiro";

  const elegirTipo = (t) => {
    setTipo(t);
    if (t === "traslado" && destino === origen) {
      setDestino(cajas.find((c) => c.caja_id !== origen)?.caja_id || destino);
    }
  };

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    setEnviando(true);
    try {
      onGuardado(await api.movimientoCaja(turnoId, {
        tipo, monto: Number(monto), motivo,
        caja_origen_id: usaOrigen ? origen : null,
        caja_destino_id: usaDestino ? destino : null,
      }));
    } catch (err) {
      setError(err.message);
      setEnviando(false);
      onFallo(err.message);
    }
  };

  const selector = (valor, setValor) => (
    <select className="inp" value={valor} onChange={(e) => setValor(e.target.value)}>
      {cajas.map((c) => <option key={c.caja_id} value={c.caja_id}>{c.caja}</option>)}
    </select>
  );

  return (
    <Modal titulo="Registrar movimiento" onClose={onClose}>
      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="seg" role="radiogroup" aria-label="Tipo de movimiento" style={{ alignSelf: "flex-start" }}>
          {TIPOS_MOVIMIENTO.map(([t, etiqueta]) => (
            <button key={t} type="button" role="radio" aria-checked={tipo === t} className={tipo === t ? "on" : ""}
              onClick={() => elegirTipo(t)}>{etiqueta}</button>
          ))}
        </div>
        <div className="muted" style={{ fontSize: 13 }}>{TIPOS_MOVIMIENTO.find(([t]) => t === tipo)[2]}</div>
        {usaOrigen && <Campo etiqueta={tipo === "traslado" ? "Sale de" : "Caja"}>{selector(origen, setOrigen)}</Campo>}
        {usaDestino && <Campo etiqueta={tipo === "traslado" ? "Entra a" : "Caja"}>{selector(destino, setDestino)}</Campo>}
        <Campo etiqueta="Monto ($)">
          <input className="inp num" type="number" min="1" inputMode="numeric" required value={monto}
            onChange={(e) => setMonto(e.target.value)} />
        </Campo>
        <Campo etiqueta="Motivo" ayuda="Un movimiento no se borra: si te equivocas, registra el contrario.">
          <input className="inp" required value={motivo} onChange={(e) => setMotivo(e.target.value)} />
        </Campo>
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-p" disabled={enviando}>{enviando ? "Guardando…" : "Registrar"}</button>
        </div>
      </form>
    </Modal>
  );
}

// ── Cierre ─────────────────────────────────────────────────────────────────

function TurnoAbierto({ turno, setTurno, onCerrado, onCambio }) {
  const isMobile = useIsMobile();
  const [denominaciones, setDenominaciones] = useState([]);
  const [cantidades, setCantidades] = useState({});
  // Los contados de las cajas sin billetes empiezan VACÍOS a propósito (no con
  // el esperado): el cajero escribe lo que de verdad ve en Nequi o en el banco,
  // para que un faltante real no quede tapado por un valor que siempre cuadra.
  const [contados, setContados] = useState({});
  const [notas, setNotas] = useState("");
  const [movimiento, setMovimiento] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [abiertas, setAbiertas] = useState([]); // cuentas sin cobrar al pedir el cierre
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    api.denominaciones().then(setDenominaciones).catch((err) => setError(err.message));
  }, []);

  const totalBilletes = totalConteo(denominaciones, cantidades);
  const contadoDe = (c) => (c.usa_denominaciones ? totalBilletes : Number(contados[c.caja_id]) || 0);
  const sinContar = turno.cajas.filter((c) => !c.usa_denominaciones && String(contados[c.caja_id] ?? "").trim() === "");

  // Vuelve a leer el turno: otra pantalla pudo vender, gastar o cerrarlo.
  // Si ya no es este turno, la página pasa al estado nuevo con el mensaje.
  const refrescar = async (mensaje) => {
    const r = await api.turnoCaja();
    if (r.turno?.id !== turno.id) {
      onCambio(r, mensaje || `El turno #${turno.numero} se cerró desde otra pantalla.`);
      return false;
    }
    setTurno(r.turno);
    return true;
  };

  // El esperado que se muestra al confirmar es el de ahora, no el de cuando se
  // abrió la pantalla (mientras se contaba pudo haber más ventas).
  const pedirCierre = async () => {
    if (sinContar.length) {
      setError(`Escribe lo contado en: ${sinContar.map((c) => c.caja).join(", ")}.`);
      return;
    }
    setError("");
    try {
      if (await refrescar()) {
        setAbiertas(await api.cuentas().catch(() => []));
        setConfirmando(true);
      }
    } catch (err) {
      setError(err.message);
    }
  };

  const cerrar = async () => {
    setEnviando(true);
    try {
      const cerrado = await api.cerrarTurno(turno.id, {
        contados: Object.fromEntries(turno.cajas.filter((c) => !c.usa_denominaciones).map((c) => [c.caja_id, contadoDe(c)])),
        conteo: Object.fromEntries(Object.entries(cantidades).filter(([, n]) => n > 0)),
        notas: notas || null,
      });
      onCerrado(cerrado);
    } catch (err) {
      setError(err.message);
      setConfirmando(false);
      setEnviando(false);
      refrescar(err.message).catch(() => {});
    }
  };

  const conBilletes = turno.cajas.find((c) => c.usa_denominaciones);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <span className="chip ok">Turno #{turno.numero} abierto · {turno.abierta_por} · {hora(turno.abierta_en)}</span>
        <span className="muted" style={{ fontSize: 14 }}>
          {turno.ventas.cantidad} {turno.ventas.cantidad === 1 ? "venta" : "ventas"} · {fmt(turno.ventas.total)}
          {Number(turno.ventas.fiado) > 0 && ` (a crédito ${fmt(turno.ventas.fiado)})`}
        </span>
        <button type="button" className="btn btn-s" style={{ marginLeft: "auto" }} onClick={() => setMovimiento(true)}>
          Retiro, ingreso o traslado
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "repeat(auto-fit, minmax(280px, 1fr))", gap: 16, alignItems: "start" }}>
        {turno.cajas.map((c) => <ResumenCaja key={c.caja_id} caja={c} />)}
      </div>

      <div className="card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
        <h2 style={{ fontSize: 18 }}>Movimientos del turno</h2>
        <ListaMovimientos movimientos={turno.movimientos} />
      </div>

      <h2 style={{ fontSize: 20, marginTop: 4 }}>Cierre del turno</h2>
      <div style={{ display: "grid", gap: 16, alignItems: "start",
        gridTemplateColumns: conBilletes && !isMobile ? "minmax(0, 1.6fr) minmax(280px, 1fr)" : "minmax(0, 560px)" }}>
        {conBilletes && (
          <ConteoBilletes titulo={`${conBilletes.caja}: billetes y monedas`} denominaciones={denominaciones}
            cantidades={cantidades} setCantidades={setCantidades} />
        )}
        <div className="card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
          {turno.cajas.map((c) => (
            <div key={c.caja_id} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {c.usa_denominaciones ? (
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 10 }}>
                  <span className="lbl">Contado {c.caja}</span>
                  <span className="num" style={{ fontWeight: 700, fontSize: 18 }}>{fmt(totalBilletes)}</span>
                </div>
              ) : (
                <Campo etiqueta={`Contado ${c.caja} ($)`} ayuda={`Esperado ${fmt(c.esperado)}: escribe lo que de verdad hay.`}>
                  <input className="inp num" type="number" min="0" inputMode="numeric" value={contados[c.caja_id] ?? ""}
                    onChange={(e) => { setError(""); setContados((x) => ({ ...x, [c.caja_id]: e.target.value })); }} />
                </Campo>
              )}
              {/* La diferencia aparece cuando se empieza a contar, no antes. */}
              {(c.usa_denominaciones ? totalBilletes > 0 : String(contados[c.caja_id] ?? "").trim() !== "") && (
                <BannerDiferencia etiqueta={`Diferencia ${c.caja}`} contado={contadoDe(c)} esperado={Number(c.esperado)} />
              )}
            </div>
          ))}
          <Campo etiqueta="Notas del cierre (opcional)">
            <textarea className="inp" style={{ height: 70, padding: "10px 12px", resize: "none" }}
              value={notas} onChange={(e) => setNotas(e.target.value)} />
          </Campo>
          <ErrorBanner mensaje={error} />
          <button type="button" className="btn btn-p" style={{ height: 48 }} onClick={pedirCierre}>Cerrar turno</button>
        </div>
      </div>

      {movimiento && (
        <ModalMovimiento turnoId={turno.id} cajas={turno.cajas} onClose={() => setMovimiento(false)}
          onGuardado={(t) => { setTurno(t); setMovimiento(false); }}
          onFallo={(mensaje) => refrescar(mensaje).catch(() => {})} />
      )}
      {confirmando && (
        <Modal titulo={`¿Cerrar el turno #${turno.numero}?`} onClose={() => !enviando && setConfirmando(false)}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {turno.cajas.map((c) => (
              <div key={c.caja_id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10 }}>
                <span>{c.caja}: <span className="num">{fmt(contadoDe(c))}</span></span>
                <span className={`chip ${claseDiferencia(contadoDe(c) - Number(c.esperado))} num`}>
                  {textoDiferencia(contadoDe(c) - Number(c.esperado))}
                </span>
              </div>
            ))}
          </div>
          {abiertas.length > 0 && (
            <div role="alert" style={{ display: "flex", flexDirection: "column", gap: 4, padding: "12px 14px", borderRadius: 12,
              background: "var(--warn-bg)", color: "var(--warn-text)", fontSize: 14 }}>
              <strong>
                {abiertas.length === 1 ? "Hay 1 cuenta abierta" : `Hay ${abiertas.length} cuentas abiertas`} por{" "}
                {fmt(abiertas.reduce((s, c) => s + Number(c.total), 0))} sin cobrar.
              </strong>
              <span style={{ fontSize: 13 }}>
                {abiertas.slice(0, 5).map((c) => c.mesa ? `Mesa ${c.mesa}${c.nombre && c.nombre !== c.mesa ? ` (${c.nombre})` : ""}` : c.nombre).join(" · ")}
                {abiertas.length > 5 && " · …"}
              </span>
              <span style={{ fontSize: 13 }}>
                Quedan abiertas para el siguiente turno. Si ya se fueron, <Link to="/cuentas">cóbralas en Cuentas</Link> antes de cerrar.
              </span>
            </div>
          )}
          {conBilletes && totalBilletes === 0 && (
            <div role="alert" className="error-banner">
              No contaste billetes ni monedas: {conBilletes.caja} se cerrará en $ 0.
            </div>
          )}
          <div className="muted" style={{ fontSize: 13 }}>Un turno cerrado ya no se puede cambiar.</div>
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
            <button type="button" className="btn btn-s" disabled={enviando} onClick={() => setConfirmando(false)}>Volver</button>
            <button type="button" className="btn btn-p" disabled={enviando} onClick={cerrar}>{enviando ? "Cerrando…" : "Cerrar turno"}</button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ── Detalle de un turno cerrado (al cerrar y en el historial) ──────────────

function DetalleTurno({ turno }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div className="muted" style={{ fontSize: 13 }}>
        Abierto por {turno.abierta_por} el {fmtFechaHora(turno.abierta_en)}
        {turno.cerrada_en && ` · cerrado por ${turno.cerrada_por} el ${fmtFechaHora(turno.cerrada_en)}`}
        <br />
        {turno.ventas.cantidad} {turno.ventas.cantidad === 1 ? "venta" : "ventas"} por {fmt(turno.ventas.total)}
        {Number(turno.ventas.fiado) > 0 && ` (a crédito ${fmt(turno.ventas.fiado)})`}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 12 }}>
        {turno.cajas.map((c) => <ResumenCaja key={c.caja_id} caja={c} />)}
      </div>
      {turno.conteo.length > 0 && (
        <div style={{ fontSize: 13 }}>
          <span className="lbl">Billetes y monedas: </span>
          <span className="num">{turno.conteo.map((d) => `${d.cantidad} × ${fmt(d.valor)}`).join(" · ")}</span>
        </div>
      )}
      {turno.movimientos.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <span className="lbl">Movimientos</span>
          <ListaMovimientos movimientos={turno.movimientos} />
        </div>
      )}
      {turno.notas && <div className="muted" style={{ fontSize: 13, whiteSpace: "pre-line" }}>Notas: {turno.notas}</div>}
    </div>
  );
}

function TurnoCerrado({ turno, onListo }) {
  return (
    <div className="card" style={{ padding: 24, display: "flex", flexDirection: "column", gap: 16, maxWidth: 760 }}>
      <h2 style={{ fontSize: 22 }}>Turno #{turno.numero} cerrado</h2>
      <DetalleTurno turno={turno} />
      <button type="button" className="btn btn-p" style={{ alignSelf: "flex-start" }} onClick={onListo}>Listo</button>
    </div>
  );
}

// ── Historial ──────────────────────────────────────────────────────────────

function Historial() {
  const [filtros, setFiltros] = useState({ desde: "", hasta: "" });
  const [turnos, setTurnos] = useState([]);
  const [detalle, setDetalle] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.historialCaja(filtros)
      .then((r) => { setError(""); setTurnos(r); })
      .catch((err) => setError(err.message));
  }, [filtros]);

  const verDetalle = (id) => api.detalleTurno(id).then(setDetalle).catch((err) => setError(err.message));
  const cambiar = (campo) => (e) => setFiltros((f) => ({ ...f, [campo]: e.target.value }));
  const columnas = "60px 130px 130px 120px 110px 1fr";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
        <Campo etiqueta="Desde"><input className="inp" type="date" value={filtros.desde} onChange={cambiar("desde")} /></Campo>
        <Campo etiqueta="Hasta"><input className="inp" type="date" value={filtros.hasta} onChange={cambiar("hasta")} /></Campo>
      </div>
      <ErrorBanner mensaje={error} />
      <div className="card tabla">
        <div className="th" style={{ gridTemplateColumns: columnas, minWidth: 760 }}>
          <span>#</span><span>Apertura</span><span>Cierre</span><span>Abrió</span><span className="r">Ventas</span><span>Diferencias</span>
        </div>
        {turnos.map((t) => (
          <div key={t.id} className="tr" style={{ gridTemplateColumns: columnas, minWidth: 760, cursor: "pointer" }} onClick={() => verDetalle(t.id)}>
            <span className="num">{t.numero}</span>
            <span className="num">{fmtFechaHora(t.abierta_en)}</span>
            <span className="num muted">{t.cerrada_en ? fmtFechaHora(t.cerrada_en) : <span className="chip ok">Abierto</span>}</span>
            <span>{t.abierta_por}</span>
            <span className="r num">{fmt(t.ventas)}</span>
            <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {t.cerrada_en && (t.cajas || []).map((c) => (
                <span key={c.caja} className={`chip ${claseDiferencia(c.diferencia)} num`}>{c.caja}: {textoDiferencia(c.diferencia)}</span>
              ))}
            </span>
          </div>
        ))}
        {turnos.length === 0 && <div className="muted" style={{ padding: 20 }}>Sin turnos en el rango.</div>}
      </div>
      {detalle && (
        <Modal titulo={`Turno #${detalle.numero}`} ancho={760} onClose={() => setDetalle(null)}>
          <DetalleTurno turno={detalle} />
        </Modal>
      )}
    </div>
  );
}

// ── Página ─────────────────────────────────────────────────────────────────

export default function Caja() {
  const { puede } = useAuth();
  const isMobile = useIsMobile();
  const [vista, setVista] = useState("turno");
  const [estado, setEstado] = useState(null); // {turno, cajas} de /caja/turno
  const [cerrado, setCerrado] = useState(null);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState(""); // el turno cambió desde otra pantalla

  const cargar = useCallback(() => {
    api.turnoCaja()
      .then((r) => { setError(""); setEstado(r); })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => { cargar(); }, [cargar]);

  let contenido;
  if (vista === "hist") contenido = <Historial />;
  else if (cerrado) contenido = <TurnoCerrado turno={cerrado} onListo={() => { setCerrado(null); cargar(); }} />;
  else if (!estado) contenido = !error && <div className="muted">Cargando…</div>;
  else if (!estado.turno) contenido = <Apertura cajas={estado.cajas} onAbierta={(t) => { setAviso(""); setEstado({ turno: t }); }} />;
  else {
    contenido = (
      <TurnoAbierto key={estado.turno.id} turno={estado.turno} setTurno={(t) => setEstado({ turno: t })}
        onCerrado={(t) => { setAviso(""); setCerrado(t); setEstado(null); }}
        onCambio={(r, mensaje) => { setAviso(mensaje); setEstado(r); }} />
    );
  }

  return (
    <>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Caja</h1>
          {!isMobile && <div className="muted" style={{ fontSize: 14 }}>Apertura, movimientos y cierre del turno</div>}
        </div>
        {puede("caja.historial") && (
          <div className="seg" role="tablist" aria-label="Vista de caja">
            <button type="button" role="tab" aria-selected={vista === "turno"} className={vista === "turno" ? "on" : ""} onClick={() => { setVista("turno"); setAviso(""); cargar(); }}>Turno actual</button>
            <button type="button" role="tab" aria-selected={vista === "hist"} className={vista === "hist" ? "on" : ""} onClick={() => setVista("hist")}>Historial</button>
          </div>
        )}
      </header>
      {error && vista === "turno" && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>{error}</span>
          <button type="button" className="btn btn-s" onClick={cargar}>Reintentar</button>
        </div>
      )}
      {vista === "turno" && <ErrorBanner mensaje={aviso} />}
      {contenido}
    </>
  );
}
