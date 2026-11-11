import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import Modal, { Campo, ErrorBanner } from "../components/Modal";
import ModalEgreso from "../components/ModalEgreso";
import { fmt, fmtFechaHora } from "../format";
import { useIsMobile } from "../useMediaQuery";
import { useTurno } from "../useTurno";

const hoy = () => new Date().toLocaleDateString("en-CA"); // AAAA-MM-DD en la hora local

const TIPOS = [["", "Todo"], ["gasto", "Gastos"], ["compra", "Pagos de compras"]];

function quien(e) {
  if (e.tipo === "compra") return `Compra #${e.compra_numero} · ${e.beneficiario}`;
  return [e.categoria, e.beneficiario].filter(Boolean).join(" · ");
}

function DetalleEgreso({ egreso, turno, onClose, onAnulado }) {
  const { puede } = useAuth();
  const [motivo, setMotivo] = useState("");
  const [anulando, setAnulando] = useState(false);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const anular = async (e) => {
    e.preventDefault();
    setEnviando(true);
    setError("");
    try {
      onAnulado(await api.anularEgreso(egreso.id, turno.id, motivo.trim()));
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <Modal titulo={egreso.concepto} onClose={onClose} ancho={500}>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <span className="muted">{quien(egreso)}</span>
        <span className="muted" style={{ fontSize: 13 }}>
          {fmtFechaHora(egreso.creado_en)} · turno #{egreso.turno} · {egreso.usuario}
        </span>
        {egreso.pagos.map((p, i) => (
          <div key={i} style={{ display: "flex", justifyContent: "space-between" }}>
            <span>{p.metodo} <span className="muted">(caja {p.caja})</span></span>
            <span className="num">{fmt(p.monto)}</span>
          </div>
        ))}
        {Number(egreso.cruzado) > 0 && (
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span>Cruce contra su fiado</span><span className="num">{fmt(egreso.cruzado)}</span>
          </div>
        )}
        <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700, borderTop: "1px solid var(--border-2)", paddingTop: 8 }}>
          <span>Total</span><span className="num">{fmt(egreso.monto)}</span>
        </div>
        {egreso.notas && <span style={{ fontSize: 14 }}>{egreso.notas}</span>}
        {egreso.anulado && (
          <div role="status" className="error-banner" style={{ flexDirection: "column", alignItems: "flex-start", gap: 4 }}>
            <strong>Anulado: {egreso.motivo_anulacion}</strong>
            <span style={{ fontSize: 13 }}>{fmtFechaHora(egreso.anulado_en)} · {egreso.anulado_por} · la plata volvió en el turno #{egreso.turno_anulacion}</span>
          </div>
        )}
      </div>

      {!egreso.anulado && puede("gastos.anular") && (anulando ? (
        <form onSubmit={anular} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <span style={{ fontSize: 14 }}>
            {Number(egreso.pagado) > 0 && <>Vuelven <strong className="num">{fmt(egreso.pagado)}</strong> a las cajas en el turno #{turno?.numero}. </>}
            {Number(egreso.cruzado) > 0 && <>El cruce de {fmt(egreso.cruzado)} deja de contar y esa deuda reaparece. </>}
          </span>
          <Campo etiqueta="Motivo">
            <input className="inp" autoFocus value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </Campo>
          <ErrorBanner mensaje={error} />
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
            <button type="button" className="btn btn-s" onClick={() => setAnulando(false)} disabled={enviando}>Volver</button>
            <button type="submit" className="btn btn-d" disabled={enviando || !motivo.trim()}>Anular</button>
          </div>
        </form>
      ) : (
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", alignItems: "center", flexWrap: "wrap" }}>
          {!turno && <span className="muted" style={{ fontSize: 13 }}>Para anular abre el turno en <Link to="/caja">Caja</Link>.</span>}
          <button type="button" className="btn btn-d" disabled={!turno} onClick={() => setAnulando(true)}>Anular</button>
        </div>
      ))}
    </Modal>
  );
}

// Salidas de plata (gastos y pagos de compras) por rango de fechas.
export default function Gastos() {
  const { puede } = useAuth();
  const historial = puede("reportes.ver"); // sin él, el servidor solo devuelve el turno abierto
  const isMobile = useIsMobile();
  const { turno, error: errorTurno, recargar: recargarTurno } = useTurno();
  const [filtros, setFiltros] = useState(() => ({ desde: hoy(), hasta: hoy(), tipo: "" }));
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [registrando, setRegistrando] = useState(false);
  const [detalle, setDetalle] = useState(null);
  const ultima = useRef(0);

  const cargar = useCallback(() => {
    const mia = ++ultima.current;
    api.egresos(filtros)
      .then((r) => { if (mia === ultima.current) { setError(""); setLista(r); } })
      .catch((err) => mia === ultima.current && setError(err.message));
  }, [filtros]);

  useEffect(() => { cargar(); }, [cargar]);

  const vigentes = (lista || []).filter((e) => !e.anulado);
  const total = vigentes.reduce((a, e) => a + Number(e.monto), 0);
  const filtro = (k) => (e) => setFiltros((f) => ({ ...f, [k]: e.target.value }));

  return (
    <>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Gastos</h1>
          {!isMobile && <div className="muted" style={{ fontSize: 14 }}>Toda la plata que sale: gastos, nómina y pagos a proveedores</div>}
        </div>
        <button type="button" className="btn btn-p" disabled={!turno} onClick={() => setRegistrando(true)}>+ Registrar gasto</button>
      </header>
      {turno === null && <span className="muted" style={{ fontSize: 14, marginTop: -8 }}>Para registrar gastos abre el turno en <Link to="/caja">Caja</Link>.</span>}
      {errorTurno && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>No se pudo revisar el turno de caja: {errorTurno}</span>
          <button type="button" className="btn btn-s" onClick={recargarTurno}>Reintentar</button>
        </div>
      )}

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        {historial ? (
          <>
            <Campo etiqueta="Desde"><input className="inp" type="date" value={filtros.desde} onChange={filtro("desde")} /></Campo>
            <Campo etiqueta="Hasta"><input className="inp" type="date" value={filtros.hasta} onChange={filtro("hasta")} /></Campo>
          </>
        ) : (
          <span className="muted" style={{ fontSize: 14, alignSelf: "center" }}>
            {turno ? `Egresos del turno #${turno.numero}` : "Sin turno abierto"}
          </span>
        )}
        <div className="seg" role="tablist" aria-label="Tipo de egreso" style={{ maxWidth: "100%", overflowX: "auto" }}>
          {TIPOS.map(([k, etiqueta]) => (
            <button key={k} type="button" role="tab" aria-selected={filtros.tipo === k} className={filtros.tipo === k ? "on" : ""}
              onClick={() => setFiltros((f) => ({ ...f, tipo: k }))}>{etiqueta}</button>
          ))}
        </div>
      </div>
      {error && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>{error}</span>
          <button type="button" className="btn btn-s" onClick={cargar}>Reintentar</button>
        </div>
      )}
      {lista && (
        <div className="muted num" style={{ fontSize: 14 }}>
          {vigentes.length} {vigentes.length === 1 ? "egreso" : "egresos"} · total <strong style={{ color: "var(--text)" }}>{fmt(total)}</strong>
          {lista.length > vigentes.length && ` · ${lista.length - vigentes.length} anulado(s) no suman`}
        </div>
      )}

      <div className="card" style={{ overflow: "hidden" }}>
        {!lista && !error && <div className="muted" style={{ padding: 16 }}>Cargando…</div>}
        {lista?.length === 0 && <div className="muted" style={{ padding: 16 }}>{historial ? "No hay egresos en esas fechas." : "No hay egresos en el turno."}</div>}
        {(lista || []).map((e) => (
          <button key={e.id} type="button" onClick={() => api.egreso(e.id).then(setDetalle).catch((err) => setError(err.message))}
            style={{
              width: "100%", border: 0, borderBottom: "1px solid var(--border-2)", background: "#fff", textAlign: "left",
              font: "inherit", color: "inherit", cursor: "pointer", padding: "12px 16px", display: "flex", gap: 12, alignItems: "center",
              opacity: e.anulado ? 0.55 : 1,
            }}>
            <span style={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
              <strong style={{ overflowWrap: "anywhere", textDecoration: e.anulado ? "line-through" : "none" }}>{e.concepto}</strong>
              <span className="muted" style={{ fontSize: 12, overflowWrap: "anywhere" }}>
                {quien(e)} · {fmtFechaHora(e.creado_en)}
                {e.metodos && ` · ${e.metodos}`}{Number(e.cruzado) > 0 && " · cruce de cuentas"}
              </span>
            </span>
            {e.anulado && <span className="chip neu">Anulado</span>}
            <span className="num" style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{fmt(e.monto)}</span>
          </button>
        ))}
      </div>

      {registrando && (
        <ModalEgreso turno={turno} onClose={() => setRegistrando(false)}
          onHecho={() => {
            setRegistrando(false);
            // Si el rango no llega a hoy se amplía (el efecto recarga); si llega, se recarga aquí.
            if (filtros.hasta < hoy()) setFiltros((f) => ({ ...f, hasta: hoy() }));
            else cargar();
          }} />
      )}
      {detalle && (
        <DetalleEgreso egreso={detalle} turno={turno} onClose={() => setDetalle(null)}
          onAnulado={(d) => { setDetalle(d); cargar(); }} />
      )}
    </>
  );
}
