import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { fmt } from "../format";
import { useIsMobile } from "../useMediaQuery";

const DENOMINACIONES = [100000, 50000, 20000, 10000, 5000, 2000, 1000, 500, 200, 100, 50];

function AperturaCaja({ onAbierta }) {
  const [montoBase, setMontoBase] = useState("");
  const [montoBaseDigital, setMontoBaseDigital] = useState("");
  const [notas, setNotas] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setEnviando(true);
    try {
      await api.abrirCaja({
        monto_base: Number(montoBase) || 0,
        monto_base_digital: Number(montoBaseDigital) || 0,
        notas: notas || null,
      });
      onAbierta();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={submit} className="card" style={{ maxWidth: 420, padding: 24, display: "flex", flexDirection: "column", gap: 16 }}>
      <h2 style={{ fontSize: 22 }}>Abrir caja</h2>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <label className="lbl" htmlFor="mb">Base inicial efectivo ($)</label>
        <input className="inp num" id="mb" type="number" min="0" value={montoBase}
          onChange={(e) => setMontoBase(e.target.value)} required />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <label className="lbl" htmlFor="mbd">Saldo inicial digital ($)</label>
        <input className="inp num" id="mbd" type="number" min="0" value={montoBaseDigital}
          onChange={(e) => setMontoBaseDigital(e.target.value)} />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <label className="lbl" htmlFor="nt">Notas (opcional)</label>
        <textarea className="inp" id="nt" style={{ height: 80, padding: "10px 12px", resize: "none" }}
          value={notas} onChange={(e) => setNotas(e.target.value)} />
      </div>
      {error && <div className="error-banner">{error}</div>}
      <button type="submit" className="btn btn-p" disabled={enviando} style={{ height: 48 }}>
        {enviando ? "Abriendo…" : "Abrir caja"}
      </button>
    </form>
  );
}

function TarjetaResumen({ titulo, color, base, ventas, abonos, egresos, esperado, chip }) {
  return (
    <div className="card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
        <h2 style={{ fontSize: 18 }}>{titulo}</h2>
        <span className="chip neu">{chip}</span>
      </div>
      <div className="kv" style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "6px 0" }}>
        <span className="muted">Base inicial</span><span className="num">{fmt(base)}</span>
      </div>
      <div className="kv" style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "6px 0" }}>
        <span className="muted">Ventas</span><span className="num">{fmt(ventas)}</span>
      </div>
      {abonos > 0 && (
        <div className="kv" style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "6px 0" }}>
          <span className="muted">Abonos de fiado</span><span className="num">{fmt(abonos)}</span>
        </div>
      )}
      <div className="kv" style={{ display: "flex", justifyContent: "space-between", fontSize: 14, padding: "6px 0" }}>
        <span className="muted">Gastos / egresos</span>
        <span className="num" style={{ color: egresos > 0 ? "#8E2A20" : undefined }}>− {fmt(egresos)}</span>
      </div>
      <div style={{ height: 1, background: "var(--border)", margin: "8px 0" }} />
      <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700, fontSize: 16 }}>
        <span>Esperado</span><span className="num">{fmt(esperado)}</span>
      </div>
    </div>
  );
}

function BannerDiferencia({ etiqueta, contado, esperado }) {
  const dif = contado - esperado;
  const bg = dif === 0 ? "var(--ok-bg)" : dif < 0 ? "var(--danger-bg)" : "var(--warn-bg)";
  const color = dif === 0 ? "var(--ok-text)" : dif < 0 ? "#8E2A20" : "var(--warn-text)";
  const texto = dif === 0 ? "$ 0 · cuadra" : (dif > 0 ? "Sobran " : "Faltan ") + fmt(Math.abs(dif));
  return (
    <div style={{ borderRadius: 12, padding: 14, background: bg, display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 13, fontWeight: 600, color }}>{etiqueta}</span>
      <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 22, fontWeight: 700, color }}>{texto}</span>
    </div>
  );
}

function CierreCaja({ onCerrada }) {
  const isMobile = useIsMobile();
  const [preview, setPreview] = useState(null);
  const [cantidades, setCantidades] = useState(() => Object.fromEntries(DENOMINACIONES.map((d) => [d, 0])));
  const [contadoDigital, setContadoDigital] = useState("");
  const [notas, setNotas] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    // El campo de contado digital se deja VACÍO a propósito (no se precarga
    // con esperado_digital): el cajero debe escribir lo que de verdad ve en
    // Nequi/Daviplata, para no ocultar un faltante real con un valor que
    // siempre cuadra por defecto.
    api.previewCierre().then(setPreview).catch((err) => setError(err.message));
  }, []);

  const cambiar = (d, delta) => setCantidades((c) => ({ ...c, [d]: Math.max(0, c[d] + delta) }));
  const contadoEfectivo = DENOMINACIONES.reduce((a, d) => a + d * cantidades[d], 0);

  const cerrar = async () => {
    if (contadoDigital.trim() === "") {
      setError("Ingresa el saldo digital contado antes de cerrar.");
      return;
    }
    setError("");
    setEnviando(true);
    try {
      await api.cerrarCaja({
        denominaciones: Object.fromEntries(DENOMINACIONES.map((d) => [String(d), cantidades[d]])),
        digital: Number(contadoDigital),
        notas: notas || null,
      });
      onCerrada();
    } catch (err) {
      setError(err.message);
    } finally {
      setEnviando(false);
    }
  };

  if (!preview) return error ? <div className="error-banner">{error}</div> : <div className="muted">Cargando…</div>;

  return (
    <div style={{ display: "grid", gridTemplateColumns: isMobile ? "1fr" : "1fr 1fr 1.25fr", gap: 16, flexGrow: 1, minHeight: 0 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <TarjetaResumen titulo="Caja efectivo" chip={`Abierta ${preview.sesion.apertura?.slice(11, 16)}`}
          base={preview.sesion.monto_base} ventas={preview.ventas.efectivo} abonos={preview.abonos.efectivo}
          egresos={preview.egresos.efectivo} esperado={preview.esperado_efectivo} />
        <BannerDiferencia etiqueta="Diferencia con lo contado" contado={contadoEfectivo} esperado={preview.esperado_efectivo} />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <TarjetaResumen titulo="Caja digital" chip="Nequi · Daviplata · Tarjeta"
          base={preview.sesion.monto_base_digital} ventas={preview.ventas.digital} abonos={preview.abonos.digital}
          egresos={preview.egresos.digital} esperado={preview.esperado_digital} />
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label className="lbl" htmlFor="dig">Saldo actual digital ($)</label>
          <input className="inp num" id="dig" type="number" value={contadoDigital}
            onChange={(e) => setContadoDigital(e.target.value)} />
        </div>
        <BannerDiferencia etiqueta="Diferencia digital" contado={Number(contadoDigital) || 0} esperado={preview.esperado_digital} />
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label className="lbl" htmlFor="nt">Notas (opcional)</label>
          <textarea className="inp" id="nt" style={{ height: 80, padding: "10px 12px", resize: "none" }}
            value={notas} onChange={(e) => setNotas(e.target.value)} />
        </div>
      </div>

      <div className="card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ fontSize: 18 }}>Conteo de denominaciones</h2>
          <span className="muted" style={{ fontSize: 13 }}>Pesos colombianos</span>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", columnGap: 20, rowGap: 6 }}>
          {DENOMINACIONES.map((d) => (
            <div key={d} style={{ display: "flex", alignItems: "center", gap: 8, padding: "4px 0", borderBottom: "1px solid var(--neu-bg)" }}>
              <span className="num" style={{ fontWeight: 600, fontSize: 14, flexGrow: 1 }}>{fmt(d)}</span>
              <button type="button" className="step" onClick={() => cambiar(d, -1)}>−</button>
              <span className="num" style={{ width: 26, textAlign: "center", fontWeight: 700 }}>{cantidades[d]}</span>
              <button type="button" className="step" onClick={() => cambiar(d, 1)}>+</button>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", paddingTop: 6 }}>
          <span style={{ fontWeight: 600 }}>Contado efectivo</span>
          <span className="num" style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontSize: 26, fontWeight: 700 }}>{fmt(contadoEfectivo)}</span>
        </div>
        {error && <div className="error-banner">{error}</div>}
        <button type="button" className="btn btn-p" style={{ height: 48 }} disabled={enviando} onClick={cerrar}>
          {enviando ? "Cerrando…" : "Cerrar caja"}
        </button>
      </div>
    </div>
  );
}

function Historial() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [sesiones, setSesiones] = useState([]);
  const [detalle, setDetalle] = useState(null);
  const [error, setError] = useState("");

  const buscar = async () => {
    setError("");
    try {
      setSesiones(await api.historialCaja(desde || null, hasta || null));
    } catch (err) {
      setError(err.message);
    }
  };

  useEffect(() => { buscar(); }, []);

  const verDetalle = async (id) => {
    try {
      setDetalle(await api.detalleSesionCaja(id));
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "end", flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label className="lbl" htmlFor="d1">Desde</label>
          <input className="inp" id="d1" type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <label className="lbl" htmlFor="d2">Hasta</label>
          <input className="inp" id="d2" type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </div>
        <button type="button" className="btn btn-s" onClick={buscar}>Buscar</button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div style={{ display: "flex", gap: 16 }}>
        <div className="card" style={{ flexGrow: 1, overflow: "hidden" }}>
          <div className="th" style={{ gridTemplateColumns: "90px 1fr 1fr 100px 110px 110px" }}>
            <span>Apertura</span><span>Cierre</span><span>Cajero</span><span className="r">Ventas</span><span className="r">Dif. efec.</span><span className="r">Dif. dig.</span>
          </div>
          {sesiones.map((s) => (
            <div key={s.id} className="tr" style={{ gridTemplateColumns: "90px 1fr 1fr 100px 110px 110px", cursor: "pointer" }}
              onClick={() => verDetalle(s.id)}>
              <span className="num">{s.apertura?.slice(0, 10)}</span>
              <span className="num muted">{s.cierre?.slice(11, 16)}</span>
              <span>{s.cajero}</span>
              <span className="r num">{fmt(s.total_ventas)}</span>
              <span className="r"><span className={`chip ${s.diferencia === 0 ? "ok" : s.diferencia < 0 ? "bad" : "warn"} num`}>{fmt(s.diferencia)}</span></span>
              <span className="r"><span className={`chip ${s.diferencia_digital === 0 ? "ok" : s.diferencia_digital < 0 ? "bad" : "warn"} num`}>{fmt(s.diferencia_digital)}</span></span>
            </div>
          ))}
          {sesiones.length === 0 && <div className="muted" style={{ padding: 20 }}>Sin sesiones en el rango.</div>}
        </div>

        {detalle && (
          <div className="card" style={{ width: 320, flexShrink: 0, padding: 20, display: "flex", flexDirection: "column", gap: 8 }}>
            <h2 style={{ fontSize: 18 }}>Sesión #{detalle.id}</h2>
            <div className="muted" style={{ fontSize: 13 }}>{detalle.cajero} · {detalle.apertura} → {detalle.cierre}</div>
            <div style={{ height: 1, background: "var(--border)", margin: "6px 0" }} />
            <div style={{ fontSize: 14, display: "flex", justifyContent: "space-between" }}><span>Base efectivo</span><span className="num">{fmt(detalle.monto_base)}</span></div>
            <div style={{ fontSize: 14, display: "flex", justifyContent: "space-between" }}><span>Ventas efectivo</span><span className="num">{fmt(detalle.total_efectivo)}</span></div>
            <div style={{ fontSize: 14, display: "flex", justifyContent: "space-between" }}><span>Contado</span><span className="num">{fmt(detalle.monto_cierre)}</span></div>
            <div style={{ fontSize: 14, display: "flex", justifyContent: "space-between", fontWeight: 700 }}><span>Diferencia</span><span className="num">{fmt(detalle.diferencia)}</span></div>
            <div style={{ height: 1, background: "var(--border)", margin: "6px 0" }} />
            <div style={{ fontSize: 14, display: "flex", justifyContent: "space-between" }}><span>Base digital</span><span className="num">{fmt(detalle.monto_base_digital)}</span></div>
            <div style={{ fontSize: 14, display: "flex", justifyContent: "space-between" }}><span>Ventas digitales</span><span className="num">{fmt(detalle.total_digital)}</span></div>
            <div style={{ fontSize: 14, display: "flex", justifyContent: "space-between", fontWeight: 700 }}><span>Dif. digital</span><span className="num">{fmt(detalle.diferencia_digital)}</span></div>
            {detalle.notas && <div className="muted" style={{ fontSize: 13, marginTop: 8 }}>Notas: {detalle.notas}</div>}
          </div>
        )}
      </div>
    </div>
  );
}

export default function Caja() {
  const { usuario } = useAuth();
  const isMobile = useIsMobile();
  const [vista, setVista] = useState("turno");
  const [sesion, setSesion] = useState(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");

  const cargarSesion = () => {
    setCargando(true);
    setError("");
    api.cajaSesionActiva()
      .then((r) => setSesion(r.sesion))
      .catch((err) => setError(err.message))
      .finally(() => setCargando(false));
  };

  useEffect(() => { cargarSesion(); }, []);

  return (
    <>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Caja</h1>
          {!isMobile && <div className="muted" style={{ fontSize: 14 }}>Apertura y cierre de turno</div>}
        </div>
        {usuario?.rol === "admin" && !cargando && (
          <div className="seg" role="tablist" aria-label="Vista de caja">
            <button type="button" role="tab" className={vista === "turno" ? "on" : ""} onClick={() => setVista("turno")}>Turno actual</button>
            <button type="button" role="tab" className={vista === "hist" ? "on" : ""} onClick={() => setVista("hist")}>Historial</button>
          </div>
        )}
      </header>

      {error && (
        <div className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>{error}</span>
          {vista === "turno" && (
            <button type="button" className="btn btn-s" onClick={cargarSesion}>Reintentar</button>
          )}
        </div>
      )}

      {vista === "hist" ? (
        <Historial />
      ) : cargando ? (
        <div className="muted">Cargando…</div>
      ) : sesion === null ? (
        <AperturaCaja onAbierta={cargarSesion} />
      ) : (
        <CierreCaja onCerrada={cargarSesion} />
      )}
    </>
  );
}
