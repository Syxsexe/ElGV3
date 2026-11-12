// Editor de lo que lleva un combo: productos fijos y grupos de los que el
// cliente elige una opción al pedirlo (ej. "Bebida"), con recargo opcional.
// Abajo, en vivo: costo y margen (un rango si hay grupos: con la opción más
// barata y con la más cara), cuántos combos alcanzan y lo que impide venderlo.
//
// productos: [{id, nombre, activo, costo, stock, categoria_tipo, alcanza}] (todos).
// fijos: [{id, cantidad}]; grupos: [{nombre, cantidad, opciones: [{id, recargo}]}]
// con cantidades y recargos como texto (se mandan tal cual a la API).
import EditorLineas from "./EditorLineas";
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
function resumenCombo(productos, fijos, grupos, precio) {
  const porId = new Map(productos.map((p) => [p.id, p]));
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

function Grupo({ grupo, productos, onChange, onQuitar }) {
  const cambiar = (campo) => (e) => onChange({ ...grupo, [campo]: e.target.value });
  const usados = new Set(grupo.opciones.map((o) => o.id));
  const libre = productos.find((p) => p.activo && !usados.has(p.id));
  const cambiarOpcion = (i, campo, valor) =>
    onChange({ ...grupo, opciones: grupo.opciones.map((o, j) => (j === i ? { ...o, [campo]: valor } : o)) });
  const costoDe = (id) => Number(productos.find((p) => p.id === id)?.costo || 0);

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
      <span className="muted" style={{ fontSize: 12 }}>Opciones para elegir (recargo: lo que se suma al precio del combo)</span>
      {grupo.opciones.map((o, i) => (
        <div key={i} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select className="inp" aria-label="Opción" value={o.id} onChange={(e) => cambiarOpcion(i, "id", e.target.value)} style={{ flexGrow: 1, minWidth: 0 }}>
            {productos.filter((p) => p.id === o.id || (p.activo && !usados.has(p.id))).map((p) => (
              <option key={p.id} value={p.id}>{p.nombre}{p.activo ? "" : " (inactivo)"}</option>
            ))}
          </select>
          <span className="muted" style={{ fontSize: 13 }}>+$</span>
          <input className="inp num" inputMode="decimal" placeholder="0" aria-label="Recargo" value={o.recargo}
            onChange={(e) => cambiarOpcion(i, "recargo", e.target.value)} style={{ width: 90 }} />
          <span className="muted num" style={{ width: 76, fontSize: 12, textAlign: "right" }} title="Costo de la opción por combo">
            {fmt(Number(grupo.cantidad || 0) * costoDe(o.id))}
          </span>
          <button type="button" className="step" aria-label="Quitar opción"
            onClick={() => onChange({ ...grupo, opciones: grupo.opciones.filter((_, j) => j !== i) })}><IconoQuitar /></button>
        </div>
      ))}
      {libre && (
        <button type="button" className="btn btn-g" style={{ alignSelf: "flex-start", height: 34 }}
          onClick={() => onChange({ ...grupo, opciones: [...grupo.opciones, { id: libre.id, recargo: "" }] })}>+ Opción</button>
      )}
    </div>
  );
}

export default function EditorCombo({ productos, fijos, grupos, precio, onFijos, onGrupos }) {
  const r = resumenCombo(productos, fijos, grupos, precio);
  const costoDe = (id) => Number(productos.find((p) => p.id === id)?.costo || 0);
  const nuevoGrupo = () => {
    const primero = productos.find((p) => p.activo);
    onGrupos([...grupos, { nombre: grupos.length ? "" : "Bebida", cantidad: "1", opciones: primero ? [{ id: primero.id, recargo: "" }] : [] }]);
  };

  return (
    <>
      <Seccion etiqueta="Productos fijos (siempre los lleva)">
        <EditorLineas opciones={productos} lineas={fijos} unidad={() => "und"} onChange={onFijos}
          etiquetaVacia="Sin productos fijos."
          detalle={(l) => (
            <span className="muted num" style={{ width: 76, fontSize: 12, textAlign: "right" }} title="Costo por combo">
              {fmt(Number(l.cantidad || 0) * costoDe(l.id))}
            </span>
          )} />
      </Seccion>

      <Seccion etiqueta="Para elegir al pedirlo">
        {grupos.length === 0 && (
          <span className="muted" style={{ fontSize: 13 }}>
            Sin grupos. Agrega uno si el cliente escoge algo, por ejemplo la bebida: así no hace falta un combo por cada bebida.
          </span>
        )}
        {grupos.map((g, i) => (
          <Grupo key={i} grupo={g} productos={productos}
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
