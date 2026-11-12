import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import BuscarMunicipio from "../components/BuscarMunicipio";
import { Campo, ErrorBanner } from "../components/Modal";
import { olvidarEmpresa } from "../imprimir";

const SECCIONES = [
  ["negocio", "Negocio"],
  ["cajas", "Cajas y pagos"],
  ["mesas", "Mesas"],
  ["categorias-gasto", "Categorías de gasto"],
  ["juegos", "Juegos"],
];

function Aviso({ texto }) {
  if (!texto) return null;
  return <div className="chip ok" style={{ alignSelf: "flex-start" }}>{texto}</div>;
}

// ── Negocio ────────────────────────────────────────────────────────────────

function Negocio() {
  const [datos, setDatos] = useState(null);
  const [tipos, setTipos] = useState([]);
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");

  useEffect(() => {
    Promise.all([api.empresa(), api.tiposIdentificacion()])
      .then(([e, t]) => {
        setDatos(e);
        setTipos(t);
      })
      .catch((err) => setError(err.message));
  }, []);

  if (!datos) return <ErrorBanner mensaje={error} />;
  const cambiar = (campo) => (e) => {
    const valor = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setDatos((d) => ({ ...d, [campo]: valor }));
  };

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    setAviso("");
    try {
      const campos = ["tipo_persona", "nombre", "tipo_identificacion", "numero_identificacion", "direccion",
        "municipio_id", "telefono", "email", "responsable_iva", "regimen_tributario", "responsable_inc",
        "precios_incluyen_impuestos", "mensaje_ticket"];
      setDatos(await api.editarEmpresa(Object.fromEntries(campos.map((c) => [c, datos[c]]))));
      olvidarEmpresa();
      setAviso("Datos del negocio guardados.");
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <form onSubmit={guardar} className="card" style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14, maxWidth: 640 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 14 }}>
        <Campo etiqueta="Nombre o razón social">
          <input className="inp" required value={datos.nombre} onChange={cambiar("nombre")} />
        </Campo>
        <Campo etiqueta="Tipo de persona">
          <select className="inp" value={datos.tipo_persona} onChange={cambiar("tipo_persona")}>
            <option value="natural">Natural</option>
            <option value="juridica">Jurídica</option>
          </select>
        </Campo>
        <Campo etiqueta="Tipo de documento">
          <select className="inp" value={datos.tipo_identificacion || ""} onChange={cambiar("tipo_identificacion")}>
            {tipos.map((t) => <option key={t.codigo} value={t.codigo}>{t.nombre}</option>)}
          </select>
        </Campo>
        <Campo etiqueta="Número" ayuda={datos.dv != null ? `Dígito de verificación: ${datos.dv}` : undefined}>
          <input className="inp" required value={datos.numero_identificacion || ""} onChange={cambiar("numero_identificacion")} />
        </Campo>
        <Campo etiqueta="Municipio" ayuda={datos.municipio ? `${datos.municipio} (${datos.departamento})` : "Sin municipio"}>
          <BuscarMunicipio actual={datos.municipio}
            onElegir={(m) => setDatos((d) => ({ ...d, municipio_id: m.id, municipio: m.nombre, departamento: m.departamento }))} />
        </Campo>
        <Campo etiqueta="Dirección">
          <input className="inp" value={datos.direccion || ""} onChange={cambiar("direccion")} />
        </Campo>
        <Campo etiqueta="Teléfono">
          <input className="inp" value={datos.telefono || ""} onChange={cambiar("telefono")} />
        </Campo>
        <Campo etiqueta="Email">
          <input className="inp" type="email" value={datos.email || ""} onChange={cambiar("email")} />
        </Campo>
        <Campo etiqueta="Régimen tributario">
          <select className="inp" value={datos.regimen_tributario} onChange={cambiar("regimen_tributario")}>
            <option value="ordinario">Ordinario</option>
            <option value="simple">Simple (RST)</option>
          </select>
        </Campo>
      </div>
      <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input type="checkbox" checked={Boolean(datos.responsable_iva)} onChange={cambiar("responsable_iva")} />
        <span>Responsable de IVA</span>
      </label>
      <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input type="checkbox" checked={datos.responsable_inc} onChange={cambiar("responsable_inc")} />
        <span>Responsable de INC (impuesto al consumo)</span>
      </label>
      <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <input type="checkbox" checked={datos.precios_incluyen_impuestos} onChange={cambiar("precios_incluyen_impuestos")} />
        <span>Los precios de venta ya incluyen impuestos</span>
      </label>
      <Campo etiqueta="Mensaje del ticket" ayuda={`Va al final del ticket de venta. Déjalo vacío para no poner nada. ${(datos.mensaje_ticket || "").length}/300`}>
        <textarea className="inp" maxLength={300} value={datos.mensaje_ticket || ""} onChange={cambiar("mensaje_ticket")}
          placeholder="¡Gracias por su compra! · Síguenos en Instagram" style={{ height: 80, padding: "10px 12px", resize: "none" }} />
      </Campo>
      <ErrorBanner mensaje={error} />
      <Aviso texto={aviso} />
      <button type="submit" className="btn btn-p" style={{ alignSelf: "flex-start" }}>Guardar</button>
    </form>
  );
}

// ── Cajas y métodos de pago ────────────────────────────────────────────────

function NombreEditable({ valor, onGuardar }) {
  const [texto, setTexto] = useState(valor);
  const cambiado = texto.trim() && texto.trim() !== valor;
  return (
    <div style={{ display: "flex", gap: 6, flexGrow: 1, minWidth: 0 }}>
      <input className="inp" value={texto} onChange={(e) => setTexto(e.target.value)} style={{ height: 34 }} />
      {cambiado && <button type="button" className="btn btn-s" style={{ height: 34 }} onClick={() => onGuardar(texto.trim())}>Guardar</button>}
    </div>
  );
}

function Interruptor({ activo, onCambiar }) {
  return (
    <button type="button" className={`chip ${activo ? "ok" : "neu"}`} onClick={() => onCambiar(!activo)}
      style={{ border: 0, cursor: "pointer" }} title={activo ? "Clic para desactivar" : "Clic para activar"}>
      {activo ? "Activo" : "Inactivo"}
    </button>
  );
}

function Cajas() {
  const [cajas, setCajas] = useState([]);
  const [error, setError] = useState("");
  const [nuevaCaja, setNuevaCaja] = useState("");
  const [nuevoMetodo, setNuevoMetodo] = useState({}); // caja_id → nombre

  const cargar = useCallback(() => api.cajas().then(setCajas).catch((err) => setError(err.message)), []);
  useEffect(() => {
    cargar();
  }, [cargar]);

  // true si salió bien: el formulario solo se limpia cuando se guardó.
  const hacer = async (accion) => {
    setError("");
    try {
      await accion();
      await cargar();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, maxWidth: 760 }}>
      <p className="muted" style={{ margin: 0 }}>
        Cada método de pago cae en una caja; al cerrar el turno se cuenta cada caja. Solo una caja se cuenta en
        billetes y monedas. Un método que ya tiene pagos no cambia de caja: crea otro y desactiva el viejo.
      </p>
      <ErrorBanner mensaje={error} />
      {cajas.map((c) => (
        <div key={c.id} className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <NombreEditable valor={c.nombre} onGuardar={(nombre) => hacer(() => api.editarCaja(c.id, { nombre }))} />
            {c.usa_denominaciones && <span className="chip neu">Billetes y monedas</span>}
            <Interruptor activo={c.activo} onCambiar={(activo) => hacer(() => api.editarCaja(c.id, { activo }))} />
          </div>
          {c.metodos.map((m) => (
            <div key={m.id} style={{ display: "flex", gap: 10, alignItems: "center", paddingLeft: 12, flexWrap: "wrap" }}>
              <NombreEditable valor={m.nombre} onGuardar={(nombre) => hacer(() => api.editarMetodoPago(m.id, { nombre }))} />
              <select className="inp" style={{ width: 150, height: 34 }} value={c.id}
                onChange={(e) => hacer(() => api.editarMetodoPago(m.id, { caja_id: e.target.value }))}>
                {cajas.filter((x) => x.activo || x.id === c.id).map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
              </select>
              <Interruptor activo={m.activo} onCambiar={(activo) => hacer(() => api.editarMetodoPago(m.id, { activo }))} />
            </div>
          ))}
          {c.activo && (
            <form style={{ display: "flex", gap: 8, paddingLeft: 12 }} onSubmit={(e) => {
              e.preventDefault();
              hacer(() => api.crearMetodoPago({ nombre: nuevoMetodo[c.id], caja_id: c.id }))
                .then((ok) => ok && setNuevoMetodo((n) => ({ ...n, [c.id]: "" })));
            }}>
              <input className="inp" style={{ height: 34 }} placeholder="Nuevo método de pago" required
                value={nuevoMetodo[c.id] || ""} onChange={(e) => setNuevoMetodo((n) => ({ ...n, [c.id]: e.target.value }))} />
              <button type="submit" className="btn btn-s" style={{ height: 34 }}>Agregar</button>
            </form>
          )}
        </div>
      ))}
      <form style={{ display: "flex", gap: 8 }} onSubmit={(e) => {
        e.preventDefault();
        hacer(() => api.crearCaja({ nombre: nuevaCaja })).then((ok) => ok && setNuevaCaja(""));
      }}>
        <input className="inp" placeholder="Nueva caja (ej. Caja menor)" required value={nuevaCaja} onChange={(e) => setNuevaCaja(e.target.value)} />
        <button type="submit" className="btn btn-s">Crear caja</button>
      </form>
    </div>
  );
}

// ── Mesas, categorías de gasto y juegos ────────────────────────────────────

function ListaSimple({ catalogo, ayuda }) {
  const [items, setItems] = useState([]);
  const [nuevo, setNuevo] = useState("");
  const [error, setError] = useState("");

  const cargar = useCallback(
    () => api.catalogo(catalogo, true).then(setItems).catch((err) => setError(err.message)),
    [catalogo],
  );
  useEffect(() => {
    cargar();
  }, [cargar]);

  // true si salió bien: el formulario solo se limpia cuando se guardó.
  const hacer = async (accion) => {
    setError("");
    try {
      await accion();
      await cargar();
      return true;
    } catch (err) {
      setError(err.message);
      return false;
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, maxWidth: 560 }}>
      <p className="muted" style={{ margin: 0 }}>{ayuda} Lo que ya no se usa se desactiva: no se borra porque lo referencia el historial.</p>
      <ErrorBanner mensaje={error} />
      <form style={{ display: "flex", gap: 8 }} onSubmit={(e) => {
        e.preventDefault();
        hacer(() => api.crearEnCatalogo(catalogo, nuevo)).then((ok) => ok && setNuevo(""));
      }}>
        <input className="inp" placeholder="Nombre" required value={nuevo} onChange={(e) => setNuevo(e.target.value)} />
        <button type="submit" className="btn btn-s">Agregar</button>
      </form>
      <div className="card" style={{ overflow: "hidden" }}>
        {items.map((it) => (
          <div key={it.id} className="tr" style={{ gridTemplateColumns: "1fr auto" }}>
            <NombreEditable valor={it.nombre} onGuardar={(nombre) => hacer(() => api.editarEnCatalogo(catalogo, it.id, { nombre }))} />
            <Interruptor activo={it.activo} onCambiar={(activo) => hacer(() => api.editarEnCatalogo(catalogo, it.id, { activo }))} />
          </div>
        ))}
        {items.length === 0 && <div className="muted" style={{ padding: 16 }}>Nada todavía.</div>}
      </div>
    </div>
  );
}

const AYUDAS = {
  mesas: "Las mesas a las que se les abre cuenta.",
  "categorias-gasto": "Para clasificar los gastos del negocio (arriendo, servicios…).",
  juegos: "Los juegos de los torneos.",
};

export default function Configuracion() {
  const [seccion, setSeccion] = useState("negocio");
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <h1 style={{ fontSize: 28 }}>Configuración</h1>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {SECCIONES.map(([clave, etiqueta]) => (
          <button key={clave} type="button" className={`pill${seccion === clave ? " on" : ""}`} onClick={() => setSeccion(clave)}>
            {etiqueta}
          </button>
        ))}
      </div>
      {seccion === "negocio" && <Negocio />}
      {seccion === "cajas" && <Cajas />}
      {AYUDAS[seccion] && <ListaSimple key={seccion} catalogo={seccion} ayuda={AYUDAS[seccion]} />}
    </div>
  );
}
