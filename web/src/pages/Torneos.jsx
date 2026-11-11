import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import BuscarArticulo from "../components/BuscarArticulo";
import BuscarTercero from "../components/BuscarTercero";
import Modal, { Campo, ErrorBanner, Seccion } from "../components/Modal";
import { centavos, fmt, fmtCant, fmtFechaHora } from "../format";
import { useIsMobile } from "../useMediaQuery";
import { useTurno } from "../useTurno";

const FIADO = "fiado";
const GRATIS = "gratis";
const haceDias = (n) => new Date(Date.now() - n * 86400000).toLocaleDateString("en-CA");
const hoy = () => new Date().toLocaleDateString("en-CA");

function ModalTorneo({ turno, onClose, onRegistrado }) {
  const [juegos, setJuegos] = useState([]);
  const [metodos, setMetodos] = useState([]);
  const [datos, setDatos] = useState({ nombre: "", juego_id: "", precio: "", notas: "" });
  const [jugadores, setJugadores] = useState([]); // [{clave, cliente_id?, alias?, nombre, forma}]
  const [alias, setAlias] = useState("");
  const [premios, setPremios] = useState([]); // [{producto_id, nombre, cantidad}]
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);
  const turnoInicial = useRef(turno);

  useEffect(() => {
    const deTurno = turnoInicial.current;
    api.catalogo("juegos").then((js) => {
      setJuegos(js);
      setDatos((d) => ({ ...d, juego_id: d.juego_id || js[0]?.id || "" }));
    }).catch((err) => setError(err.message));
    if (deTurno) {
      api.metodosPago().then((ms) => setMetodos(ms.filter((m) => deTurno.cajas.includes(m.caja_id)))).catch((err) => setError(err.message));
      api.inscripcionTorneo().then((s) => setDatos((d) => ({ ...d, precio: d.precio || String(Number(s.precio)) })))
        .catch((err) => setError(err.message));
    }
  }, []);

  // Un jugador nuevo entra con la forma del último (o el primer método; sin turno, gratis).
  const formaInicial = (esCliente) => {
    const ultima = jugadores[jugadores.length - 1]?.forma;
    if (ultima && (ultima !== FIADO || esCliente)) return ultima;
    return metodos[0]?.id ?? GRATIS;
  };
  const agregarCliente = (t) => {
    if (jugadores.some((j) => j.cliente_id === t.id)) return setError(`${t.nombre} ya está inscrito.`);
    setError("");
    setJugadores((js) => [...js, { clave: t.id, cliente_id: t.id, nombre: t.nombre, forma: formaInicial(true) }]);
  };
  const agregarAlias = () => {
    const nombre = alias.trim();
    if (!nombre) return;
    setJugadores((js) => [...js, { clave: `${nombre}-${Date.now()}`, alias: nombre, nombre, forma: formaInicial(false) }]);
    setAlias("");
  };
  const cambiarJugador = (i, cambios) => setJugadores((js) => js.map((j, k) => (k === i ? { ...j, ...cambios } : j)));

  const precio = centavos(Number(datos.precio) || 0);
  const pagan = jugadores.filter((j) => j.forma !== GRATIS);
  const porForma = {};
  pagan.forEach((j) => {
    const nombre = j.forma === FIADO ? "Fiado" : metodos.find((m) => m.id === j.forma)?.nombre;
    porForma[nombre] = (porForma[nombre] || 0) + precio;
  });

  let bloqueo = "";
  if (!datos.nombre.trim()) bloqueo = "Escribe el nombre del torneo.";
  else if (!datos.juego_id) bloqueo = "Elige el juego.";
  else if (jugadores.length === 0) bloqueo = "Agrega los jugadores.";
  else if (pagan.length > 0 && !(precio > 0)) bloqueo = "Escribe el precio de la inscripción.";
  else if (premios.some((p) => !(Number(p.cantidad) > 0))) bloqueo = "Cada premio lleva una cantidad mayor que cero.";

  const registrar = async (e) => {
    e.preventDefault();
    if (bloqueo) return;
    setEnviando(true);
    setError("");
    try {
      const r = await api.registrarTorneo({
        nombre: datos.nombre.trim(), juego_id: datos.juego_id, notas: datos.notas.trim() || null,
        sesion_id: pagan.length ? turno.id : null, precio: pagan.length ? precio : null,
        participantes: jugadores.map((j) => ({
          ...(j.cliente_id ? { cliente_id: j.cliente_id } : { alias: j.alias }),
          forma: j.forma === FIADO || j.forma === GRATIS ? j.forma : "pago",
          metodo_pago_id: j.forma === FIADO || j.forma === GRATIS ? null : j.forma,
        })),
        premios: premios.map((p) => ({ producto_id: p.producto_id, cantidad: Math.round(Number(p.cantidad) * 1000) / 1000 })),
      });
      onRegistrado(r);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  const campo = (k) => (e) => setDatos((d) => ({ ...d, [k]: e.target.value }));
  return (
    <Modal titulo="Registrar torneo" onClose={() => !enviando && onClose()} ancho={680}>
      <form onSubmit={registrar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 12 }}>
          <Campo etiqueta="Nombre"><input className="inp" autoFocus value={datos.nombre} placeholder="Ej.: Yugi semanal" onChange={campo("nombre")} /></Campo>
          <Campo etiqueta="Juego">
            <select className="inp" value={datos.juego_id} onChange={campo("juego_id")}>
              {juegos.map((j) => <option key={j.id} value={j.id}>{j.nombre}</option>)}
            </select>
          </Campo>
          {turno && (
            <Campo etiqueta="Inscripción">
              <input className="inp num" type="number" min="0" step="any" inputMode="decimal" value={datos.precio} onChange={campo("precio")} />
            </Campo>
          )}
        </div>
        {!turno && <span className="muted" style={{ fontSize: 13 }}>Sin turno abierto solo se registran jugadores gratis. Para cobrar inscripciones abre el turno en <Link to="/caja">Caja</Link>.</span>}

        <Seccion etiqueta={`Jugadores (${jugadores.length})`}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 8 }}>
            <BuscarTercero rol="cliente" placeholder="Agregar cliente registrado" onElegir={agregarCliente} />
            <div style={{ display: "flex", gap: 8 }}>
              <input className="inp" aria-label="Nombre del jugador" placeholder="O escribe un nombre" value={alias}
                onChange={(e) => setAlias(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); agregarAlias(); } }} />
              <button type="button" className="btn btn-s" onClick={agregarAlias} disabled={!alias.trim()}>Agregar</button>
            </div>
          </div>
          {jugadores.map((j, i) => (
            <div key={j.clave} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 150px auto", gap: 8, alignItems: "center" }}>
              <span style={{ overflowWrap: "anywhere" }}>
                {j.nombre}{j.cliente_id && <span className="muted" style={{ fontSize: 12 }}> · cliente</span>}
              </span>
              <select className="inp" aria-label={`Pago de ${j.nombre}`} value={j.forma} onChange={(e) => cambiarJugador(i, { forma: e.target.value })}>
                {metodos.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
                {turno && j.cliente_id && <option value={FIADO}>Fiado</option>}
                <option value={GRATIS}>Gratis</option>
              </select>
              <button type="button" className="btn btn-g" aria-label={`Quitar a ${j.nombre}`} onClick={() => setJugadores((js) => js.filter((_, k) => k !== i))}>✕</button>
            </div>
          ))}
        </Seccion>

        <Seccion etiqueta="Premios entregados (salen del inventario)">
          {/* Solo productos de tienda: son los que tienen stock y salen del inventario. */}
          <BuscarArticulo tipo="producto" filtros={{ categoria_tipo: "tienda" }} etiqueta="Buscar premio" placeholder="Buscar producto para el premio"
            derecha={(a) => `Stock ${fmtCant(a.stock)}`} onElegir={(a) => premios.some((p) => p.producto_id === a.id)
            ? setError(`${a.nombre} ya está en los premios: cambia su cantidad.`)
            : setPremios((ps) => [...ps, { producto_id: a.id, nombre: a.nombre, cantidad: "1" }])} />
          {premios.map((p, i) => (
            <div key={p.producto_id} style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 100px auto", gap: 8, alignItems: "center" }}>
              <span style={{ overflowWrap: "anywhere" }}>{p.nombre}</span>
              <input className="inp num" type="number" min="0" step="any" inputMode="decimal" aria-label={`Cantidad de ${p.nombre}`} value={p.cantidad}
                onChange={(e) => setPremios((ps) => ps.map((x, k) => (k === i ? { ...x, cantidad: e.target.value } : x)))} />
              <button type="button" className="btn btn-g" aria-label={`Quitar premio ${p.nombre}`} onClick={() => setPremios((ps) => ps.filter((_, k) => k !== i))}>✕</button>
            </div>
          ))}
        </Seccion>
        <Campo etiqueta="Notas (opcional)"><input className="inp" value={datos.notas} onChange={campo("notas")} /></Campo>

        <div className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 4, background: "var(--surface-2)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontWeight: 700 }}>
            <span>{jugadores.length} jugador(es){jugadores.length > pagan.length && `, ${jugadores.length - pagan.length} gratis`}</span>
            <span className="num">{fmt(pagan.length * precio)}</span>
          </div>
          {Object.entries(porForma).map(([nombre, monto]) => (
            <div key={nombre} className="muted num" style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
              <span>{nombre}</span><span>{fmt(monto)}</span>
            </div>
          ))}
        </div>
        {bloqueo && (datos.nombre || jugadores.length > 0) && <div className="muted" role="status" style={{ fontSize: 14 }}>{bloqueo}</div>}
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-p" disabled={!!bloqueo || enviando}>Registrar torneo</button>
        </div>
      </form>
    </Modal>
  );
}

function DetalleTorneo({ torneo, onClose }) {
  return (
    <Modal titulo={torneo.nombre} onClose={onClose} ancho={560}>
      <span className="muted" style={{ fontSize: 14 }}>
        {torneo.juego} · {fmtFechaHora(torneo.realizado_en)} · {torneo.usuario}
        {torneo.venta_numero && ` · venta #${torneo.venta_numero}`}
      </span>
      {torneo.notas && <span style={{ fontSize: 14 }}>{torneo.notas}</span>}
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <span>Recaudado <strong className="num">{fmt(torneo.recaudado)}</strong></span>
        <span>Premios <strong className="num">{fmt(torneo.costo_premios)}</strong></span>
        <span>Ganancia <strong className="num" style={{ color: Number(torneo.ganancia) < 0 ? "var(--danger)" : undefined }}>{fmt(torneo.ganancia)}</strong></span>
      </div>
      <Seccion etiqueta={`Jugadores (${torneo.jugadores})`}>
        {torneo.participantes.map((p) => (
          <div key={p.id} style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 14 }}>
            <span style={{ overflowWrap: "anywhere" }}>{p.nombre}</span>
            <span className="muted num" style={{ whiteSpace: "nowrap" }}>{p.forma}{Number(p.monto) > 0 && ` · ${fmt(p.monto)}`}</span>
          </div>
        ))}
      </Seccion>
      {torneo.premios.length > 0 && (
        <Seccion etiqueta="Premios">
          {torneo.premios.map((p) => (
            <div key={p.producto_id} style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 14 }}>
              <span style={{ overflowWrap: "anywhere" }}>{fmtCant(p.cantidad)} × {p.nombre}</span>
              <span className="muted num">{fmt(p.costo)}</span>
            </div>
          ))}
        </Seccion>
      )}
    </Modal>
  );
}

// Historial de torneos con lo recaudado, lo que costaron los premios y la ganancia.
export default function Torneos() {
  const isMobile = useIsMobile();
  const { turno, error: errorTurno, recargar: recargarTurno } = useTurno();
  const [filtros, setFiltros] = useState(() => ({ desde: haceDias(30), hasta: hoy(), juego_id: "" }));
  const [juegos, setJuegos] = useState([]);
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [registrando, setRegistrando] = useState(false);
  const [detalle, setDetalle] = useState(null);
  const ultima = useRef(0);

  const cargar = useCallback(() => {
    const mia = ++ultima.current;
    api.torneos(filtros)
      .then((r) => { if (mia === ultima.current) { setError(""); setLista(r); } })
      .catch((err) => mia === ultima.current && setError(err.message));
  }, [filtros]);
  useEffect(() => { cargar(); }, [cargar]);
  useEffect(() => { api.catalogo("juegos", true).then(setJuegos).catch(() => {}); }, []);

  const suma = (k) => (lista || []).reduce((a, t) => a + Number(t[k]), 0);
  const filtro = (k) => (e) => setFiltros((f) => ({ ...f, [k]: e.target.value }));

  return (
    <>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Torneos</h1>
          {!isMobile && <div className="muted" style={{ fontSize: 14 }}>Inscripciones, premios y ganancia de cada torneo</div>}
        </div>
        <button type="button" className="btn btn-p" disabled={turno === undefined} onClick={() => setRegistrando(true)}>+ Registrar torneo</button>
      </header>
      {errorTurno && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>No se pudo revisar el turno de caja: {errorTurno}</span>
          <button type="button" className="btn btn-s" onClick={recargarTurno}>Reintentar</button>
        </div>
      )}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <Campo etiqueta="Desde"><input className="inp" type="date" value={filtros.desde} onChange={filtro("desde")} /></Campo>
        <Campo etiqueta="Hasta"><input className="inp" type="date" value={filtros.hasta} onChange={filtro("hasta")} /></Campo>
        <Campo etiqueta="Juego">
          <select className="inp" value={filtros.juego_id} onChange={filtro("juego_id")}>
            <option value="">Todos</option>
            {juegos.map((j) => <option key={j.id} value={j.id}>{j.nombre}</option>)}
          </select>
        </Campo>
      </div>
      {error && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>{error}</span>
          <button type="button" className="btn btn-s" onClick={cargar}>Reintentar</button>
        </div>
      )}
      {lista && lista.length > 0 && (
        <div className="muted num" style={{ fontSize: 14 }}>
          {lista.length} {lista.length === 1 ? "torneo" : "torneos"} · recaudado {fmt(suma("recaudado"))} · premios {fmt(suma("costo_premios"))} ·
          ganancia <strong style={{ color: "var(--text)" }}>{fmt(suma("ganancia"))}</strong>
        </div>
      )}
      <div className="card" style={{ overflow: "hidden" }}>
        {!lista && !error && <div className="muted" style={{ padding: 16 }}>Cargando…</div>}
        {lista?.length === 0 && <div className="muted" style={{ padding: 16 }}>No hay torneos en esas fechas.</div>}
        {(lista || []).map((t) => (
          <button key={t.id} type="button" onClick={() => api.torneo(t.id).then(setDetalle).catch((err) => setError(err.message))}
            style={{ width: "100%", border: 0, borderBottom: "1px solid var(--border-2)", background: "#fff", textAlign: "left",
              font: "inherit", color: "inherit", cursor: "pointer", padding: "12px 16px", display: "flex", gap: 12, alignItems: "center" }}>
            <span style={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
              <strong style={{ overflowWrap: "anywhere" }}>{t.nombre}</strong>
              <span className="muted" style={{ fontSize: 12 }}>
                {t.juego} · {fmtFechaHora(t.realizado_en)} · {t.jugadores} jugador(es){Number(t.jugadores_gratis) > 0 && `, ${t.jugadores_gratis} gratis`}
              </span>
            </span>
            <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
              <span className="num" style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{fmt(t.recaudado)}</span>
              <span className="muted num" style={{ fontSize: 12, whiteSpace: "nowrap" }}>ganancia {fmt(t.ganancia)}</span>
            </span>
          </button>
        ))}
      </div>
      {registrando && (
        <ModalTorneo turno={turno} onClose={() => setRegistrando(false)}
          onRegistrado={(t) => {
            setRegistrando(false);
            setDetalle(t);
            if (filtros.hasta < hoy()) setFiltros((f) => ({ ...f, hasta: hoy() }));
            else cargar();
          }} />
      )}
      {detalle && <DetalleTorneo torneo={detalle} onClose={() => setDetalle(null)} />}
    </>
  );
}
