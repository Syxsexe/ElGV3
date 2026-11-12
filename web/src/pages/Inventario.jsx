import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import EditorCombo from "../components/EditorCombo";
import Modal, { Campo, ErrorBanner, Seccion } from "../components/Modal";
import { fmt, fmtCant, fmtCosto, margen } from "../format";
import { useIsMobile } from "../useMediaQuery";
import { IconoQuitar } from "../components/Iconos";
import { unaVez } from "../formularios";

// Productos de tienda y platos de cocina son el mismo tipo de artículo
// (producto); los separa el tipo de su categoría.
const PESTANAS = [
  ["tienda", "Productos de tienda"],
  ["cocina", "Platos de cocina"],
  ["combo", "Combos"],
  ["adicional", "Adicionales"],
  ["servicio", "Servicios"],
  ["insumos", "Insumos"],
  ["categorias", "Categorías"],
];
const PERMISO_TIPO = { combo: "combos.editar" };
const tipoDePestana = (p) => (p === "tienda" || p === "cocina" ? "producto" : p);
const permisoDe = (tipo) => PERMISO_TIPO[tipo] || "inventario.editar";

// "" en un campo opcional → null (la API lo toma como "sin dato").
const opcional = (v) => (v === "" || v == null ? null : v);

function Fila({ columnas, onClick, children }) {
  return (
    <div className="tr" style={{ gridTemplateColumns: columnas, cursor: onClick ? "pointer" : "default" }} onClick={onClick}>
      {children}
    </div>
  );
}

function Estado({ activo }) {
  return <span className={`chip ${activo ? "ok" : "neu"}`}>{activo ? "Activo" : "Inactivo"}</span>;
}

// ── Modal de artículo (los cuatro tipos) ───────────────────────────────────

// categoriaTipo (al crear un producto): "tienda" o "cocina", según la pestaña.
function ModalArticulo({ tipo, articuloId, categoriaTipo, catalogos, onClose, onGuardado, onStockAjustado }) {
  const { impuestos, insumos, productos } = catalogos;
  const nuevo = !articuloId;
  const categorias = nuevo && categoriaTipo ? catalogos.categorias.filter((c) => c.tipo === categoriaTipo) : catalogos.categorias;
  // Nuevo: el formulario arranca vacío; editar: se llena con el detalle del servidor.
  const [f, setF] = useState(() => (nuevo ? {
    nombre: "", categoria_id: categorias[0]?.id || "", impuesto_id: "", precio_venta: "", activo: true,
    codigo: "", precio_costo: "", stock: "", stock_minimo: "", receta: [], descripcion: "", productos: [], grupos: [],
    insumo_id: insumos.find((i) => i.activo)?.id || "", cantidad: "",
  } : null));
  const [error, setError] = useState("");
  const [ajuste, setAjuste] = useState({ contado: "", motivo: "" });

  useEffect(() => {
    if (nuevo) return;
    api.articulo(articuloId).then((a) => setF({
      ...a,
      impuesto_id: a.impuesto_id,
      codigo: a.codigo || "", descripcion: a.descripcion || "",
      precio_costo: a.precio_costo ?? "", stock_minimo: a.stock_minimo ?? "",
      insumo_id: a.adicional_insumo_id || "", cantidad: a.adicional_cantidad ?? "",
      receta: (a.receta || []).map((r) => ({ id: r.insumo_id || r.producto_id, clase: r.insumo_id ? "insumo" : "producto", cantidad: String(r.cantidad) })),
      productos: (a.productos || []).map((p) => ({ id: p.producto_id, cantidad: String(p.cantidad) })),
      grupos: (a.grupos || []).map((g) => ({
        nombre: g.nombre, cantidad: String(g.cantidad),
        opciones: g.opciones.map((o) => ({ id: o.producto_id, recargo: Number(o.recargo) ? String(o.recargo) : "" })),
      })),
    })).catch((err) => setError(err.message));
  }, [articuloId, nuevo]);

  if (!f) return <Modal titulo="Cargando…" onClose={onClose}><ErrorBanner mensaje={error} /></Modal>;

  const cambiar = (campo) => (e) => {
    const valor = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setF((x) => ({ ...x, [campo]: valor }));
  };
  const categoria = categorias.find((c) => c.id === f.categoria_id);
  const esCocina = categoria?.tipo === "cocina";
  const conReceta = tipo === "producto" && (esCocina || f.receta.length > 0);
  const impuestosValidos = tipo === "combo" ? impuestos.filter((i) => i.tributo === "INC") : impuestos;
  const unidadDe = (id) => insumos.find((i) => i.id === id)?.unidad || "";

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    const body = {
      nombre: f.nombre, categoria_id: f.categoria_id, precio_venta: f.precio_venta,
      impuesto_id: opcional(f.impuesto_id),
    };
    if (!nuevo) body.activo = f.activo;
    if (tipo === "producto") {
      Object.assign(body, { codigo: opcional(f.codigo), stock_minimo: opcional(f.stock_minimo) || "0" });
      if (!f.receta.length) body.precio_costo = opcional(f.precio_costo) || "0";
      if (conReceta || !nuevo) {
        body.receta = f.receta.map((r) => (r.clase === "producto"
          ? { producto_id: r.id, cantidad: r.cantidad } : { insumo_id: r.id, cantidad: r.cantidad }));
      }
      if (nuevo && !esCocina) body.stock = opcional(f.stock);
      if (esCocina) { delete body.codigo; body.stock_minimo = "0"; }
    }
    if (tipo === "combo") {
      body.descripcion = opcional(f.descripcion);
      body.productos = f.productos.map((p) => ({ producto_id: p.id, cantidad: p.cantidad }));
      body.grupos = f.grupos.map((g) => ({
        nombre: g.nombre, cantidad: g.cantidad,
        opciones: g.opciones.map((o) => ({ producto_id: o.id, recargo: o.recargo || "0" })),
      }));
    }
    if (tipo === "adicional") Object.assign(body, { insumo_id: f.insumo_id, cantidad: f.cantidad });
    try {
      if (nuevo) await api.crearArticulo({ tipo, ...body });
      else await api.editarArticulo(articuloId, body);
      onGuardado();
    } catch (err) {
      setError(err.message);
    }
  };

  const ajustar = async () => {
    setError("");
    try {
      const a = await api.ajustarStock(articuloId, ajuste.contado, ajuste.motivo);
      setF((x) => ({ ...x, stock: a.stock }));
      setAjuste({ contado: "", motivo: "" });
      onStockAjustado(); // el ajuste ya quedó guardado: la lista de atrás se actualiza aunque se cancele
    } catch (err) {
      setError(err.message);
    }
  };

  const nombreTipo = tipo === "producto" ? (esCocina ? "plato de cocina" : "producto de tienda")
    : { combo: "combo", adicional: "adicional", servicio: "servicio" }[tipo];
  const titulo = `${nuevo ? "Nuevo" : "Editar"} ${nombreTipo}`;
  return (
    <Modal titulo={titulo} onClose={onClose} ancho={560}>
      <form onSubmit={unaVez(guardar)} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Campo etiqueta="Nombre">
          <input className="inp" required value={f.nombre} onChange={cambiar("nombre")} />
        </Campo>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
          <Campo etiqueta="Categoría">
            <select className="inp" value={f.categoria_id} onChange={cambiar("categoria_id")}>
              {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre} ({c.tipo})</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Precio de venta">
            <input className="inp num" inputMode="decimal" required value={f.precio_venta} onChange={cambiar("precio_venta")} />
          </Campo>
          <Campo etiqueta="Impuesto">
            <select className="inp" value={f.impuesto_id || ""} onChange={cambiar("impuesto_id")}>
              {nuevo && <option value="">Según la categoría</option>}
              {impuestosValidos.map((i) => <option key={i.id} value={i.id}>{i.nombre}</option>)}
            </select>
          </Campo>
        </div>

        {tipo === "producto" && esCocina && !f.receta.length && (
          <Campo etiqueta="Costo (a mano, sin receta)" ayuda="Con receta, el costo lo calcula la suma de sus ingredientes.">
            <input className="inp num" inputMode="decimal" value={f.precio_costo} onChange={cambiar("precio_costo")} style={{ maxWidth: 200 }} />
          </Campo>
        )}
        {tipo === "producto" && !esCocina && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
            <Campo etiqueta="Código (opcional)">
              <input className="inp" value={f.codigo} onChange={cambiar("codigo")} />
            </Campo>
            <Campo etiqueta="Costo" ayuda={f.receta.length ? "Lo calcula la receta" : undefined}>
              <input className="inp num" inputMode="decimal" disabled={f.receta.length > 0}
                value={f.receta.length ? (f.costo ?? "") : f.precio_costo} onChange={cambiar("precio_costo")} />
            </Campo>
            {nuevo && (
              <Campo etiqueta="Stock inicial">
                <input className="inp num" inputMode="decimal" value={f.stock} onChange={cambiar("stock")} />
              </Campo>
            )}
            <Campo etiqueta="Stock mínimo">
              <input className="inp num" inputMode="decimal" value={f.stock_minimo} onChange={cambiar("stock_minimo")} />
            </Campo>
          </div>
        )}
        {conReceta && (
          <Seccion etiqueta="Receta (por plato)">
            <RecetaPlato lineas={f.receta} insumos={insumos} precio={Number(f.precio_venta) || 0}
              productos={productos.filter((p) => p.categoria_tipo === "tienda" && p.id !== articuloId)}
              onChange={(receta) => setF((x) => ({ ...x, receta }))} />
          </Seccion>
        )}

        {tipo === "combo" && (
          <>
            <Campo etiqueta="Descripción (opcional)">
              <input className="inp" value={f.descripcion} onChange={cambiar("descripcion")} />
            </Campo>
            <EditorCombo productos={productos} fijos={f.productos} grupos={f.grupos} precio={Number(f.precio_venta) || 0}
              onFijos={(lista) => setF((x) => ({ ...x, productos: lista }))}
              onGrupos={(lista) => setF((x) => ({ ...x, grupos: lista }))} />
          </>
        )}

        {tipo === "adicional" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 140px", gap: 12 }}>
            <Campo etiqueta="Insumo">
              <select className="inp" value={f.insumo_id} onChange={cambiar("insumo_id")}>
                {insumos.filter((i) => i.activo || i.id === f.insumo_id).map((i) => (
                  <option key={i.id} value={i.id}>{i.nombre}{i.activo ? "" : " (inactivo)"}</option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta={`Porción (${unidadDe(f.insumo_id)})`}>
              <input className="inp num" inputMode="decimal" required value={f.cantidad} onChange={cambiar("cantidad")} />
            </Campo>
          </div>
        )}

        {!nuevo && tipo !== "combo" && (
          <div className="muted" style={{ fontSize: 13 }}>
            Costo actual {fmt(f.costo || 0)} · margen {margen(f.precio_venta, f.costo || 0)}
          </div>
        )}
        {!nuevo && (
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={f.activo} onChange={cambiar("activo")} />
            <span>Activo (se ofrece para vender)</span>
          </label>
        )}

        {!nuevo && tipo === "producto" && !esCocina && (
          <div className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8, background: "var(--surface-2)" }}>
            <span className="lbl">Stock actual: {fmtCant(f.stock)} · ajustar por conteo físico</span>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <input className="inp num" inputMode="decimal" placeholder="Contado" style={{ width: 110 }}
                value={ajuste.contado} onChange={(e) => setAjuste((a) => ({ ...a, contado: e.target.value }))} />
              <input className="inp" placeholder="Motivo (ej. conteo semanal)" style={{ flexGrow: 1, width: 160 }}
                value={ajuste.motivo} onChange={(e) => setAjuste((a) => ({ ...a, motivo: e.target.value }))} />
              <button type="button" className="btn btn-s" disabled={!ajuste.contado || !ajuste.motivo.trim()} onClick={ajustar}>Ajustar</button>
            </div>
          </div>
        )}

        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-p">Guardar</button>
        </div>
      </form>
    </Modal>
  );
}

// Receta de un plato: insumos, preparaciones o productos de la tienda, cada uno
// con su costo por cantidad. Abajo, el costo total, el margen con el precio de
// venta y cuántos platos alcanzan con el stock de hoy.
function RecetaPlato({ lineas, insumos, productos, precio, onChange }) {
  const isMobile = useIsMobile();
  const opciones = [
    ...insumos.filter((i) => !i.es_preparacion).map((i) => ({ ...i, clase: "insumo", grupo: "Insumos", costoUnit: Number(i.costo) })),
    ...insumos.filter((i) => i.es_preparacion).map((i) => ({ ...i, clase: "insumo", grupo: "Preparaciones", costoUnit: Number(i.costo) })),
    ...productos.map((p) => ({ id: p.id, nombre: p.nombre, activo: p.activo, unidad: "und", stock: p.stock,
      clase: "producto", grupo: "Productos de la tienda", costoUnit: Number(p.precio_costo) })),
  ];
  const deId = new Map(opciones.map((o) => [o.id, o]));
  const usados = new Set(lineas.map((l) => l.id));
  const disponible = (o) => o.activo !== false && !usados.has(o.id);
  const cambiar = (i, cambios) => onChange(lineas.map((l, j) => (j === i ? { ...l, ...cambios } : l)));
  const libre = opciones.find(disponible);
  const filas = lineas.map((l) => {
    const o = deId.get(l.id);
    const cant = Number(l.cantidad) || 0;
    return { ...l, o, subtotal: o ? cant * o.costoUnit : 0, alcanza: o && cant > 0 ? Math.floor(Math.max(Number(o.stock), 0) / cant) : null };
  });
  const costo = Math.round(filas.reduce((s, f) => s + f.subtotal, 0) * 100) / 100;
  const alcanza = filas.length ? Math.min(...filas.map((f) => (f.alcanza == null ? Infinity : f.alcanza))) : null;
  const grupos = ["Insumos", "Preparaciones", "Productos de la tienda"];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {lineas.length === 0 && <span className="muted" style={{ fontSize: 13 }}>Sin receta: el costo se escribe a mano.</span>}
      {filas.map((l, i) => (
        <div key={i} style={{ display: "grid", gap: 8, alignItems: "center",
          gridTemplateColumns: isMobile ? "84px 36px minmax(0, 1fr) auto" : "minmax(0, 1fr) 84px 36px 90px auto",
          ...(isMobile && { paddingBottom: 8, borderBottom: "1px solid var(--border-2)" }) }}>
          <select className="inp" aria-label={`Ingrediente ${i + 1}`} value={l.id} style={{ minWidth: 0, gridColumn: isMobile ? "1 / -1" : undefined }}
            onChange={(e) => cambiar(i, { id: e.target.value, clase: deId.get(e.target.value)?.clase || "insumo" })}>
            {grupos.map((g) => {
              const lista = opciones.filter((o) => o.grupo === g && (o.id === l.id || disponible(o)));
              return lista.length > 0 && (
                <optgroup key={g} label={g}>
                  {lista.map((o) => <option key={o.id} value={o.id}>{o.nombre}{o.activo === false ? " (inactivo)" : ""}</option>)}
                </optgroup>
              );
            })}
          </select>
          <input className="inp num" inputMode="decimal" required aria-label={`Cantidad de ${l.o?.nombre || "ingrediente"}`} value={l.cantidad}
            onChange={(e) => cambiar(i, { cantidad: e.target.value })} />
          <span className="muted" style={{ fontSize: 13 }}>{l.o?.unidad}</span>
          <span className="num" style={{ textAlign: "right", fontSize: 13 }} title={l.o ? `${fmtCosto(l.o.costoUnit)} por ${l.o.unidad}` : undefined}>
            {fmt(l.subtotal)}
          </span>
          <button type="button" className="step" aria-label={`Quitar ${l.o?.nombre || "ingrediente"}`} onClick={() => onChange(lineas.filter((_, j) => j !== i))}><IconoQuitar /></button>
        </div>
      ))}
      {libre && (
        <button type="button" className="btn btn-g" style={{ alignSelf: "flex-start", height: 34 }}
          onClick={() => onChange([...lineas, { id: libre.id, clase: libre.clase, cantidad: "1" }])}>+ Agregar ingrediente</button>
      )}
      {lineas.length > 0 && (
        <div role="status" aria-label="Costo del plato" style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "2px 12px", fontSize: 14,
          padding: "10px 12px", borderRadius: 10, background: "var(--surface-2)", border: "1px solid var(--border-2)" }}>
          <strong>Costo del plato</strong><strong className="num">{fmt(costo)}</strong>
          <span className="muted">Margen con el precio de venta</span><span className="num muted">{margen(precio, costo)}</span>
          {alcanza != null && Number.isFinite(alcanza) && (
            <><span className="muted">Alcanza hoy para</span>
              <span className="num" style={{ color: alcanza === 0 ? "var(--danger)" : undefined }}>{alcanza} {alcanza === 1 ? "plato" : "platos"}</span></>
          )}
        </div>
      )}
    </div>
  );
}

// ── Insumos y categorías ───────────────────────────────────────────────────

function ModalInsumo({ insumo, unidades, onClose, onGuardado, onAjustado }) {
  const nuevo = !insumo;
  const [f, setF] = useState({
    nombre: insumo?.nombre || "", unidad_medida_id: insumo?.unidad_medida_id || unidades[0]?.id || "",
    costo_unitario: insumo ? String(insumo.costo_unitario) : "", activo: insumo?.activo ?? true,
    stock: "", stock_minimo: insumo ? String(insumo.stock_minimo) : "",
  });
  const [stock, setStock] = useState(insumo?.stock);
  const [ajuste, setAjuste] = useState({ contado: "", motivo: "" });
  const [error, setError] = useState("");
  const cambiar = (campo) => (e) => setF((x) => ({ ...x, [campo]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    const body = { nombre: f.nombre, unidad_medida_id: f.unidad_medida_id, stock_minimo: f.stock_minimo || "0" };
    if (!insumo?.es_preparacion) body.costo_unitario = f.costo_unitario || "0";
    if (nuevo && f.stock !== "") body.stock = f.stock;
    if (!nuevo) body.activo = f.activo;
    try {
      if (nuevo) await api.crearInsumo(body); else await api.editarInsumo(insumo.id, body);
      onGuardado();
    } catch (err) {
      setError(err.message);
    }
  };

  const unidad = unidades.find((u) => u.id === f.unidad_medida_id)?.simbolo || "";
  return (
    <Modal titulo={nuevo ? "Nuevo insumo" : `Editar ${insumo.nombre}`} onClose={onClose}>
      <form onSubmit={unaVez(guardar)} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Campo etiqueta="Nombre">
          <input className="inp" required value={f.nombre} onChange={cambiar("nombre")} />
        </Campo>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <Campo etiqueta="Unidad">
            <select className="inp" value={f.unidad_medida_id} onChange={cambiar("unidad_medida_id")}>
              {unidades.map((u) => <option key={u.id} value={u.id}>{u.nombre} ({u.simbolo})</option>)}
            </select>
          </Campo>
          <Campo etiqueta={`Costo por ${unidad}`}
            ayuda={insumo?.es_preparacion ? "Preparación: lo calcula su receta." : "Ej. bolsa de 1000 g a $8.000 → 8"}>
            <input className="inp num" inputMode="decimal" disabled={insumo?.es_preparacion}
              value={insumo?.es_preparacion ? String(insumo.costo) : f.costo_unitario} onChange={cambiar("costo_unitario")} />
          </Campo>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          {nuevo && (
            <Campo etiqueta={`Stock inicial (${unidad})`}>
              <input className="inp num" inputMode="decimal" value={f.stock} onChange={cambiar("stock")} />
            </Campo>
          )}
          <Campo etiqueta={`Stock mínimo (${unidad})`} ayuda="Por debajo, sale en Inicio como stock bajo.">
            <input className="inp num" inputMode="decimal" value={f.stock_minimo} onChange={cambiar("stock_minimo")} />
          </Campo>
        </div>
        {!nuevo && (
          <div className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 8, background: "var(--surface-2)" }}>
            <span className="lbl">
              Stock actual: <span style={{ color: Number(stock) < 0 ? "var(--danger)" : undefined }}>{fmtCant(stock)} {unidad}</span> · ajustar por conteo físico
            </span>
            {insumo.es_preparacion && <span className="muted" style={{ fontSize: 12 }}>Para sumar lo que se preparó, usa Producir en Preparaciones.</span>}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <input className="inp num" inputMode="decimal" placeholder="Contado" aria-label="Contado" style={{ width: 110 }}
                value={ajuste.contado} onChange={(e) => setAjuste((a) => ({ ...a, contado: e.target.value }))} />
              <input className="inp" placeholder="Motivo (ej. conteo semanal)" aria-label="Motivo del ajuste" style={{ flexGrow: 1, width: 160 }}
                value={ajuste.motivo} onChange={(e) => setAjuste((a) => ({ ...a, motivo: e.target.value }))} />
              <button type="button" className="btn btn-s" disabled={!ajuste.contado || !ajuste.motivo.trim()} onClick={async () => {
                setError("");
                try {
                  const r = await api.ajustarStockInsumo(insumo.id, ajuste.contado, ajuste.motivo.trim());
                  setStock(r.stock);
                  setAjuste({ contado: "", motivo: "" });
                  onAjustado();
                } catch (err) { setError(err.message); }
              }}>Ajustar</button>
            </div>
          </div>
        )}
        {!nuevo && (
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={f.activo} onChange={cambiar("activo")} />
            <span>Activo</span>
          </label>
        )}
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-p">Guardar</button>
        </div>
      </form>
    </Modal>
  );
}

function Categorias({ categorias, puedeEditar, recargar }) {
  const [nueva, setNueva] = useState({ nombre: "", tipo: "tienda" });
  const [error, setError] = useState("");

  const hacer = async (accion) => {
    setError("");
    try {
      await accion();
      await recargar();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 640 }}>
      <p className="muted" style={{ margin: 0 }}>
        El tipo propone el impuesto (tienda → IVA 19%, cocina → INC 8%) y cómo se lleva el stock: en tienda, por producto; en cocina, por los insumos de la receta de cada plato.
      </p>
      <ErrorBanner mensaje={error} />
      {puedeEditar && (
        <form style={{ display: "flex", gap: 8 }} onSubmit={(e) => {
          e.preventDefault();
          hacer(() => api.crearCategoria(nueva)).then((ok) => ok && setNueva({ nombre: "", tipo: nueva.tipo }));
        }}>
          <input className="inp" placeholder="Nueva categoría" required value={nueva.nombre}
            onChange={(e) => setNueva((n) => ({ ...n, nombre: e.target.value }))} />
          <select className="inp" style={{ width: 120 }} value={nueva.tipo} onChange={(e) => setNueva((n) => ({ ...n, tipo: e.target.value }))}>
            <option value="tienda">Tienda</option>
            <option value="cocina">Cocina</option>
          </select>
          <button type="submit" className="btn btn-s">Agregar</button>
        </form>
      )}
      <div className="card tabla">
        <div className="th" style={{ gridTemplateColumns: "1fr 120px 90px 80px" }}>
          <span>Nombre</span><span>Tipo</span><span className="r">Artículos</span><span />
        </div>
        {categorias.map((c) => (
          <Fila key={c.id} columnas="1fr 120px 90px 80px">
            <span>{c.nombre}</span>
            {puedeEditar ? (
              <select className="inp" style={{ height: 32 }} value={c.tipo}
                onChange={(e) => hacer(() => api.editarCategoria(c.id, { tipo: e.target.value }))}>
                <option value="tienda">Tienda</option>
                <option value="cocina">Cocina</option>
              </select>
            ) : <span>{c.tipo}</span>}
            <span className="r num">{c.articulos}</span>
            <span className="r">
              {puedeEditar && c.articulos === 0 && (
                <button type="button" className="btn btn-d" style={{ height: 30, padding: "0 10px" }}
                  onClick={() => hacer(() => api.borrarCategoria(c.id))}>Borrar</button>
              )}
            </span>
          </Fila>
        ))}
      </div>
    </div>
  );
}

// ── Página ─────────────────────────────────────────────────────────────────

export default function Inventario() {
  const { puede } = useAuth();
  const [pestana, setPestana] = useState("tienda");
  const [busqueda, setBusqueda] = useState("");
  const [articulos, setArticulos] = useState([]);
  const [catalogos, setCatalogos] = useState({ categorias: [], impuestos: [], insumos: [], productos: [], unidades: [] });
  const [editando, setEditando] = useState(null); // {id} | {nuevo: true}
  const [error, setError] = useState("");

  const cargarCatalogos = useCallback(() => Promise.all([
    api.categorias(), api.impuestos(), api.insumos(), api.articulos({ tipo: "producto" }), api.unidades(),
  ]).then(([categorias, impuestos, insumos, productos, unidades]) => {
    setCatalogos({ categorias, impuestos, insumos, productos, unidades });
  }).catch((err) => setError(err.message)), []);

  // Cada búsqueda lleva un número: si una respuesta vieja llega tarde (otra
  // pestaña u otro texto), se descarta en vez de pisar la lista actual.
  const ultimaBusqueda = useRef(0);
  const cargarArticulos = useCallback(() => {
    if (pestana === "categorias") return Promise.resolve();
    const mia = ++ultimaBusqueda.current;
    const pedido = pestana === "insumos" ? api.insumos(busqueda.trim())
      : api.articulos({ tipo: tipoDePestana(pestana), q: busqueda.trim(), categoria_tipo: ["tienda", "cocina"].includes(pestana) ? pestana : undefined });
    return pedido.then((lista) => {
      if (mia !== ultimaBusqueda.current) return;
      setError("");
      setArticulos(lista);
    }).catch((err) => mia === ultimaBusqueda.current && setError(err.message));
  }, [pestana, busqueda]);

  useEffect(() => {
    cargarCatalogos();
  }, [cargarCatalogos]);
  useEffect(() => {
    const t = setTimeout(cargarArticulos, 200);
    return () => clearTimeout(t);
  }, [cargarArticulos]);

  const alGuardar = () => {
    setEditando(null);
    cargarArticulos();
    cargarCatalogos();
  };

  const esArticulo = !["insumos", "categorias"].includes(pestana);
  const puedeCrear = esArticulo ? puede(permisoDe(tipoDePestana(pestana))) : puede("inventario.editar");
  // Productos de tienda y platos se crean en una categoría de su tipo: sin ninguna, primero hay que crearla.
  const sinCategoria = ["tienda", "cocina"].includes(pestana) && !catalogos.categorias.some((c) => c.tipo === pestana);
  // El modal usa el tipo del artículo, no el de la pestaña.
  const abrir = (a) => setEditando({ id: a.id, tipo: a.tipo });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h1 style={{ fontSize: 28 }}>Inventario</h1>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {PESTANAS.map(([clave, etiqueta]) => (
          <button key={clave} type="button" className={`pill${pestana === clave ? " on" : ""}`}
            onClick={() => { setPestana(clave); setArticulos([]); }}>{etiqueta}</button>
        ))}
      </div>
      {pestana !== "categorias" && (
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <input className="inp" placeholder="Buscar por nombre o código" value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)} style={{ maxWidth: 360 }} />
          {puedeCrear && (
            <button type="button" className="btn btn-p" style={{ marginLeft: "auto" }} disabled={sinCategoria}
              onClick={() => setEditando({ nuevo: true })}>
              {{ tienda: "+ Nuevo producto", cocina: "+ Nuevo plato" }[pestana] || "+ Nuevo"}
            </button>
          )}
        </div>
      )}
      {pestana === "cocina" && (
        <div className="card" style={{ padding: "12px 16px", background: "var(--accent-soft)", borderColor: "transparent", fontSize: 14 }}>
          Aquí se crean los platos que prepara la cocina (hamburguesas, salchipapas, perros…). Su receta lleva insumos,
          preparaciones o productos de la tienda: el costo es la suma de cada ingrediente por su cantidad y el precio de
          venta lo pones tú. No llevan stock propio: al venderlos se descuentan sus ingredientes, y "Alcanza" dice cuántos
          salen con lo que hay.
        </div>
      )}
      {sinCategoria && (
        <div className="muted" role="status" style={{ fontSize: 14 }}>
          Para crear {pestana === "cocina" ? "platos" : "productos de tienda"}, primero crea una categoría de {pestana} en la pestaña Categorías.
        </div>
      )}
      <ErrorBanner mensaje={error} />

      {pestana === "tienda" && (
        <div className="card tabla">
          <div className="th" style={{ gridTemplateColumns: "1fr 140px 100px 100px 70px 90px 80px" }}>
            <span>Producto</span><span>Categoría</span><span className="r">Precio</span><span className="r">Costo</span>
            <span className="r">Margen</span><span className="r">Stock</span><span>Estado</span>
          </div>
          {articulos.map((a) => {
            const bajo = a.categoria_tipo === "tienda" && Number(a.stock) <= Number(a.stock_minimo);
            return (
              <Fila key={a.id} columnas="1fr 140px 100px 100px 70px 90px 80px" onClick={puede(permisoDe(a.tipo)) ? () => abrir(a) : undefined}>
                <span>
                  <strong>{a.nombre}</strong>
                  {(a.codigo || a.tiene_receta) && (
                    <span className="muted" style={{ display: "block", fontSize: 12 }}>
                      {[a.codigo, a.tiene_receta && "con receta"].filter(Boolean).join(" · ")}
                    </span>
                  )}
                </span>
                <span className="muted">{a.categoria}</span>
                <span className="r num">{fmt(a.precio_venta)}</span>
                <span className="r num">{fmt(a.costo)}</span>
                <span className="r num">{margen(a.precio_venta, a.costo)}</span>
                <span className="r">
                  {a.categoria_tipo === "tienda"
                    ? <span className={`chip num ${bajo ? "bad" : "ok"}`}>{fmtCant(a.stock)}</span>
                    : <span className="muted">—</span>}
                </span>
                <span><Estado activo={a.activo} /></span>
              </Fila>
            );
          })}
        </div>
      )}

      {pestana === "combo" && (
        <div className="card tabla">
          <div className="th" style={{ gridTemplateColumns: "1fr 100px 130px 90px 90px 80px" }}>
            <span>Nombre</span><span className="r">Precio</span><span className="r">Costo</span>
            <span className="r">Margen</span><span className="r">Alcanza</span><span>Estado</span>
          </div>
          {articulos.map((a) => {
            const conRango = a.costo_max != null && Number(a.costo_max) !== Number(a.costo);
            return (
              <Fila key={a.id} columnas="1fr 100px 130px 90px 90px 80px" onClick={puede(permisoDe(a.tipo)) ? () => abrir(a) : undefined}>
                <span>
                  <strong>{a.nombre}</strong>
                  {a.tiene_grupos && <span className="chip neu" style={{ marginLeft: 6 }}>Con opciones</span>}
                  {a.descripcion && <span className="muted" style={{ display: "block", fontSize: 12 }}>{a.descripcion}</span>}
                  {a.bloqueo && (
                    <span className="chip bad" style={{ display: "inline-flex", marginTop: 4, height: "auto", padding: "2px 8px", whiteSpace: "normal" }}>
                      No se puede vender: {a.bloqueo}
                    </span>
                  )}
                </span>
                <span className="r num">{fmt(a.precio_venta)}</span>
                <span className="r num">{conRango ? `${fmt(a.costo)} – ${fmt(a.costo_max)}` : fmt(a.costo)}</span>
                <span className="r num">
                  {a.margen_min == null ? "—" : a.margen_min === a.margen_max ? `${a.margen_min}%` : `${a.margen_min}% – ${a.margen_max}%`}
                </span>
                <span className="r">
                  {a.alcanza == null ? <span className="muted">—</span> : (
                    <span className={`chip num ${Number(a.alcanza) === 0 ? "bad" : Number(a.alcanza) <= 3 ? "warn" : "neu"}`}>{fmtCant(a.alcanza)}</span>
                  )}
                </span>
                <span><Estado activo={a.activo} /></span>
              </Fila>
            );
          })}
        </div>
      )}
      {(pestana === "adicional" || pestana === "servicio") && (
        <div className="card tabla">
          <div className="th" style={{ gridTemplateColumns: "1fr 140px 100px 100px 70px 80px" }}>
            <span>Nombre</span><span>Impuesto</span><span className="r">Precio</span><span className="r">Costo</span>
            <span className="r">Margen</span><span>Estado</span>
          </div>
          {articulos.map((a) => (
            <Fila key={a.id} columnas="1fr 140px 100px 100px 70px 80px" onClick={puede(permisoDe(a.tipo)) ? () => abrir(a) : undefined}>
              <span>
                <strong>{a.nombre}</strong>
                {a.descripcion && <span className="muted" style={{ display: "block", fontSize: 12 }}>{a.descripcion}</span>}
              </span>
              <span className="muted">{a.impuesto}</span>
              <span className="r num">{fmt(a.precio_venta)}</span>
              <span className="r num">{fmt(a.costo)}</span>
              <span className="r num">{margen(a.precio_venta, a.costo)}</span>
              <span><Estado activo={a.activo} /></span>
            </Fila>
          ))}
        </div>
      )}
      {pestana !== "categorias" && articulos.length === 0 && <div className="muted">Nada que mostrar.</div>}

      {pestana === "insumos" && (
        <div className="card tabla">
          <div className="th" style={{ gridTemplateColumns: "1fr 70px 120px 110px 120px 80px" }}>
            <span>Insumo</span><span>Unidad</span><span className="r">Costo por unidad</span><span className="r">Stock</span><span>Tipo</span><span>Estado</span>
          </div>
          {articulos.map((i) => (
            <Fila key={i.id} columnas="1fr 70px 120px 110px 120px 80px" onClick={puede("inventario.editar") ? () => setEditando({ insumo: i }) : undefined}>
              <strong>{i.nombre}</strong>
              <span className="muted">{i.unidad}</span>
              <span className="r num">{fmtCosto(i.costo)}</span>
              <span className="r">
                <span className={`chip num ${Number(i.stock) < 0 || (Number(i.stock_minimo) > 0 && Number(i.stock) <= Number(i.stock_minimo)) ? "bad" : "ok"}`}>
                  {fmtCant(i.stock)}
                </span>
              </span>
              <span>{i.es_preparacion ? <span className="chip neu">Preparación</span> : <span className="muted">Comprado</span>}</span>
              <span><Estado activo={i.activo} /></span>
            </Fila>
          ))}
        </div>
      )}

      {pestana === "categorias" && (
        <Categorias categorias={catalogos.categorias} puedeEditar={puede("inventario.editar")} recargar={cargarCatalogos} />
      )}

      {pestana === "cocina" && (
        <div className="card tabla">
          <div className="th" style={{ gridTemplateColumns: "1fr 140px 100px 100px 70px 90px 80px" }}>
            <span>Plato</span><span>Categoría</span><span className="r">Precio</span><span className="r">Costo</span>
            <span className="r">Margen</span><span className="r">Alcanza</span><span>Estado</span>
          </div>
          {articulos.map((a) => (
            <Fila key={a.id} columnas="1fr 140px 100px 100px 70px 90px 80px" onClick={puede(permisoDe(a.tipo)) ? () => abrir(a) : undefined}>
              <span>
                <strong>{a.nombre}</strong>
                <span className="muted" style={{ display: "block", fontSize: 12 }}>{a.tiene_receta ? "Con receta" : "Sin receta: costo a mano"}</span>
              </span>
              <span className="muted">{a.categoria}</span>
              <span className="r num">{fmt(a.precio_venta)}</span>
              <span className="r num">{fmt(a.costo)}</span>
              <span className="r num">{margen(a.precio_venta, a.costo)}</span>
              <span className="r">
                {a.alcanza == null ? <span className="muted">—</span>
                  : <span className={`chip num ${Number(a.alcanza) === 0 ? "bad" : "ok"}`}>{fmtCant(a.alcanza)}</span>}
              </span>
              <span><Estado activo={a.activo} /></span>
            </Fila>
          ))}
        </div>
      )}

      {editando && esArticulo && (
        <ModalArticulo tipo={editando.tipo || tipoDePestana(pestana)} articuloId={editando.id} catalogos={catalogos}
          categoriaTipo={["tienda", "cocina"].includes(pestana) ? pestana : undefined}
          onClose={() => setEditando(null)} onGuardado={alGuardar} onStockAjustado={cargarArticulos} />
      )}
      {editando && pestana === "insumos" && (
        <ModalInsumo insumo={editando.insumo} unidades={catalogos.unidades} onClose={() => setEditando(null)} onGuardado={alGuardar}
          onAjustado={() => { cargarArticulos(); cargarCatalogos(); }} />
      )}
    </div>
  );
}
