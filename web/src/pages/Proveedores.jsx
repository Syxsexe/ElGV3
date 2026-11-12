import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import BuscarTercero from "../components/BuscarTercero";
import Modal, { Campo, ErrorBanner, Seccion } from "../components/Modal";
import ModalEgreso from "../components/ModalEgreso";
import { centavos, fmt, fmtCant, fmtCosto, fmtFecha, fmtFechaHora } from "../format";
import { useIsMobile } from "../useMediaQuery";
import { useTurno } from "../useTurno";
import Terceros from "./Terceros";
import { IconoQuitar } from "../components/Iconos";

const SOPORTES = [["factura", "Factura"], ["factura_electronica", "Factura electrónica"], ["pos", "Tiquete POS"], ["otro", "Otro / sin soporte"]];
const nombreSoporte = (c) => SOPORTES.find(([k]) => k === c.tipo_soporte)?.[1] + (c.numero_soporte ? ` ${c.numero_soporte}` : "");

// Buscar un producto o insumo para agregarlo a la compra.
function BuscarItem({ onElegir }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState([]);
  const ultima = useRef(0);

  useEffect(() => {
    if (q.trim().length < 2) return undefined;
    const mia = ++ultima.current;
    const t = setTimeout(() => api.itemsCompra(q.trim()).then((r) => mia === ultima.current && setItems(r)).catch(() => {}), 200);
    return () => clearTimeout(t);
  }, [q]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <input className="inp" aria-label="Buscar producto o insumo" placeholder="Buscar producto o insumo para agregar" value={q}
        onChange={(e) => setQ(e.target.value)} />
      {q.trim().length >= 2 && items.length > 0 && (
        <div className="card" style={{ maxHeight: 220, overflowY: "auto" }}>
          {items.map((it) => (
            <button key={`${it.tipo}-${it.id}`} type="button" onClick={() => { onElegir(it); setQ(""); setItems([]); }}
              style={{ width: "100%", border: 0, borderBottom: "1px solid var(--border-2)", background: "#fff", textAlign: "left",
                font: "inherit", color: "inherit", cursor: "pointer", padding: "10px 14px", display: "flex", justifyContent: "space-between", gap: 10 }}>
              <span style={{ overflowWrap: "anywhere" }}>{it.nombre} <span className="muted" style={{ fontSize: 12 }}>· {it.tipo === "insumo" ? `insumo (${it.unidad})` : "producto"}</span></span>
              <span className="muted num" style={{ whiteSpace: "nowrap" }}>{fmtCosto(it.costo)}/{it.unidad}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function ModalCompra({ onClose, onRegistrada }) {
  const [proveedor, setProveedor] = useState(null);
  const [soporte, setSoporte] = useState({ tipo_soporte: "factura", numero_soporte: "", fecha_soporte: "", cufe: "", notas: "" });
  const [lineas, setLineas] = useState([]); // [{tipo, id, nombre, unidad, cantidad, costo, impuesto_id}]
  const [impuestos, setImpuestos] = useState([]);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  useEffect(() => { api.impuestos().then(setImpuestos).catch((err) => setError(err.message)); }, []);

  const agregar = (it) => {
    if (lineas.some((l) => l.tipo === it.tipo && l.id === it.id)) return setError(`${it.nombre} ya está en la compra: cambia su cantidad.`);
    setError("");
    setLineas((ls) => [...ls, { tipo: it.tipo, id: it.id, nombre: it.nombre, unidad: it.unidad, cantidad: "1",
      costo: Number(it.costo) > 0 ? String(Number(it.costo)) : "", impuesto_id: it.impuesto_id || "" }]);
  };
  const cambiar = (i, cambios) => setLineas((ls) => ls.map((l, j) => (j === i ? { ...l, ...cambios } : l)));
  const total = centavos(lineas.reduce((a, l) => a + (Number(l.cantidad) || 0) * (Number(l.costo) || 0), 0));
  const campo = (k) => (e) => setSoporte((s) => ({ ...s, [k]: e.target.value }));

  let bloqueo = "";
  if (!proveedor) bloqueo = "Elige el proveedor.";
  else if (lineas.length === 0) bloqueo = "Agrega lo que se compró.";
  else if (lineas.some((l) => !(Number(l.cantidad) > 0) || !(Number(l.costo) > 0))) bloqueo = "Cada línea lleva cantidad y costo mayores que cero.";
  else if (soporte.tipo_soporte === "factura_electronica" && !soporte.cufe.trim()) bloqueo = "Una factura electrónica lleva su CUFE.";

  const guardar = async (e) => {
    e.preventDefault();
    if (bloqueo) return;
    setEnviando(true);
    setError("");
    try {
      const r = await api.registrarCompra({
        proveedor_id: proveedor.id, tipo_soporte: soporte.tipo_soporte, numero_soporte: soporte.numero_soporte || null,
        fecha_soporte: soporte.fecha_soporte || null, cufe: soporte.tipo_soporte === "factura_electronica" ? soporte.cufe : null,
        notas: soporte.notas || null,
        // Las columnas guardan 3 decimales en cantidad y 4 en costo.
        lineas: lineas.map((l) => ({
          [`${l.tipo}_id`]: l.id, cantidad: Math.round(Number(l.cantidad) * 1000) / 1000,
          costo_unit: Math.round(Number(l.costo) * 10000) / 10000, impuesto_id: l.impuesto_id || null,
        })),
      });
      onRegistrada(r);
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <Modal titulo="Nueva compra" onClose={() => !enviando && onClose()} ancho={820}>
      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Seccion etiqueta="Proveedor">
          {proveedor ? (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
              <strong>{proveedor.nombre}</strong>
              <button type="button" className="btn btn-g" onClick={() => setProveedor(null)}>Cambiar</button>
            </div>
          ) : (
            <BuscarTercero rol="proveedor" placeholder="Buscar proveedor" onElegir={(t) => setProveedor({ id: t.id, nombre: t.nombre })} />
          )}
        </Seccion>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
          <Campo etiqueta="Soporte">
            <select className="inp" value={soporte.tipo_soporte} onChange={campo("tipo_soporte")}>
              {SOPORTES.map(([k, n]) => <option key={k} value={k}>{n}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Número (opcional)"><input className="inp" value={soporte.numero_soporte} onChange={campo("numero_soporte")} /></Campo>
          <Campo etiqueta="Fecha del soporte"><input className="inp" type="date" value={soporte.fecha_soporte} onChange={campo("fecha_soporte")} /></Campo>
        </div>
        {soporte.tipo_soporte === "factura_electronica" && (
          <Campo etiqueta="CUFE"><input className="inp" value={soporte.cufe} onChange={campo("cufe")} /></Campo>
        )}

        <Seccion etiqueta="Lo que se compró (costo por unidad, impuestos incluidos)">
          <BuscarItem onElegir={agregar} />
          {lineas.map((l, i) => (
            <div key={`${l.tipo}-${l.id}`} className="card" style={{ padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                <div style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
                  <strong style={{ overflowWrap: "anywhere" }}>{l.nombre}</strong>
                  <span className="muted num" style={{ fontSize: 12 }}>
                    {l.tipo === "insumo" ? `Insumo, en ${l.unidad}` : "Producto"} · {fmt((Number(l.cantidad) || 0) * (Number(l.costo) || 0))}
                  </span>
                </div>
                <button type="button" className="btn btn-g" aria-label={`Quitar ${l.nombre}`} onClick={() => setLineas((ls) => ls.filter((_, j) => j !== i))}><IconoQuitar /></button>
              </div>
              <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))" }}>
                <Campo etiqueta="Cantidad">
                  <input className="inp num" type="number" min="0" step="any" inputMode="decimal" value={l.cantidad} onChange={(e) => cambiar(i, { cantidad: e.target.value })} />
                </Campo>
                <Campo etiqueta={`Costo/${l.unidad}`}>
                  <input className="inp num" type="number" min="0" step="any" inputMode="decimal" value={l.costo} onChange={(e) => cambiar(i, { costo: e.target.value })} />
                </Campo>
                <Campo etiqueta="Impuesto">
                  <select className="inp" value={l.impuesto_id} onChange={(e) => cambiar(i, { impuesto_id: e.target.value })}>
                    <option value="">Sin discriminar</option>
                    {impuestos.map((im) => <option key={im.id} value={im.id}>{im.nombre}</option>)}
                  </select>
                </Campo>
              </div>
            </div>
          ))}
        </Seccion>
        <Campo etiqueta="Notas (opcional)"><input className="inp" value={soporte.notas} onChange={campo("notas")} /></Campo>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontWeight: 600 }}>Total</span>
          <span className="num" style={{ fontSize: 26, fontWeight: 700 }}>{fmt(total)}</span>
        </div>
        <span className="muted" style={{ fontSize: 13 }}>Al registrarla sube el stock de los productos y se actualiza su último costo (y el de los insumos).</span>
        {bloqueo && (proveedor || lineas.length > 0) && <div className="muted" role="status" style={{ fontSize: 14 }}>{bloqueo}</div>}
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-p" disabled={!!bloqueo || enviando}>Registrar compra</button>
        </div>
      </form>
    </Modal>
  );
}

function DetalleCompra({ compraId, costos, turno, onClose, onCambio }) {
  const [compra, setCompra] = useState(null);
  const [pagando, setPagando] = useState(false);
  const [borrando, setBorrando] = useState(false);
  const [error, setError] = useState("");

  const cargar = useCallback(() => api.compra(compraId).then(setCompra).catch((err) => setError(err.message)), [compraId]);
  useEffect(() => { cargar(); }, [cargar]);

  const borrar = async () => {
    try {
      await api.borrarCompra(compraId);
      onCambio();
      onClose();
    } catch (err) {
      setError(err.message);
      setBorrando(false);
    }
  };

  if (pagando) {
    return (
      <ModalEgreso turno={turno} compra={compra} onClose={() => setPagando(false)}
        onHecho={() => { setPagando(false); cargar(); onCambio(); }} />
    );
  }

  return (
    <Modal titulo={compra ? `Compra #${compra.numero}` : "Compra"} onClose={onClose} ancho={720}>
      <ErrorBanner mensaje={error} />
      {compra && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <span className="muted" style={{ fontSize: 14 }}>
            <strong style={{ color: "var(--text)" }}>{compra.proveedor}</strong> · {nombreSoporte(compra)}
            {compra.fecha_soporte && ` del ${fmtFecha(compra.fecha_soporte)}`} · registrada {fmtFechaHora(compra.registrada_en)} por {compra.usuario}
          </span>
          {compra.cufe && <span className="muted" style={{ fontSize: 12, overflowWrap: "anywhere" }}>CUFE {compra.cufe}</span>}
          {costos?.length > 0 && (
            <div role="status" className="card" style={{ padding: 12, borderColor: "var(--accent)", fontSize: 14 }}>
              <strong>Último costo actualizado:</strong>
              {costos.map((c) => <div key={c.nombre} className="num">{c.nombre}: {fmtCosto(c.antes)} → {fmtCosto(c.ahora)}</div>)}
            </div>
          )}
          <div className="card tabla">
            {compra.items.map((it) => (
              <div key={it.id} className="tr" style={{ gridTemplateColumns: "1fr auto auto" }}>
                <span style={{ overflowWrap: "anywhere" }}>{it.nombre}{it.impuesto && <span className="muted" style={{ fontSize: 12 }}> · {it.impuesto}</span>}</span>
                <span className="muted num">{fmtCant(it.cantidad)} {it.unidad} × {fmtCosto(it.costo_unit)}</span>
                <span className="r num" style={{ fontWeight: 600 }}>{fmt(it.subtotal)}</span>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
            <span>Total <strong className="num">{fmt(compra.total)}</strong></span>
            <span>Pagado <strong className="num">{fmt(compra.pagado)}</strong></span>
            <span>Por pagar <strong className="num" style={{ color: Number(compra.pendiente) > 0 ? "var(--danger)" : undefined }}>{fmt(compra.pendiente)}</strong></span>
          </div>
          {compra.pagos.length > 0 && (
            <Seccion etiqueta="Pagos">
              {compra.pagos.map((p) => (
                <div key={p.id} style={{ display: "flex", justifyContent: "space-between", gap: 10, fontSize: 14, opacity: p.anulado ? 0.55 : 1 }}>
                  <span>{fmtFechaHora(p.creado_en)} · turno #{p.turno} · {p.usuario}{Number(p.cruzado) > 0 && ` · cruce ${fmt(p.cruzado)}`}{p.anulado && " · anulado"}</span>
                  <span className="num">{fmt(p.monto)}</span>
                </div>
              ))}
            </Seccion>
          )}
          {compra.notas && <span style={{ fontSize: 14 }}>{compra.notas}</span>}
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", alignItems: "center", flexWrap: "wrap" }}>
            {compra.pagos.length === 0 && (borrando ? (
              <>
                <span style={{ fontSize: 14 }}>¿Borrarla? El stock se devuelve; los costos actualizados no.</span>
                <button type="button" className="btn btn-s" onClick={() => setBorrando(false)}>No</button>
                <button type="button" className="btn btn-d" onClick={borrar}>Sí, borrar</button>
              </>
            ) : (
              <button type="button" className="btn btn-d" onClick={() => setBorrando(true)}>Borrar compra</button>
            ))}
            {Number(compra.pendiente) > 0 && (
              <>
                {turno === null && <span className="muted" style={{ fontSize: 13 }}>Para pagar abre el turno en <Link to="/caja">Caja</Link>.</span>}
                <button type="button" className="btn btn-p" disabled={!turno} onClick={() => setPagando(true)}>Registrar pago</button>
              </>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
}

function Compras({ filtroInicial, turno }) {
  const [filtros, setFiltros] = useState(filtroInicial);
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [nueva, setNueva] = useState(false);
  const [abierta, setAbierta] = useState(null); // {id, costos?}
  const ultima = useRef(0);

  const cargar = useCallback(() => {
    const mia = ++ultima.current;
    api.compras({ pendientes: filtros.pendientes, proveedor_id: filtros.proveedor?.id })
      .then((r) => { if (mia === ultima.current) { setError(""); setLista(r); } })
      .catch((err) => mia === ultima.current && setError(err.message));
  }, [filtros]);
  useEffect(() => { cargar(); }, [cargar]);

  return (
    <>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
        <label style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
          <input type="checkbox" checked={!!filtros.pendientes} onChange={(e) => setFiltros((f) => ({ ...f, pendientes: e.target.checked }))} />
          Solo las que se deben
        </label>
        {filtros.proveedor && (
          <span className="chip neu">
            {filtros.proveedor.nombre}{" "}
            <button type="button" aria-label="Quitar el filtro de proveedor" onClick={() => setFiltros((f) => ({ ...f, proveedor: null }))}
              style={{ border: 0, background: "none", cursor: "pointer", color: "inherit", padding: 0, width: 24, height: 24, display: "inline-flex", alignItems: "center", justifyContent: "center", borderRadius: 99, marginRight: -6 }}><IconoQuitar size={14} /></button>
          </span>
        )}
        <button type="button" className="btn btn-p" style={{ marginLeft: "auto" }} onClick={() => setNueva(true)}>+ Nueva compra</button>
      </div>
      {error && <ErrorBanner mensaje={error} />}
      <div className="card" style={{ overflow: "hidden" }}>
        {!lista && !error && <div className="muted" style={{ padding: 16 }}>Cargando…</div>}
        {lista?.length === 0 && <div className="muted" style={{ padding: 16 }}>No hay compras.</div>}
        {(lista || []).map((c) => (
          <button key={c.id} type="button" onClick={() => setAbierta({ id: c.id })}
            style={{ width: "100%", border: 0, borderBottom: "1px solid var(--border-2)", background: "#fff", textAlign: "left",
              font: "inherit", color: "inherit", cursor: "pointer", padding: "12px 16px", display: "flex", gap: 12, alignItems: "center" }}>
            <span style={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
              <strong style={{ overflowWrap: "anywhere" }}>#{c.numero} · {c.proveedor}</strong>
              <span className="muted" style={{ fontSize: 12 }}>{nombreSoporte(c)} · {fmtFechaHora(c.registrada_en)} · {c.lineas} {Number(c.lineas) === 1 ? "línea" : "líneas"}</span>
            </span>
            {Number(c.pendiente) > 0
              ? <span className="chip warn num">Debe {fmt(c.pendiente)}</span>
              : <span className="chip ok">Pagada</span>}
            <span className="num" style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{fmt(c.total)}</span>
          </button>
        ))}
      </div>
      {nueva && <ModalCompra onClose={() => setNueva(false)} onRegistrada={(r) => { setNueva(false); cargar(); setAbierta({ id: r.id, costos: r.costos_actualizados }); }} />}
      {abierta && <DetalleCompra compraId={abierta.id} costos={abierta.costos} turno={turno} onClose={() => setAbierta(null)} onCambio={cargar} />}
    </>
  );
}

function PorPagar({ onVer }) {
  const [datos, setDatos] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { api.porPagar().then(setDatos).catch((err) => setError(err.message)); }, []);
  return (
    <>
      <ErrorBanner mensaje={error} />
      {datos && <div className="muted num" style={{ fontSize: 14 }}>Total por pagar <strong style={{ color: "var(--text)" }}>{fmt(datos.total)}</strong></div>}
      <div className="card" style={{ overflow: "hidden" }}>
        {datos?.proveedores.length === 0 && <div className="muted" style={{ padding: 16 }}>No se le debe nada a ningún proveedor.</div>}
        {(datos?.proveedores || []).map((p) => (
          <button key={p.proveedor_id} type="button" onClick={() => onVer({ id: p.proveedor_id, nombre: p.proveedor })}
            style={{ width: "100%", border: 0, borderBottom: "1px solid var(--border-2)", background: "#fff", textAlign: "left",
              font: "inherit", color: "inherit", cursor: "pointer", padding: "12px 16px", display: "flex", gap: 12, alignItems: "center" }}>
            <span style={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
              <strong style={{ overflowWrap: "anywhere" }}>{p.proveedor}</strong>
              <span className="muted" style={{ fontSize: 12 }}>{p.compras} {Number(p.compras) === 1 ? "compra" : "compras"} · desde {fmtFecha(p.desde)}</span>
            </span>
            <span className="num" style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{fmt(p.pendiente)}</span>
          </button>
        ))}
      </div>
    </>
  );
}

// Proveedores: sus datos y, con compras.registrar, las compras y lo que se les debe.
export default function Proveedores() {
  const { puede } = useAuth();
  const isMobile = useIsMobile();
  const { turno } = useTurno();
  const [vista, setVista] = useState("datos");
  const [filtroCompras, setFiltroCompras] = useState({ pendientes: false, proveedor: null });
  const compras = puede("compras.registrar");

  const pestanas = [["datos", "Proveedores"], ...(compras ? [["compras", "Compras"], ["por-pagar", "Por pagar"]] : [])];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: isMobile ? 26 : 28 }}>Proveedores</h1>
        {pestanas.length > 1 && (
          <div className="seg" role="tablist" aria-label="Vista de proveedores" style={{ maxWidth: "100%", overflowX: "auto" }}>
            {pestanas.map(([k, etiqueta]) => (
              <button key={k} type="button" role="tab" aria-selected={vista === k} className={vista === k ? "on" : ""}
                onClick={() => { if (k === "compras") setFiltroCompras({ pendientes: false, proveedor: null }); setVista(k); }}>{etiqueta}</button>
            ))}
          </div>
        )}
      </header>
      {vista === "datos" && <Terceros rol="proveedor" sinTitulo />}
      {vista === "compras" && <Compras key={JSON.stringify(filtroCompras)} filtroInicial={filtroCompras} turno={turno} />}
      {vista === "por-pagar" && (
        <PorPagar onVer={(proveedor) => { setFiltroCompras({ pendientes: true, proveedor }); setVista("compras"); }} />
      )}
    </div>
  );
}
