import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import BuscarArticulo from "../components/BuscarArticulo";
import BuscarTercero from "../components/BuscarTercero";
import Modal, { Campo, ErrorBanner, Seccion } from "../components/Modal";
import PagoModal from "../components/PagoModal";
import { centavos, fmt, fmtCant, fmtFecha, fmtFechaHora } from "../format";
import { useIsMobile } from "../useMediaQuery";
import { useTurno } from "../useTurno";
import { IconoQuitar } from "../components/Iconos";

const TIPOS = [["cotizacion", "Cotización", "Cotizaciones"], ["orden_pedido", "Orden de pedido", "Órdenes"], ["remision", "Remisión", "Remisiones"]];
const nombreTipo = (t) => TIPOS.find(([k]) => k === t)?.[1] ?? t;
const SIGUIENTE = { cotizacion: "orden_pedido", orden_pedido: "remision" };
const ESTADOS = {
  vigente: ["Vigente", "ok"], vencida: ["Vencida", "warn"], aceptada: ["Aceptada", "neu"], entregada: ["Entregada", "neu"],
  facturada: ["Vendida", "ok"], rechazada: ["Rechazada", "bad"], anulada: ["Anulada", "bad"],
};
const ABIERTOS = ["vigente", "vencida"];
// Las cantidades se guardan con 3 decimales: se valida y se manda ese valor.
const cantidad3 = (v) => Math.round((Number(v) || 0) * 1000) / 1000;
const enDias = (n) => new Date(Date.now() + n * 86400000).toLocaleDateString("en-CA");

function Estado({ estado }) {
  const [texto, clase] = ESTADOS[estado] ?? [estado, "neu"];
  return <span className={`chip ${clase}`}>{texto}</span>;
}

// Crear un documento o editar uno abierto (reemplaza encabezado y líneas).
function EditorDocumento({ documento, onClose, onGuardado }) {
  const nuevo = !documento;
  const [tipo, setTipo] = useState(documento?.tipo ?? "cotizacion");
  const [cliente, setCliente] = useState(documento?.cliente_id ? { id: documento.cliente_id, nombre: documento.cliente } : null);
  const [vigente, setVigente] = useState(documento ? documento.vigente_hasta ?? "" : enDias(15));
  const [descuento, setDescuento] = useState(documento ? String(Number(documento.descuento) || "") : "");
  const [notas, setNotas] = useState(documento?.notas ?? "");
  const [lineas, setLineas] = useState(() => (documento?.items ?? []).map((i) => ({
    clave: i.id, articulo_id: i.articulo_id, articulo: i.articulo, descripcion: i.descripcion,
    cantidad: String(Number(i.cantidad)), precio: String(Number(i.precio_unit)),
  })));
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const agregarArticulo = (a) => setLineas((ls) => [...ls, {
    clave: `${a.id}-${Date.now()}`, articulo_id: a.id, articulo: a.nombre, descripcion: a.nombre, cantidad: "1", precio: String(Number(a.precio_venta)),
  }]);
  const agregarLibre = () => setLineas((ls) => [...ls, { clave: `libre-${Date.now()}`, articulo_id: null, descripcion: "", cantidad: "1", precio: "" }]);
  const cambiar = (i, cambios) => setLineas((ls) => ls.map((l, k) => (k === i ? { ...l, ...cambios } : l)));

  const subtotal = centavos(lineas.reduce((a, l) => a + (Number(l.cantidad) || 0) * (Number(l.precio) || 0), 0));
  const valorDescuento = centavos(Number(descuento) || 0);
  let bloqueo = "";
  if (lineas.length === 0) bloqueo = "Agrega al menos una línea.";
  else if (lineas.some((l) => !l.descripcion.trim())) bloqueo = "Cada línea lleva su descripción.";
  else if (lineas.some((l) => !(cantidad3(l.cantidad) > 0) || l.precio === "" || Number(l.precio) < 0)) bloqueo = "Cada línea lleva cantidad mayor que cero y precio.";
  else if (valorDescuento < 0 || valorDescuento > subtotal) bloqueo = "El descuento no puede superar el subtotal.";

  const guardar = async (e) => {
    e.preventDefault();
    if (bloqueo) return;
    setEnviando(true);
    setError("");
    const body = {
      cliente_id: cliente?.id ?? null, descuento: valorDescuento, notas: notas.trim() || null,
      vigente_hasta: tipo === "cotizacion" && vigente ? vigente : null,
      items: lineas.map((l) => ({
        articulo_id: l.articulo_id, descripcion: l.descripcion.trim(),
        cantidad: cantidad3(l.cantidad), precio_unit: centavos(Number(l.precio)),
      })),
    };
    try {
      onGuardado(nuevo ? await api.crearDocumento({ tipo, ...body }) : await api.editarDocumento(documento.id, body));
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <Modal titulo={nuevo ? "Nuevo documento" : `Editar ${nombreTipo(documento.tipo).toLowerCase()} #${documento.numero}`}
      onClose={() => !enviando && onClose()} ancho={760}>
      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
          {nuevo && (
            <Campo etiqueta="Tipo">
              <select className="inp" value={tipo} onChange={(e) => setTipo(e.target.value)}>
                {TIPOS.map(([k, n]) => <option key={k} value={k}>{n}</option>)}
              </select>
            </Campo>
          )}
          {tipo === "cotizacion" && (
            <Campo etiqueta="Vigente hasta"><input className="inp" type="date" value={vigente} onChange={(e) => setVigente(e.target.value)} /></Campo>
          )}
        </div>
        <Seccion etiqueta="Cliente (opcional)">
          {cliente ? (
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
              <strong style={{ overflowWrap: "anywhere" }}>{cliente.nombre}</strong>
              <button type="button" className="btn btn-g" onClick={() => setCliente(null)}>Quitar</button>
            </div>
          ) : (
            <BuscarTercero rol="cliente" placeholder="Buscar cliente" onElegir={(t) => setCliente({ id: t.id, nombre: t.nombre })} />
          )}
        </Seccion>

        <Seccion etiqueta="Líneas">
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-start" }}>
            <BuscarArticulo onElegir={agregarArticulo} etiqueta="Buscar artículo del catálogo" placeholder="Agregar artículo del catálogo" />
            <button type="button" className="btn btn-s" onClick={agregarLibre}>+ Línea de texto libre</button>
          </div>
          {lineas.map((l, i) => (
            <div key={l.clave} className="card" style={{ padding: 10, display: "flex", flexDirection: "column", gap: 8 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                <div style={{ flexGrow: 1, minWidth: 0 }}>
                  <Campo etiqueta={l.articulo_id ? `Descripción (artículo: ${l.articulo})` : "Descripción (texto libre)"}>
                    <input className="inp" value={l.descripcion} onChange={(e) => cambiar(i, { descripcion: e.target.value })} />
                  </Campo>
                </div>
                <button type="button" className="btn btn-g" style={{ marginTop: 22 }} aria-label={`Quitar línea ${i + 1}`}
                  onClick={() => setLineas((ls) => ls.filter((_, k) => k !== i))}><IconoQuitar /></button>
              </div>
              <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(110px, 1fr))", alignItems: "end" }}>
                <Campo etiqueta="Cantidad">
                  <input className="inp num" type="number" min="0" step="any" inputMode="decimal" value={l.cantidad} onChange={(e) => cambiar(i, { cantidad: e.target.value })} />
                </Campo>
                <Campo etiqueta="Precio unitario">
                  <input className="inp num" type="number" min="0" step="any" inputMode="decimal" value={l.precio} onChange={(e) => cambiar(i, { precio: e.target.value })} />
                </Campo>
                <span className="num" style={{ fontWeight: 600, textAlign: "right", paddingBottom: 10 }}>
                  {fmt((Number(l.cantidad) || 0) * (Number(l.precio) || 0))}
                </span>
              </div>
            </div>
          ))}
          {lineas.some((l) => !l.articulo_id) && (
            <span className="muted" style={{ fontSize: 13 }}>Las líneas de texto libre se pueden cotizar, pero para vender hay que cambiarlas por artículos del catálogo.</span>
          )}
        </Seccion>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))", gap: 12 }}>
          <Campo etiqueta="Descuento">
            <input className="inp num" type="number" min="0" step="any" inputMode="decimal" value={descuento} placeholder="0" onChange={(e) => setDescuento(e.target.value)} />
          </Campo>
          <Campo etiqueta="Notas (opcional)"><input className="inp" value={notas} onChange={(e) => setNotas(e.target.value)} /></Campo>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <span style={{ fontWeight: 600 }}>Total{valorDescuento > 0 && <span className="muted num" style={{ fontWeight: 400 }}> ({fmt(subtotal)} − {fmt(valorDescuento)})</span>}</span>
          <span className="num" style={{ fontSize: 26, fontWeight: 700 }}>{fmt(subtotal - valorDescuento)}</span>
        </div>
        {bloqueo && lineas.length > 0 && <div className="muted" role="status" style={{ fontSize: 14 }}>{bloqueo}</div>}
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose} disabled={enviando}>Volver</button>
          <button type="submit" className="btn btn-p" disabled={!!bloqueo || enviando}>{nuevo ? "Crear" : "Guardar"}</button>
        </div>
      </form>
    </Modal>
  );
}

function DetalleDocumento({ documentoId, turno, onClose, onCambio, onAbrir }) {
  const [doc, setDoc] = useState(null);
  const [modo, setModo] = useState(null); // "editar" | "vender" | "descartar"
  const [motivo, setMotivo] = useState("rechazado");
  const [explicacion, setExplicacion] = useState("");
  const [aviso, setAviso] = useState("");
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const cargar = useCallback(() => api.documento(documentoId).then(setDoc).catch((err) => setError(err.message)), [documentoId]);
  useEffect(() => { cargar(); }, [cargar]);

  // Convertir o descartar: si falla (otra pantalla lo cambió), se recarga.
  const accion = async (promesa) => {
    setOcupado(true);
    setError("");
    try {
      const r = await promesa;
      onCambio();
      return r;
    } catch (err) {
      setError(err.message);
      cargar();
      return null;
    } finally {
      setOcupado(false);
    }
  };

  if (modo === "editar") {
    return <EditorDocumento documento={doc} onClose={() => setModo(null)} onGuardado={(d) => { setModo(null); setDoc(d); onCambio(); }} />;
  }
  if (modo === "vender") {
    return (
      <PagoModal total={Number(doc.total)} cliente={doc.cliente_id ? { id: doc.cliente_id, nombre: doc.cliente } : null}
        cajas={turno.cajas} onClose={() => { setModo(null); cargar(); }}
        onCobrar={async (cobro, { cambio }) => {
          const venta = await api.venderDocumento(doc.id, { ...cobro, sesion_id: turno.id });
          setModo(null);
          setDoc(venta.documento);
          setAviso(`Venta #${venta.numero} registrada por ${fmt(venta.total)}.${cambio > 0 ? ` Cambio ${fmt(cambio)}.` : ""}`);
          onCambio();
        }} />
    );
  }

  const abierto = doc && ABIERTOS.includes(doc.estado);
  const libres = doc ? doc.items.filter((i) => !i.articulo_id).length : 0;
  return (
    <Modal titulo={doc ? `${nombreTipo(doc.tipo)} #${doc.numero}` : "Documento"} onClose={onClose} ancho={720}>
      <ErrorBanner mensaje={error} />
      {doc && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <Estado estado={doc.estado} />
            <span className="muted" style={{ fontSize: 14 }}>
              {doc.cliente ?? "Sin cliente"} · {fmtFechaHora(doc.creado_en)} · {doc.usuario}
              {doc.vigente_hasta && ` · vigente hasta ${fmtFecha(doc.vigente_hasta)}`}
            </span>
          </div>
          {(doc.origen_numero || doc.hijo_numero || doc.venta_numero) && (
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 14 }}>
              {doc.origen_numero && (
                <button type="button" className="btn btn-g" style={{ height: 30 }} onClick={() => onAbrir(doc.doc_origen_id)}>
                  ← Viene de {nombreTipo(doc.origen_tipo).toLowerCase()} #{doc.origen_numero}
                </button>
              )}
              {doc.hijo_numero && (
                <button type="button" className="btn btn-g" style={{ height: 30 }} onClick={() => onAbrir(doc.hijo_id)}>
                  Pasó a {nombreTipo(doc.hijo_tipo).toLowerCase()} #{doc.hijo_numero} →
                </button>
              )}
              {doc.venta_numero && <span className="chip ok">Venta #{doc.venta_numero}</span>}
            </div>
          )}
          <div className="card tabla">
            {doc.items.map((i) => (
              <div key={i.id} className="tr" style={{ gridTemplateColumns: "1fr auto auto" }}>
                <span style={{ overflowWrap: "anywhere" }}>
                  {i.descripcion}{!i.articulo_id && <span className="muted" style={{ fontSize: 12 }}> · texto libre</span>}
                </span>
                <span className="muted num">{fmtCant(i.cantidad)} × {fmt(i.precio_unit)}</span>
                <span className="r num" style={{ fontWeight: 600 }}>{fmt(i.subtotal)}</span>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 16, flexWrap: "wrap" }}>
            {Number(doc.descuento) > 0 && <span className="muted num">Subtotal {fmt(doc.subtotal)} · descuento {fmt(doc.descuento)}</span>}
            <strong className="num" style={{ fontSize: 20 }}>Total {fmt(doc.total)}</strong>
          </div>
          {doc.notas && <span style={{ fontSize: 14, whiteSpace: "pre-line" }}>{doc.notas}</span>}
          {aviso && <div role="status" style={{ fontWeight: 600, color: "var(--accent-hover)" }}>{aviso}</div>}

          {modo === "descartar" ? (
            <form onSubmit={async (e) => { e.preventDefault(); const r = await accion(api.descartarDocumento(doc.id, motivo, explicacion.trim() || null)); if (r) { setDoc(r); setModo(null); } }}
              style={{ display: "flex", flexDirection: "column", gap: 10, borderTop: "1px solid var(--border-2)", paddingTop: 12 }}>
              <div className="seg" role="radiogroup" aria-label="Motivo" style={{ alignSelf: "flex-start" }}>
                {[["rechazado", "El cliente no lo aceptó"], ["anulado", "Fue un error"]].map(([k, n]) => (
                  <button key={k} type="button" role="radio" aria-checked={motivo === k} className={motivo === k ? "on" : ""} onClick={() => setMotivo(k)}>{n}</button>
                ))}
              </div>
              <Campo etiqueta="Explicación (opcional)"><input className="inp" value={explicacion} onChange={(e) => setExplicacion(e.target.value)} /></Campo>
              <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                <button type="button" className="btn btn-s" onClick={() => setModo(null)}>Volver</button>
                <button type="submit" className="btn btn-d" disabled={ocupado}>Descartar</button>
              </div>
            </form>
          ) : abierto && (
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", alignItems: "center", flexWrap: "wrap", borderTop: "1px solid var(--border-2)", paddingTop: 12 }}>
              <button type="button" className="btn btn-d" onClick={() => setModo("descartar")}>Descartar</button>
              <button type="button" className="btn btn-s" onClick={() => setModo("editar")}>Editar</button>
              {doc.estado === "vigente" && SIGUIENTE[doc.tipo] && (
                <button type="button" className="btn btn-s" disabled={ocupado}
                  onClick={async () => { const r = await accion(api.convertirDocumento(doc.id)); if (r) onAbrir(r.id); }}>
                  Pasar a {nombreTipo(SIGUIENTE[doc.tipo]).toLowerCase()}
                </button>
              )}
              {doc.estado === "vigente" && (
                <button type="button" className="btn btn-p" disabled={!turno || libres > 0} onClick={() => setModo("vender")}>Vender</button>
              )}
              {doc.estado === "vencida" && <span className="muted" style={{ fontSize: 13, flexBasis: "100%", textAlign: "right" }}>Venció: edita su vigencia para pasarla o venderla.</span>}
              {doc.estado === "vigente" && libres > 0 && (
                <span className="muted" style={{ fontSize: 13, flexBasis: "100%", textAlign: "right" }}>Para venderlo, edita las líneas de texto libre y cámbialas por artículos del catálogo.</span>
              )}
              {doc.estado === "vigente" && turno === null && (
                <span className="muted" style={{ fontSize: 13, flexBasis: "100%", textAlign: "right" }}>Para vender abre el turno en <Link to="/caja">Caja</Link>.</span>
              )}
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

// Cotizaciones, órdenes de pedido y remisiones.
export default function Documentos() {
  const isMobile = useIsMobile();
  const { turno } = useTurno();
  const [filtros, setFiltros] = useState({ tipo: "", estado: "abierto", q: "" });
  const [lista, setLista] = useState(null);
  const [error, setError] = useState("");
  const [creando, setCreando] = useState(false);
  const [abierto, setAbierto] = useState(null); // id del documento en el detalle
  const ultima = useRef(0);

  const cargar = useCallback(() => {
    const mia = ++ultima.current;
    api.documentos({ ...filtros, q: filtros.q.trim() })
      .then((r) => { if (mia === ultima.current) { setError(""); setLista(r); } })
      .catch((err) => mia === ultima.current && setError(err.message));
  }, [filtros]);
  useEffect(() => {
    const t = setTimeout(cargar, 200);
    return () => clearTimeout(t);
  }, [cargar]);

  return (
    <>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <h1 style={{ fontSize: isMobile ? 26 : 30 }}>Documentos</h1>
          {!isMobile && <div className="muted" style={{ fontSize: 14 }}>Cotización → orden de pedido → remisión → venta</div>}
        </div>
        <button type="button" className="btn btn-p" onClick={() => setCreando(true)}>+ Nuevo documento</button>
      </header>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "flex-end" }}>
        <div className="seg" role="tablist" aria-label="Tipo de documento" style={{ maxWidth: "100%", overflowX: "auto" }}>
          {[["", "Todos"], ...TIPOS.map(([k, , plural]) => [k, plural])].map(([k, n]) => (
            <button key={k} type="button" role="tab" aria-selected={filtros.tipo === k} className={filtros.tipo === k ? "on" : ""}
              onClick={() => setFiltros((f) => ({ ...f, tipo: k }))}>{n}</button>
          ))}
        </div>
        <Campo etiqueta="Estado">
          <select className="inp" value={filtros.estado} onChange={(e) => setFiltros((f) => ({ ...f, estado: e.target.value }))}>
            <option value="abierto">Abiertos (vigentes o vencidos)</option>
            <option value="">Todos</option>
            {Object.entries(ESTADOS).map(([k, [n]]) => <option key={k} value={k}>{n}</option>)}
          </select>
        </Campo>
        <input className="inp" type="search" aria-label="Buscar documento" placeholder="Cliente o número" value={filtros.q}
          onChange={(e) => setFiltros((f) => ({ ...f, q: e.target.value }))} style={{ flex: "1 1 200px", maxWidth: 320 }} />
      </div>
      {error && (
        <div role="alert" className="error-banner" style={{ justifyContent: "space-between" }}>
          <span>{error}</span>
          <button type="button" className="btn btn-s" onClick={cargar}>Reintentar</button>
        </div>
      )}
      <div className="card" style={{ overflow: "hidden" }}>
        {!lista && !error && <div className="muted" style={{ padding: 16 }}>Cargando…</div>}
        {lista?.length === 0 && <div className="muted" style={{ padding: 16 }}>No hay documentos con esos filtros.</div>}
        {(lista || []).map((d) => (
          <button key={d.id} type="button" onClick={() => setAbierto(d.id)}
            style={{ width: "100%", border: 0, borderBottom: "1px solid var(--border-2)", background: "#fff", textAlign: "left",
              font: "inherit", color: "inherit", cursor: "pointer", padding: "12px 16px", display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
            <span style={{ flex: "1 1 200px", minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
              <strong style={{ overflowWrap: "anywhere" }}>{nombreTipo(d.tipo)} #{d.numero}{d.cliente && ` · ${d.cliente}`}</strong>
              <span className="muted" style={{ fontSize: 12 }}>
                {fmtFechaHora(d.creado_en)} · {d.lineas} {Number(d.lineas) === 1 ? "línea" : "líneas"}
                {d.vigente_hasta && ` · vigente hasta ${fmtFecha(d.vigente_hasta)}`}
              </span>
            </span>
            <Estado estado={d.estado} />
            <span className="num" style={{ fontWeight: 700, whiteSpace: "nowrap" }}>{fmt(d.total)}</span>
          </button>
        ))}
      </div>
      {creando && <EditorDocumento onClose={() => setCreando(false)} onGuardado={(d) => { setCreando(false); cargar(); setAbierto(d.id); }} />}
      {abierto && (
        <DetalleDocumento key={abierto} documentoId={abierto} turno={turno} onClose={() => setAbierto(null)} onCambio={cargar}
          onAbrir={(id) => setAbierto(id)} />
      )}
    </>
  );
}
