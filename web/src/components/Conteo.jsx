import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { fmtCant } from "../format";
import { useIsMobile } from "../useMediaQuery";
import Modal, { ErrorBanner } from "./Modal";

// Conteo físico desde la pantalla (pensado para el celular, caminando por el
// local): se ve el stock del sistema, se escribe lo contado y el mínimo, y al
// guardar se revisa el resumen. El servidor no pisa una fila cuyo stock
// cambió mientras se contaba (una venta): la devuelve para recontarla.
// Lo escrito se guarda como borrador en este navegador hasta guardarlo.

const TIPOS = [["productos", "Productos de tienda"], ["insumos", "Insumos"]];
const FILTROS = [["todos", "Todos"], ["negativos", "Stock negativo"], ["sinminimo", "Sin mínimo"], ["cambios", "Con cambios"]];
// Por usuario: en una tablet compartida, el borrador de uno no le aparece a otro.
const claveBorrador = (usuario, tipo) => `elg-conteo-${usuario}-${tipo}`;

function leerBorrador(clave) {
  try {
    return JSON.parse(localStorage.getItem(clave)) || null;
  } catch {
    return null;
  }
}
function guardarBorrador(clave, borrador) {
  try {
    if (borrador) localStorage.setItem(clave, JSON.stringify(borrador));
    else localStorage.removeItem(clave);
  } catch { /* sin almacenamiento: el conteo sigue, solo no se recupera */ }
}

// Lo que acepta el servidor: no negativo, hasta 9 enteros y 3 decimales.
const textoValido = (t) => t === undefined || t === "" || /^\d{1,9}(\.\d{1,3})?$/.test(String(t).trim());
// Contado: vacío = no se contó.
const leerContado = (t) => (t === undefined || String(t).trim() === "" ? null : Number(t));
// Mínimo: sin tocar = sin cambio; borrado = sin mínimo (0).
const leerMinimo = (t) => (t === undefined ? null : String(t).trim() === "" ? 0 : Number(t));
const iguales = (a, b) => Math.abs(Number(a) - Number(b)) < 0.0005;

function Diferencia({ antes, despues }) {
  const d = Math.round((despues - antes) * 1000) / 1000;
  if (d === 0) return <span className="chip neu">Igual</span>;
  return <span className={`chip num ${d > 0 ? "ok" : "warn"}`}>{d > 0 ? "+" : "−"}{fmtCant(Math.abs(d))}</span>;
}

export default function Conteo() {
  const isMobile = useIsMobile();
  const { usuario } = useAuth();
  const clave = useCallback((t) => claveBorrador(usuario?.id || usuario?.usuario || "anon", t), [usuario]);
  const [tipo, setTipo] = useState("productos");
  const [datos, setDatos] = useState({}); // {tipo: {lista, visto: {id: stock}}}
  const [cambios, setCambios] = useState({}); // {tipo: {id: {contado, minimo}}}
  const [recontar, setRecontar] = useState({}); // {tipo: {id: true}}
  const [recuperado, setRecuperado] = useState({}); // {tipo: fecha del borrador}
  const [filtro, setFiltro] = useState("todos");
  const [q, setQ] = useState("");
  const [revisando, setRevisando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [error, setError] = useState("");

  const cargar = useCallback((t, { conBorrador = true, conservar = null } = {}) => {
    const pedido = t === "productos"
      ? api.articulos({ tipo: "producto", categoria_tipo: "tienda", activos: true })
      : api.insumos("", true);
    return pedido.then((lista) => {
      if (!conservar) setError("");
      const visto = Object.fromEntries(lista.map((x) => [x.id, Number(x.stock)]));
      if (conservar) {
        // Refresco tras un error: lo contado sigue comparándose con lo que se veía.
        Object.entries(conservar).forEach(([id, v]) => { if (id in visto) visto[id] = v; });
      }
      const borrador = conBorrador ? leerBorrador(clave(t)) : null;
      if (borrador && Object.keys(borrador.cambios || {}).length) {
        // Lo contado se compara con el stock que se veía al contarlo.
        Object.entries(borrador.visto || {}).forEach(([id, v]) => { if (id in visto) visto[id] = v; });
        setCambios((c) => ({ ...c, [t]: borrador.cambios }));
        setRecuperado((r) => ({ ...r, [t]: borrador.fecha }));
      }
      setDatos((d) => ({ ...d, [t]: { lista, visto } }));
    }).catch((err) => setError(err.message));
  }, [clave]);

  useEffect(() => {
    if (!datos[tipo]) cargar(tipo);
  }, [tipo, datos, cargar]);

  const actual = datos[tipo];
  const misCambios = useMemo(() => cambios[tipo] || {}, [cambios, tipo]);

  // Borrador en este navegador mientras haya algo escrito.
  useEffect(() => {
    if (!actual) return;
    const ids = Object.keys(misCambios);
    guardarBorrador(clave(tipo), ids.length ? {
      fecha: new Date().toISOString(), cambios: misCambios,
      visto: Object.fromEntries(ids.map((id) => [id, actual.visto[id]])),
    } : null);
  }, [misCambios, tipo, actual, clave]);

  // Las filas con algo que guardar (contado distinto o mínimo distinto).
  const pendientes = useMemo(() => {
    if (!actual) return [];
    return actual.lista.flatMap((x) => {
      const c = misCambios[x.id];
      if (!c) return [];
      const malo = !textoValido(c.contado) || !textoValido(c.minimo);
      const contado = leerContado(c.contado), minimo = leerMinimo(c.minimo);
      const cuenta = !malo && contado !== null && !iguales(contado, actual.visto[x.id]);
      const fijaMinimo = !malo && minimo !== null && !iguales(minimo, x.stock_minimo);
      return cuenta || fijaMinimo || malo ? [{ x, contado, minimo, cuenta, fijaMinimo, malo }] : [];
    });
  }, [actual, misCambios]);
  const hayMalos = pendientes.some((p) => p.malo);
  const nConteos = pendientes.filter((p) => p.cuenta).length;
  const nMinimos = pendientes.filter((p) => p.fijaMinimo).length;

  // Aviso del navegador si se cierra la página con cambios sin guardar.
  useEffect(() => {
    if (!pendientes.length) return undefined;
    const avisar = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", avisar);
    return () => window.removeEventListener("beforeunload", avisar);
  }, [pendientes.length]);

  const cambiar = (id, campo, valor) => {
    setResultado(null);
    setCambios((c) => {
      const delTipo = { ...(c[tipo] || {}) };
      const fila = { ...(delTipo[id] || {}), [campo]: valor };
      // Un mínimo borrado es un cambio (queda sin mínimo); un contado vacío, no.
      if ((fila.contado ?? "") === "" && fila.minimo === undefined) delete delTipo[id];
      else delTipo[id] = fila;
      return { ...c, [tipo]: delTipo };
    });
  };

  const descartar = () => {
    setCambios((c) => ({ ...c, [tipo]: {} }));
    setRecuperado((r) => ({ ...r, [tipo]: null }));
    setRecontar((r) => ({ ...r, [tipo]: {} }));
    guardarBorrador(clave(tipo), null);
    cargar(tipo, { conBorrador: false });
  };

  const guardar = async () => {
    setGuardando(true);
    setError("");
    try {
      const filas = pendientes.map((p) => ({
        id: p.x.id, stock_visto: String(actual.visto[p.x.id]),
        contado: p.cuenta ? String(p.contado) : null,
        stock_minimo: p.fijaMinimo ? String(p.minimo) : null,
      }));
      const r = await api.conteo(tipo, filas);
      setResultado(r);
      setRevisando(false);
      setRecontar((rc) => ({ ...rc, [tipo]: Object.fromEntries(r.cambiaron.map((x) => [x.id, true])) }));
      setCambios((c) => ({ ...c, [tipo]: {} }));
      setRecuperado((rp) => ({ ...rp, [tipo]: null }));
      guardarBorrador(clave(tipo), null);
      await cargar(tipo, { conBorrador: false });
    } catch (err) {
      setError(err.message);
      // Si el servidor rechazó el conteo (un artículo ya no existe o cambió
      // de tipo), la lista se recarga: lo que ya no está deja de mandarse.
      if (err.status === 400 || err.status === 404) {
        const conservar = Object.fromEntries(Object.keys(misCambios).map((id) => [id, actual.visto[id]]));
        await cargar(tipo, { conBorrador: false, conservar });
      }
    } finally {
      setGuardando(false);
    }
  };

  const visibles = useMemo(() => {
    if (!actual) return [];
    const texto = q.trim().toLowerCase();
    const conCambio = new Set(pendientes.map((p) => p.x.id));
    return actual.lista.filter((x) => {
      if (texto && ![x.nombre, x.codigo, x.categoria].some((v) => v && String(v).toLowerCase().includes(texto))) return false;
      if (filtro === "negativos") return Number(x.stock) < 0;
      if (filtro === "sinminimo") return !(Number(x.stock_minimo) > 0);
      if (filtro === "cambios") return conCambio.has(x.id) || recontar[tipo]?.[x.id];
      return true;
    });
  }, [actual, q, filtro, pendientes, recontar, tipo]);

  const cuenta = (f) => {
    if (!actual) return 0;
    if (f === "negativos") return actual.lista.filter((x) => Number(x.stock) < 0).length;
    if (f === "sinminimo") return actual.lista.filter((x) => !(Number(x.stock_minimo) > 0)).length;
    if (f === "cambios") return new Set([...pendientes.map((p) => p.x.id), ...Object.keys(recontar[tipo] || {})]).size;
    return actual.lista.length;
  };

  const unidad = (x) => (tipo === "insumos" ? ` ${x.unidad}` : "");
  const columnas = "minmax(0, 1fr) 110px 130px 90px 120px";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, paddingBottom: pendientes.length ? 72 : 0 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <div className="seg" role="tablist" aria-label="Qué contar">
          {TIPOS.map(([k, et]) => (
            <button key={k} type="button" role="tab" aria-selected={tipo === k} className={tipo === k ? "on" : ""}
              onClick={() => { setTipo(k); setResultado(null); }}>{et}</button>
          ))}
        </div>
        <span className="muted" style={{ fontSize: 13 }}>
          Escribe lo que contaste; deja vacío lo que no contaste. El mínimo es desde cuánto avisar en Inicio.
        </span>
      </div>

      {recuperado[tipo] && (
        <div className="card aviso-entrar" role="status" style={{ padding: "10px 14px", display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", borderColor: "var(--warn-text)" }}>
          <span style={{ fontSize: 14 }}>Se recuperó un conteo sin guardar ({new Date(recuperado[tipo]).toLocaleString("es-CO", { dateStyle: "short", timeStyle: "short" })}).</span>
          <button type="button" className="btn btn-s" style={{ marginLeft: "auto" }} onClick={descartar}>Descartar y empezar de nuevo</button>
        </div>
      )}

      {resultado && (
        <div className="card aviso-entrar" role="status" style={{ padding: "12px 16px", display: "flex", flexDirection: "column", gap: 6, borderColor: "var(--accent)" }}>
          <strong>Conteo guardado: {resultado.ajustados.length} {resultado.ajustados.length === 1 ? "ajuste" : "ajustes"} de stock
            y {resultado.minimos.length} {resultado.minimos.length === 1 ? "mínimo" : "mínimos"}.</strong>
          {resultado.cambiaron.length > 0 && (
            <span style={{ fontSize: 14, color: "var(--warn-text)" }}>
              No se ajustó porque se movió mientras contabas (vuelve a contarlo):{" "}
              {resultado.cambiaron.map((x) => `${x.nombre} (veías ${fmtCant(x.visto)}, ahora ${fmtCant(x.actual)})`).join(", ")}.
            </span>
          )}
        </div>
      )}
      {!revisando && <ErrorBanner mensaje={error} />}

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <input className="inp" type="search" placeholder={tipo === "productos" ? "Buscar por nombre, código o categoría" : "Buscar insumo"}
          aria-label="Buscar en el conteo" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 360 }} />
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {FILTROS.map(([k, et]) => (
            <button key={k} type="button" className={`pill${filtro === k ? " on" : ""}`} style={{ height: 36, fontSize: 13 }}
              aria-pressed={filtro === k} onClick={() => setFiltro(k)}>{et} · {cuenta(k)}</button>
          ))}
        </div>
      </div>

      {!actual && !error && <div className="muted">Cargando…</div>}
      {actual && visibles.length === 0 && <div className="muted">Nada que mostrar con ese filtro.</div>}
      {actual && visibles.length > 0 && (
        <div className="card" style={{ overflow: "hidden" }}>
          {!isMobile && (
            <div className="th" style={{ gridTemplateColumns: columnas }}>
              <span>{tipo === "productos" ? "Producto" : "Insumo"}</span><span className="r">En el sistema</span>
              <span>Contado</span><span>Diferencia</span><span>Mínimo</span>
            </div>
          )}
          {visibles.map((x) => {
            const c = misCambios[x.id] || {};
            const visto = actual.visto[x.id];
            const contadoOk = textoValido(c.contado), minimoOk = textoValido(c.minimo);
            const contado = contadoOk ? leerContado(c.contado) : null;
            const minimo = minimoOk ? leerMinimo(c.minimo) : null;
            const editado = (contado !== null && !iguales(contado, visto)) || (minimo !== null && !iguales(minimo, x.stock_minimo));
            const negativo = Number(x.stock) < 0;
            // Borrador recuperado: el stock pudo moverse desde que se contó.
            const movido = !iguales(visto, x.stock);
            const contadoInput = (
              <input className="inp num" type="number" min="0" step="any" inputMode="decimal" placeholder="—"
                aria-label={`Contado de ${x.nombre}`} aria-invalid={!contadoOk} value={c.contado ?? ""}
                onChange={(e) => cambiar(x.id, "contado", e.target.value)} style={{ height: 38 }} />
            );
            const minimoInput = (
              <input className="inp num" type="number" min="0" step="any" inputMode="decimal"
                aria-label={`Stock mínimo de ${x.nombre}`} aria-invalid={!minimoOk}
                value={c.minimo ?? (Number(x.stock_minimo) > 0 ? Number(x.stock_minimo) : "")} placeholder="0"
                onChange={(e) => cambiar(x.id, "minimo", e.target.value)} style={{ height: 38 }} />
            );
            const sistema = (
              <span className="num" style={{ fontWeight: 600, color: negativo ? "var(--danger)" : undefined, display: "inline-flex", flexDirection: "column", alignItems: "inherit" }}>
                <span>{fmtCant(x.stock)}{unidad(x)}</span>
                {movido && <span className="muted" style={{ fontSize: 11, fontWeight: 500 }}>al contar: {fmtCant(visto)}</span>}
              </span>
            );
            const nombre = (
              <span style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 2 }}>
                <strong style={{ overflowWrap: "break-word" }}>{x.nombre}</strong>
                <span className="muted" style={{ fontSize: 12 }}>
                  {tipo === "productos" ? [x.categoria, x.codigo].filter(Boolean).join(" · ") : x.unidad}
                  {recontar[tipo]?.[x.id] && <span className="chip warn" style={{ marginLeft: 6 }}>Recontar</span>}
                </span>
              </span>
            );
            const marca = editado ? { boxShadow: "inset 3px 0 0 var(--accent)", background: "var(--surface-2)" } : {};
            return isMobile ? (
              <div key={x.id} style={{ padding: "12px 14px", borderBottom: "1px solid var(--border-2)", display: "flex", flexDirection: "column", gap: 8, ...marca }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "flex-start" }}>
                  {nombre}
                  {contado !== null && <Diferencia antes={visto} despues={contado} />}
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, alignItems: "start" }}>
                  <span style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    <span className="lbl">Sistema</span>
                    <span style={{ minHeight: 38, display: "flex", alignItems: "center" }}>{sistema}</span>
                  </span>
                  <span style={{ display: "flex", flexDirection: "column", gap: 4 }}><span className="lbl">Contado</span>{contadoInput}</span>
                  <span style={{ display: "flex", flexDirection: "column", gap: 4 }}><span className="lbl">Mínimo</span>{minimoInput}</span>
                </div>
              </div>
            ) : (
              <div key={x.id} className="tr" style={{ gridTemplateColumns: columnas, ...marca }}>
                {nombre}
                <span className="r">{sistema}</span>
                {contadoInput}
                <span>{contado !== null ? <Diferencia antes={visto} despues={contado} /> : <span className="muted">—</span>}</span>
                {minimoInput}
              </div>
            );
          })}
        </div>
      )}

      {pendientes.length > 0 && (
        <div className="card aviso-entrar" style={{
          position: "sticky", bottom: isMobile ? 84 : 16, zIndex: 5, padding: "10px 14px", display: "flex", gap: 12,
          alignItems: "center", flexWrap: "wrap", boxShadow: "0 6px 20px rgba(var(--sombra), .12)",
        }}>
          <span style={{ fontSize: 14 }}>
            <strong>{nConteos}</strong> {nConteos === 1 ? "conteo" : "conteos"} · <strong>{nMinimos}</strong> {nMinimos === 1 ? "mínimo" : "mínimos"}
            {hayMalos && <span style={{ color: "var(--danger)" }}> · revisa los marcados: sin negativos y hasta 3 decimales</span>}
          </span>
          <button type="button" className="btn btn-p" style={{ marginLeft: "auto" }} disabled={hayMalos} onClick={() => setRevisando(true)}>
            Revisar y guardar
          </button>
        </div>
      )}

      {revisando && (
        <Modal titulo="Revisar el conteo" onClose={() => !guardando && setRevisando(false)} ancho={560}>
          <ErrorBanner mensaje={error} />
          <span className="muted" style={{ fontSize: 14 }}>
            Cada ajuste queda en la auditoría como "conteo físico". Si algo se vendió o se compró mientras contabas, esa fila no se toca y te
            avisamos para recontarla.
          </span>
          <div className="tabla" style={{ maxHeight: "50vh", overflowY: "auto" }}>
            {pendientes.map((p) => (
              <div key={p.x.id} className="tr" style={{ gridTemplateColumns: "minmax(0, 1fr) auto", minWidth: 0 }}>
                <span style={{ overflowWrap: "break-word", minWidth: 0 }}>{p.x.nombre}</span>
                <span className="num" style={{ fontSize: 13, textAlign: "right", display: "flex", flexDirection: "column", gap: 2 }}>
                  {p.cuenta && <span>stock {fmtCant(actual.visto[p.x.id])} → <strong>{fmtCant(p.contado)}</strong>{unidad(p.x)}</span>}
                  {p.fijaMinimo && <span className="muted">mínimo {fmtCant(p.x.stock_minimo)} → {fmtCant(p.minimo)}</span>}
                </span>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
            <button type="button" className="btn btn-s" disabled={guardando} onClick={() => setRevisando(false)}>Seguir contando</button>
            <button type="button" className="btn btn-p" disabled={guardando} onClick={guardar}>
              {guardando ? "Guardando…" : "Guardar conteo"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
