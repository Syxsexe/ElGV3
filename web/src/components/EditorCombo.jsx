// Editor de lo que lleva un combo: productos fijos y grupos de los que el
// cliente elige una opción al pedirlo (ej. "Bebida"), con recargo opcional.
// Abajo, en vivo: costo y margen (un rango si hay grupos: con la opción más
// barata y con la más cara), cuántos combos alcanzan y lo que impide venderlo.
//
// productos: [{id, nombre, activo, costo, stock, categoria_tipo, alcanza}] (todos).
// fijos: [{id, cantidad}]; grupos: [{nombre, cantidad, opciones: [{id, recargo}]}]
// con cantidades y recargos como texto (se mandan tal cual a la API).
import { useMemo, useState } from "react";
import ElegirProducto from "./ElegirProducto";
import { IconoQuitar } from "./Iconos";
import { Seccion } from "./Modal";
import { fmt, fmtCant } from "../format";

const pct = (ganancia, precio) => (precio > 0 ? Math.round((ganancia / precio) * 100) : null);
const rango = (a, b, f) => (a === b ? f(a) : `${f(a)} – ${f(b)}`);

// Unidades para vender de un producto: stock en la tienda, platos que
// alcanzan en la cocina; null = sin límite (plato sin receta).
const unidades = (p) => {
  if (!p) return 0;
  if (p.categoria_tipo === "tienda") return Math.max(Number(p.stock) || 0, 0);
  return p.alcanza == null ? null : Number(p.alcanza);
};

// Lo mismo que calcula la base (0024): costo, margen, alcanza y bloqueos.
function resumenCombo(porId, fijos, grupos, precio) {
  const costo = (id) => Number(porId.get(id)?.costo || 0);
  const costoFijo = fijos.reduce((s, l) => s + Number(l.cantidad || 0) * costo(l.id), 0);

  let costoMin = costoFijo, costoMax = costoFijo;
  // Cada combinación de opciones: {recargo, costo}. El margen se mira sobre lo
  // cobrado (precio + recargos): más plata no siempre es más porcentaje.
  let combinaciones = [{ recargo: 0, costo: 0 }];
  let sinOpciones = false;
  const avisos = [];
  const limites = [];

  for (const l of fijos) {
    const p = porId.get(l.id);
    if (p && !p.activo) avisos.push({ grave: true, texto: `${p.nombre} está desactivado: el combo no se puede vender.` });
    const u = unidades(p);
    if (u != null && Number(l.cantidad) > 0) limites.push(Math.floor(u / Number(l.cantidad)));
  }
  for (const g of grupos) {
    const cant = Number(g.cantidad || 0);
    const activas = g.opciones.filter((o) => porId.get(o.id)?.activo);
    for (const o of g.opciones) {
      const p = porId.get(o.id);
      if (p && !p.activo) avisos.push({ grave: false, texto: `${p.nombre} está desactivado: no se ofrece en ${g.nombre || "el grupo"}.` });
    }
    if (!activas.length) {
      avisos.push({ grave: true, texto: `${g.nombre || "Un grupo"} no tiene opciones activas: el combo no se puede vender.` });
      limites.push(0);
      sinOpciones = true;
      continue;
    }
    const costos = activas.map((o) => cant * costo(o.id));
    costoMin += Math.min(...costos);
    costoMax += Math.max(...costos);
    combinaciones = combinaciones.flatMap((c) => activas.map((o) => ({
      recargo: c.recargo + Number(o.recargo || 0), costo: c.costo + cant * costo(o.id),
    })));
    const u = activas.map((o) => unidades(porId.get(o.id)));
    if (cant > 0 && !u.includes(null)) limites.push(u.reduce((s, x) => s + Math.floor(x / cant), 0));
  }
  const margenes = sinOpciones ? [] : combinaciones
    .map((c) => pct(precio + c.recargo - costoFijo - c.costo, precio + c.recargo)).filter((m) => m != null);
  return {
    costoMin, costoMax,
    margenMin: margenes.length ? Math.min(...margenes) : null, margenMax: margenes.length ? Math.max(...margenes) : null,
    alcanza: limites.length ? Math.min(...limites) : null,
    avisos,
  };
}

// Un producto ya elegido: nombre y categoría (para cambiarlo, se quita y se
// busca otro). Si está inactivo se avisa.
function NombreProducto({ p }) {
  return (
    <span style={{ flexGrow: 1, minWidth: 0, display: "flex", flexDirection: "column" }}>
      <span style={{ fontSize: 14, fontWeight: 600, overflowWrap: "break-word" }}>
        {p?.nombre || "Producto"}{p && !p.activo && <span className="chip bad" style={{ marginLeft: 6 }}>Inactivo</span>}
      </span>
      {p?.categoria && <span className="muted" style={{ fontSize: 12 }}>{p.categoria}</span>}
    </span>
  );
}

// Categorías con productos activos que todavía no están en el grupo.
function categoriasLibres(productos, usados) {
  const cuenta = new Map();
  for (const p of productos) {
    if (p.activo && p.categoria && !usados.has(p.id)) cuenta.set(p.categoria, (cuenta.get(p.categoria) || 0) + 1);
  }
  return [...cuenta.entries()].sort((a, b) => a[0].localeCompare(b[0], "es"));
}

const MAX_OPCIONES = 100; // el servidor no acepta más por grupo

function Grupo({ grupo, productos, porId, onChange, onQuitar }) {
  const [buscando, setBuscando] = useState(false);
  const [elegida, setElegida] = useState("");
  const [aviso, setAviso] = useState("");
  const cambiar = (campo) => (e) => onChange({ ...grupo, [campo]: e.target.value });
  const usados = useMemo(() => new Set(grupo.opciones.map((o) => o.id)), [grupo.opciones]);
  const cambiarOpcion = (i, campo, valor) =>
    onChange({ ...grupo, opciones: grupo.opciones.map((o, j) => (j === i ? { ...o, [campo]: valor } : o)) });
  const costoDe = (id) => Number(porId.get(id)?.costo || 0);
  const libres = categoriasLibres(productos, usados);
  // Si la categoría elegida ya no tiene productos libres, se olvida.
  const categoria = libres.some(([c]) => c === elegida) ? elegida : "";
  const agregarCategoria = () => {
    const nuevas = productos.filter((p) => p.activo && p.categoria === categoria && !usados.has(p.id))
      .sort((a, b) => a.nombre.localeCompare(b.nombre, "es"))
      .map((p) => ({ id: p.id, recargo: "" }));
    const caben = Math.max(MAX_OPCIONES - grupo.opciones.length, 0);
    setAviso(nuevas.length > caben
      ? `Se agregaron ${caben} de ${nuevas.length}: un grupo admite hasta ${MAX_OPCIONES} opciones.` : "");
    onChange({ ...grupo, opciones: [...grupo.opciones, ...nuevas.slice(0, caben)] });
    setElegida("");
  };

  return (
    <div className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10, background: "var(--surface-2)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input className="inp" required placeholder="Nombre del grupo (ej. Bebida)" aria-label="Nombre del grupo"
          value={grupo.nombre} onChange={cambiar("nombre")} style={{ flexGrow: 1, minWidth: 0 }} />
        <input className="inp num" inputMode="decimal" required aria-label="Unidades por combo" title="Unidades de la opción por combo"
          value={grupo.cantidad} onChange={cambiar("cantidad")} style={{ width: 70 }} />
        <span className="muted" style={{ fontSize: 13 }}>und</span>
        <button type="button" className="step" aria-label={`Quitar el grupo ${grupo.nombre}`} onClick={onQuitar}><IconoQuitar /></button>
      </div>
      <span className="muted" style={{ fontSize: 12 }}>
        {grupo.opciones.length ? `${grupo.opciones.length} ${grupo.opciones.length === 1 ? "opción" : "opciones"} · recargo: lo que se suma al precio del combo`
          : "Sin opciones todavía: busca productos o agrega una categoría completa."}
      </span>
      {grupo.opciones.map((o, i) => (
        <div key={o.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <NombreProducto p={porId.get(o.id)} />
          <span className="muted" style={{ fontSize: 13 }}>+$</span>
          <input className="inp num" inputMode="decimal" placeholder="0" aria-label={`Recargo de ${porId.get(o.id)?.nombre || "la opción"}`}
            value={o.recargo} onChange={(e) => cambiarOpcion(i, "recargo", e.target.value)} style={{ width: 90 }} />
          <span className="muted num" style={{ width: 76, fontSize: 12, textAlign: "right" }} title="Costo de la opción por combo">
            {fmt(Number(grupo.cantidad || 0) * costoDe(o.id))}
          </span>
          <button type="button" className="step" aria-label={`Quitar ${porId.get(o.id)?.nombre || "la opción"}`}
            onClick={() => onChange({ ...grupo, opciones: grupo.opciones.filter((_, j) => j !== i) })}><IconoQuitar /></button>
        </div>
      ))}
      {buscando ? (
        <ElegirProducto productos={productos} excluir={usados} etiqueta={`Buscar opción para ${grupo.nombre || "el grupo"}`}
          onElegir={(p) => onChange({ ...grupo, opciones: [...grupo.opciones, { id: p.id, recargo: "" }] })}
          onCerrar={() => setBuscando(false)} />
      ) : (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button type="button" className="btn btn-g" style={{ height: 34 }} onClick={() => setBuscando(true)}>+ Opción</button>
          {libres.length > 0 && (
            <>
              <select className="inp" aria-label="Agregar toda una categoría" value={categoria} onChange={(e) => setElegida(e.target.value)}
                style={{ width: "auto", height: 34, flexShrink: 1, minWidth: 0 }}>
                <option value="">+ Toda una categoría…</option>
                {libres.map(([c, n]) => <option key={c} value={c}>{c} ({n})</option>)}
              </select>
              {categoria && <button type="button" className="btn btn-s" style={{ height: 34 }} onClick={agregarCategoria}>Agregar</button>}
            </>
          )}
        </div>
      )}
      {aviso && <span className="chip warn" style={{ alignSelf: "flex-start", height: "auto", padding: "4px 10px", whiteSpace: "normal" }}>{aviso}</span>}
    </div>
  );
}

export default function EditorCombo({ productos, fijos, grupos, precio, onFijos, onGrupos }) {
  const [buscandoFijo, setBuscandoFijo] = useState(false);
  const porId = useMemo(() => new Map(productos.map((p) => [p.id, p])), [productos]);
  const enFijos = useMemo(() => new Set(fijos.map((l) => l.id)), [fijos]);
  const r = resumenCombo(porId, fijos, grupos, precio);
  const costoDe = (id) => Number(porId.get(id)?.costo || 0);
  // Un grupo nuevo arranca vacío: nada de un producto puesto al azar.
  // Clave estable por grupo: el buscador abierto de uno no pasa a otro al quitar grupos.
  const nuevoGrupo = () => onGrupos([...grupos, {
    clave: `nuevo-${Date.now()}-${grupos.length}`, nombre: grupos.length ? "" : "Bebida", cantidad: "1", opciones: [],
  }]);

  return (
    <>
      <Seccion etiqueta="Productos fijos (siempre los lleva)">
        {fijos.length === 0 && <span className="muted" style={{ fontSize: 13 }}>Sin productos fijos.</span>}
        {fijos.map((l, i) => (
          <div key={l.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <NombreProducto p={porId.get(l.id)} />
            <input className="inp num" inputMode="decimal" required aria-label={`Cantidad de ${porId.get(l.id)?.nombre || "producto"}`}
              value={l.cantidad} onChange={(e) => onFijos(fijos.map((x, j) => (j === i ? { ...x, cantidad: e.target.value } : x)))}
              style={{ width: 80 }} />
            <span className="muted" style={{ fontSize: 13 }}>und</span>
            <span className="muted num" style={{ width: 76, fontSize: 12, textAlign: "right" }} title="Costo por combo">
              {fmt(Number(l.cantidad || 0) * costoDe(l.id))}
            </span>
            <button type="button" className="step" aria-label={`Quitar ${porId.get(l.id)?.nombre || "producto"}`}
              onClick={() => onFijos(fijos.filter((_, j) => j !== i))}><IconoQuitar /></button>
          </div>
        ))}
        {buscandoFijo ? (
          <ElegirProducto productos={productos} excluir={enFijos} etiqueta="Buscar producto fijo"
            onElegir={(p) => onFijos([...fijos, { id: p.id, cantidad: "1" }])} onCerrar={() => setBuscandoFijo(false)} />
        ) : (
          <button type="button" className="btn btn-g" style={{ alignSelf: "flex-start", height: 34 }} onClick={() => setBuscandoFijo(true)}>
            + Agregar producto fijo
          </button>
        )}
      </Seccion>

      <Seccion etiqueta="Para elegir al pedirlo">
        {grupos.length === 0 && (
          <span className="muted" style={{ fontSize: 13 }}>
            Sin grupos. Agrega uno si el cliente escoge algo, por ejemplo la bebida: así no hace falta un combo por cada bebida.
          </span>
        )}
        {grupos.map((g, i) => (
          <Grupo key={g.clave ?? i} grupo={g} productos={productos} porId={porId}
            onChange={(nuevo) => onGrupos(grupos.map((x, j) => (j === i ? nuevo : x)))}
            onQuitar={() => onGrupos(grupos.filter((_, j) => j !== i))} />
        ))}
        <button type="button" className="btn btn-g" style={{ alignSelf: "flex-start", height: 34 }} onClick={nuevoGrupo}>+ Grupo para elegir</button>
      </Seccion>

      <div className="card" role="status" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 6, background: "var(--surface-2)" }}>
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 14 }}>
          <span>Costo <strong className="num">{rango(r.costoMin, r.costoMax, fmt)}</strong></span>
          <span>Margen <strong className="num">
            {r.margenMin == null ? "—" : rango(r.margenMin, r.margenMax, (x) => `${x}%`)}
          </strong></span>
          <span>Alcanza <strong className="num">{r.alcanza == null ? "sin límite" : fmtCant(r.alcanza)}</strong></span>
        </div>
        {grupos.length > 0 && r.costoMin !== r.costoMax && (
          <span className="muted" style={{ fontSize: 12 }}>El costo y el margen dependen de lo que elija el cliente.</span>
        )}
        {r.avisos.map((a) => (
          <span key={a.texto} className={`chip ${a.grave ? "bad" : "warn"}`} style={{ alignSelf: "flex-start", height: "auto", padding: "4px 10px", whiteSpace: "normal" }}>
            {a.texto}
          </span>
        ))}
      </div>
    </>
  );
}
