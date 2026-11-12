import { useState } from "react";
import { api } from "../api";
import Modal, { ErrorBanner } from "./Modal";

// Plantillas para descargar: los encabezados que entiende el servidor y un ejemplo.
const PLANTILLAS = {
  productos: "nombre;codigo;categoria;tipo;precio;costo;stock;stock_minimo;impuesto\n"
    + "Coca-Cola 400 ml;7702535011119;Bebidas;tienda;3.500;1.800;24;6;\n"
    + "Salchipapa;;Comidas;cocina;14.000;5.200;;;\n",
  insumos: "nombre;unidad;costo;stock;stock_minimo\n"
    + "Salchicha;und;1.200;80;20\n"
    + "Queso mozzarella;g;32;5000;1000\n",
};

const AYUDA = {
  productos: <>Columnas: <strong>nombre</strong> (obligatoria), código, categoría, tipo (tienda o cocina, para categorías nuevas),
    precio, costo, stock, stock_minimo e impuesto (IVA19, INC8…). Para crear un producto hacen falta la categoría y el precio.</>,
  insumos: <>Columnas: <strong>nombre</strong> (obligatoria), unidad (g, ml o und; obligatoria para insumos nuevos), costo por
    unidad, stock y stock_minimo.</>,
};

const ETIQUETA = { crear: "Nuevo", actualizar: "Actualiza", sin_cambios: "Sin cambios", error: "Error" };
const CHIP = { crear: "ok", actualizar: "warn", sin_cambios: "neu", error: "bad" };

// Lee el archivo como texto: UTF-8 y, si no lo es (CSV guardado por Excel), Windows-1252.
async function leerTexto(archivo) {
  const bytes = await archivo.arrayBuffer();
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return new TextDecoder("windows-1252").decode(bytes);
  }
}

function descargar(nombre, texto) {
  const url = URL.createObjectURL(new Blob(["﻿" + texto], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nombre });
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Importar productos o insumos desde un CSV: se sube el archivo, se ve la
// vista previa (qué se crea, qué se actualiza, qué filas tienen error) y al
// confirmar se guarda todo o nada.
export default function ImportarCsv({ tipoInicial = "productos", onClose, onImportado }) {
  const [tipo, setTipo] = useState(tipoInicial);
  const [archivo, setArchivo] = useState(null); // {nombre, contenido}
  const [vista, setVista] = useState(null);
  const [hecho, setHecho] = useState(null);
  const [error, setError] = useState("");
  const [ocupado, setOcupado] = useState(false);

  const previsualizar = async (contenido, t = tipo) => {
    setError("");
    setVista(null);
    setOcupado(true);
    try {
      setVista(await api.importarCsv(t, contenido, false));
    } catch (err) {
      setError(err.message);
    } finally {
      setOcupado(false);
    }
  };

  const elegir = async (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    const contenido = await leerTexto(f);
    setArchivo({ nombre: f.name, contenido });
    setHecho(null);
    previsualizar(contenido);
  };

  const cambiarTipo = (t) => {
    setTipo(t);
    setHecho(null);
    if (archivo) previsualizar(archivo.contenido, t);
  };

  const confirmar = async () => {
    setError("");
    setOcupado(true);
    try {
      const r = await api.importarCsv(tipo, archivo.contenido, true);
      if (r.guardado) {
        setHecho(r);
        onImportado();
      } else {
        setVista(r); // algo cambió desde la vista previa
        setError("No se guardó nada: hay filas con error. Corrige el archivo y vuelve a subirlo.");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setOcupado(false);
    }
  };

  const r = vista?.resumen;
  return (
    <Modal titulo="Importar desde CSV" onClose={() => !ocupado && onClose()} ancho={760}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
          <div className="seg" role="tablist" aria-label="Qué importar">
            {[["productos", "Productos"], ["insumos", "Insumos"]].map(([k, et]) => (
              <button key={k} type="button" role="tab" aria-selected={tipo === k} className={tipo === k ? "on" : ""}
                disabled={ocupado} onClick={() => cambiarTipo(k)}>{et}</button>
            ))}
          </div>
          <button type="button" className="btn btn-g" style={{ height: 36, marginLeft: "auto" }}
            onClick={() => descargar(`plantilla-${tipo}.csv`, PLANTILLAS[tipo])}>Descargar plantilla</button>
        </div>
        <span className="muted" style={{ fontSize: 13 }}>
          {AYUDA[tipo]} Si el producto ya existe (por código o, sin código, por nombre) se actualiza; una celda vacía no
          cambia ese dato y el stock queda como un ajuste por conteo.
        </span>

        {!hecho && (
          <label className="btn btn-s" style={{ alignSelf: "flex-start", position: "relative", cursor: ocupado ? "default" : "pointer" }}>
            {archivo ? `Archivo: ${archivo.nombre} · cambiar` : "Elegir archivo CSV"}
            <input type="file" accept=".csv,text/csv,text/plain" onChange={elegir} disabled={ocupado}
              style={{ position: "absolute", width: 1, height: 1, opacity: 0 }} />
          </label>
        )}
        {ocupado && <span className="muted">Revisando…</span>}
        <ErrorBanner mensaje={error} />

        {hecho && (
          <div role="status" className="card" style={{ padding: 14, borderColor: "var(--accent)" }}>
            <strong>Importación guardada.</strong> {hecho.resumen.crear} nuevos, {hecho.resumen.actualizar} actualizados,
            {" "}{hecho.resumen.sin_cambios} sin cambios.
          </div>
        )}

        {vista && !hecho && (
          <>
            <div role="status" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span className="chip ok">{r.crear} nuevos</span>
              <span className="chip warn">{r.actualizar} se actualizan</span>
              <span className="chip neu">{r.sin_cambios} sin cambios</span>
              {r.error > 0 && <span className="chip bad">{r.error} con error</span>}
              {vista.categorias_nuevas.length > 0 && (
                <span className="chip neu">Categorías nuevas: {vista.categorias_nuevas.join(", ")}</span>
              )}
            </div>
            <div className="card tabla" style={{ maxHeight: 340, overflowY: "auto" }}>
              <div className="th" style={{ gridTemplateColumns: "56px 1fr 96px 1.4fr" }}>
                <span>Fila</span><span>Nombre</span><span>Qué pasa</span><span>Detalle</span>
              </div>
              {vista.filas.map((f) => (
                <div key={f.fila} className="tr" style={{ gridTemplateColumns: "56px 1fr 96px 1.4fr", alignItems: "start" }}>
                  <span className="muted num">{f.fila}</span>
                  <span style={{ overflowWrap: "anywhere" }}>
                    <strong>{f.nombre}</strong>
                    {f.codigo && <span className="muted" style={{ display: "block", fontSize: 12 }}>{f.codigo}</span>}
                  </span>
                  <span><span className={`chip ${CHIP[f.accion]}`}>{ETIQUETA[f.accion]}</span></span>
                  <span style={{ fontSize: 13, overflowWrap: "anywhere" }}>
                    {f.errores.map((e) => <span key={e} style={{ display: "block", color: "var(--danger-text)" }}>{e}</span>)}
                    {f.detalle && <span style={{ display: "block" }}>{f.detalle}</span>}
                    {f.avisos.map((a) => <span key={a} className="muted" style={{ display: "block" }}>{a}</span>)}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}

        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", alignItems: "center", flexWrap: "wrap" }}>
          {vista && !hecho && r.error > 0 && (
            <span className="muted" style={{ fontSize: 13, marginRight: "auto" }}>Corrige las filas con error para poder importar: se guarda todo o nada.</span>
          )}
          <button type="button" className="btn btn-s" onClick={onClose} disabled={ocupado}>{hecho ? "Cerrar" : "Cancelar"}</button>
          {!hecho && (
            <button type="button" className="btn btn-p" onClick={confirmar}
              disabled={ocupado || !vista || r.error > 0 || r.crear + r.actualizar === 0}>
              {vista ? `Importar ${r.crear + r.actualizar} ${tipo}` : "Importar"}
            </button>
          )}
        </div>
      </div>
    </Modal>
  );
}
