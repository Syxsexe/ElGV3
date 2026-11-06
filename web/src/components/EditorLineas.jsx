// Lista editable de componentes (receta de un plato o preparación, productos
// de un combo): cada línea es un elemento de `opciones` y una cantidad.
// lineas: [{id, cantidad}] con cantidad como texto (se manda tal cual a la API).
// opciones: [{id, nombre, activo}] con TODOS los elementos: los inactivos solo
// aparecen en la línea que ya los usa (para no mostrar otro en su lugar).
export default function EditorLineas({ opciones, lineas, onChange, unidad = () => "", etiquetaVacia = "Sin componentes." }) {
  const usados = new Set(lineas.map((l) => l.id));
  const cambiar = (i, campo, valor) => onChange(lineas.map((l, j) => (j === i ? { ...l, [campo]: valor } : l)));
  const disponible = (o) => o.activo !== false && !usados.has(o.id);
  const libre = opciones.find(disponible);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {lineas.length === 0 && <span className="muted" style={{ fontSize: 13 }}>{etiquetaVacia}</span>}
      {lineas.map((l, i) => (
        <div key={i} style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select className="inp" value={l.id} onChange={(e) => cambiar(i, "id", e.target.value)} style={{ flexGrow: 1, minWidth: 0 }}>
            {opciones.filter((o) => o.id === l.id || disponible(o)).map((o) => (
              <option key={o.id} value={o.id}>{o.nombre}{o.activo === false ? " (inactivo)" : ""}</option>
            ))}
          </select>
          <input className="inp num" inputMode="decimal" required value={l.cantidad} style={{ width: 90 }}
            onChange={(e) => cambiar(i, "cantidad", e.target.value)} aria-label="Cantidad" />
          <span className="muted" style={{ width: 32, fontSize: 13 }}>{unidad(l.id)}</span>
          <button type="button" className="step" aria-label="Quitar" onClick={() => onChange(lineas.filter((_, j) => j !== i))}>×</button>
        </div>
      ))}
      {libre && (
        <button type="button" className="btn btn-g" style={{ alignSelf: "flex-start", height: 34 }}
          onClick={() => onChange([...lineas, { id: libre.id, cantidad: "1" }])}>+ Agregar</button>
      )}
    </div>
  );
}
