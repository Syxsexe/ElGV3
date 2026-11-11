import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import { digitoVerificacion, fmt } from "../format";
import BuscarMunicipio from "./BuscarMunicipio";
import Modal, { Campo, ErrorBanner, Seccion } from "./Modal";

const VACIO = {
  tipo_persona: "natural", nombre: "", tipo_identificacion: "", numero_identificacion: "",
  telefono: "", email: "", direccion: "", municipio_id: null, municipio: "", departamento: "",
  responsable_iva: null, responsabilidades: [],
  es_cliente: false, limite_credito: "0", dias_credito: "30", cliente_activo: true,
  es_proveedor: false, contacto: "", proveedor_activo: true,
};

// Alta y edición de un tercero con sus roles de cliente y proveedor.
// rol: el rol con el que se abre desde la página ("cliente" o "proveedor").
export default function ModalTercero({ terceroId, rol, onClose, onGuardado }) {
  const { puede } = useAuth();
  const nuevo = !terceroId;
  const [f, setF] = useState(() => (nuevo ? { ...VACIO, [`es_${rol}`]: true } : null));
  const [original, setOriginal] = useState(null);
  const [tipos, setTipos] = useState([]);
  const [responsabilidades, setResponsabilidades] = useState([]);
  const [error, setError] = useState("");
  const [cupo, setCupo] = useState(null); // saldo de fiado de un cliente existente
  const editaCupo = puede("clientes.editar");
  const editaProveedor = puede("compras.registrar");

  useEffect(() => {
    Promise.all([api.tiposIdentificacion(), api.responsabilidades()])
      .then(([t, r]) => {
        setTipos(t);
        setResponsabilidades(r);
      })
      .catch((err) => setError(err.message));
    if (nuevo) return;
    api.tercero(terceroId).then((t) => {
      const datos = {
        ...t,
        tipo_identificacion: t.tipo_identificacion || "", numero_identificacion: t.numero_identificacion || "",
        telefono: t.telefono || "", email: t.email || "", direccion: t.direccion || "", contacto: t.contacto || "",
        limite_credito: String(t.limite_credito ?? "0"), dias_credito: String(t.dias_credito ?? "30"),
        cliente_activo: t.cliente_activo ?? true, proveedor_activo: t.proveedor_activo ?? true,
      };
      setF(datos);
      setOriginal(datos);
      if (t.es_cliente) api.cupoCliente(terceroId).then(setCupo).catch((err) => setCupo({ error: err.message }));
    }).catch((err) => setError(err.message));
  }, [terceroId, nuevo]);

  if (!f) return <Modal titulo="Cargando…" onClose={onClose}><ErrorBanner mensaje={error} /></Modal>;

  const cambiar = (campo) => (e) => {
    const valor = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setF((x) => ({
      ...x,
      [campo]: valor,
      // "Sin documento" borra también el número (el campo queda bloqueado).
      ...(campo === "tipo_identificacion" && !valor ? { numero_identificacion: "" } : {}),
    }));
  };
  const nit = f.tipo_identificacion === "31";
  const dv = nit ? digitoVerificacion(f.numero_identificacion.replace(/[.\s]/g, "").split("-")[0]) : null;
  const alternarResp = (codigo) => setF((x) => ({
    ...x,
    responsabilidades: x.responsabilidades.includes(codigo)
      ? x.responsabilidades.filter((c) => c !== codigo) : [...x.responsabilidades, codigo],
  }));

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    const datos = {
      tipo_persona: f.tipo_persona, nombre: f.nombre,
      tipo_identificacion: f.tipo_identificacion || null, numero_identificacion: f.numero_identificacion || null,
      telefono: f.telefono || null, email: f.email || null, direccion: f.direccion || null,
      municipio_id: f.municipio_id, responsable_iva: f.responsable_iva, responsabilidades: f.responsabilidades,
    };
    // Sin permiso de clientes, el rol se da sin tocar cupo ni días (la API lo exige así).
    const cliente = editaCupo
      ? { limite_credito: f.limite_credito, dias_credito: Number(f.dias_credito), activo: f.cliente_activo }
      : {};
    const proveedor = { contacto: f.contacto || null, activo: f.proveedor_activo };
    try {
      // Una sola petición: datos y roles se guardan juntos o no se guarda nada.
      const roles = {
        cliente: f.es_cliente && (nuevo || !original.es_cliente || editaCupo) ? cliente : undefined,
        proveedor: f.es_proveedor && editaProveedor ? proveedor : undefined,
      };
      if (nuevo) await api.crearTercero({ ...datos, ...roles });
      else await api.editarTercero(terceroId, { ...datos, ...roles });
      onGuardado();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Modal titulo={nuevo ? (rol === "cliente" ? "Nuevo cliente" : "Nuevo proveedor") : f.nombre} onClose={onClose} ancho={600}>
      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 150px", gap: 12 }}>
          <Campo etiqueta="Nombre o razón social">
            <input className="inp" required value={f.nombre} onChange={cambiar("nombre")} />
          </Campo>
          <Campo etiqueta="Persona">
            <select className="inp" value={f.tipo_persona} onChange={cambiar("tipo_persona")}>
              <option value="natural">Natural</option>
              <option value="juridica">Jurídica</option>
            </select>
          </Campo>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12 }}>
          <Campo etiqueta="Documento">
            <select className="inp" value={f.tipo_identificacion} onChange={cambiar("tipo_identificacion")}>
              <option value="">Sin documento</option>
              {tipos.map((t) => <option key={t.codigo} value={t.codigo}>{t.nombre}</option>)}
            </select>
          </Campo>
          <Campo etiqueta="Número" ayuda={dv != null ? `Dígito de verificación: ${dv}` : undefined}>
            <input className="inp" disabled={!f.tipo_identificacion} value={f.numero_identificacion}
              onChange={cambiar("numero_identificacion")} required={Boolean(f.tipo_identificacion)} />
          </Campo>
          <Campo etiqueta="Teléfono">
            <input className="inp" inputMode="tel" value={f.telefono} onChange={cambiar("telefono")} />
          </Campo>
          <Campo etiqueta="Email">
            <input className="inp" type="email" value={f.email} onChange={cambiar("email")} />
          </Campo>
          <Campo etiqueta="Dirección">
            <input className="inp" value={f.direccion} onChange={cambiar("direccion")} />
          </Campo>
          <Campo etiqueta="Municipio" ayuda={f.municipio ? `${f.municipio} (${f.departamento})` : undefined}>
            <BuscarMunicipio actual={f.municipio}
              onElegir={(m) => setF((x) => ({ ...x, municipio_id: m.id, municipio: m.nombre, departamento: m.departamento }))} />
          </Campo>
        </div>

        <details>
          <summary className="lbl" style={{ cursor: "pointer" }}>Datos para factura electrónica</summary>
          <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 10 }}>
            <Campo etiqueta="Responsable de IVA">
              <select className="inp" style={{ maxWidth: 200 }} value={f.responsable_iva == null ? "" : String(f.responsable_iva)}
                onChange={(e) => setF((x) => ({ ...x, responsable_iva: e.target.value === "" ? null : e.target.value === "true" }))}>
                <option value="">Sin dato</option>
                <option value="true">Sí</option>
                <option value="false">No</option>
              </select>
            </Campo>
            <Seccion etiqueta="Responsabilidades del RUT">
              {responsabilidades.map((r) => (
                <label key={r.codigo} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
                  <input type="checkbox" checked={f.responsabilidades.includes(r.codigo)} onChange={() => alternarResp(r.codigo)} />
                  <span>{r.codigo} · {r.descripcion}</span>
                </label>
              ))}
            </Seccion>
          </div>
        </details>

        <div className="card" style={{ padding: 14, display: "flex", flexDirection: "column", gap: 10, background: "var(--surface-2)" }}>
          <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 600 }}>
            <input type="checkbox" checked={f.es_cliente} disabled={!nuevo && original?.es_cliente} onChange={cambiar("es_cliente")} />
            <span>Cliente</span>
          </label>
          {f.es_cliente && (
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
              <Campo etiqueta="Cupo de crédito (fiado)" ayuda={editaCupo ? "0 = sin fiado" : "Solo quien administra clientes lo cambia"}>
                <input className="inp num" type="number" min="0" step="any" required disabled={!editaCupo}
                  value={f.limite_credito} onChange={cambiar("limite_credito")} style={{ width: 160 }} />
              </Campo>
              <Campo etiqueta="Días para pagar">
                <input className="inp num" type="number" min="1" max="365" step="1" required disabled={!editaCupo}
                  value={f.dias_credito} onChange={cambiar("dias_credito")} style={{ width: 110 }} />
              </Campo>
              {!nuevo && original?.es_cliente && (
                <label style={{ display: "flex", gap: 8, alignItems: "center", height: 40 }}>
                  <input type="checkbox" disabled={!editaCupo} checked={f.cliente_activo} onChange={cambiar("cliente_activo")} />
                  <span>Activo</span>
                </label>
              )}
            </div>
          )}
          {cupo?.error && <span className="muted" style={{ fontSize: 14 }}>No se pudo ver su saldo de fiado: {cupo.error}</span>}
          {cupo && !cupo.error && (
            <span style={{ fontSize: 14 }}>
              {Number(cupo.saldo) > 0 ? <>Debe <strong className="num">{fmt(cupo.saldo)}</strong></> : "No debe nada"}
              {Number(cupo.cargos_vencidos) > 0 && <span style={{ color: "var(--danger)" }}> · {cupo.cargos_vencidos} cargo(s) vencido(s)</span>}
              {" · "}
              {/* Ir a Créditos cierra este formulario: con cambios sin guardar, primero se guardan. */}
              {JSON.stringify(f) === JSON.stringify(original)
                ? <Link to={`/creditos?cliente=${terceroId}`}>Ver su crédito</Link>
                : <span className="muted">guarda los cambios para ver su crédito</span>}
            </span>
          )}
          {(editaProveedor || f.es_proveedor) && (
            <label style={{ display: "flex", gap: 8, alignItems: "center", fontWeight: 600 }}>
              <input type="checkbox" checked={f.es_proveedor} disabled={!editaProveedor || (!nuevo && original?.es_proveedor)}
                onChange={cambiar("es_proveedor")} />
              <span>Proveedor</span>
            </label>
          )}
          {f.es_proveedor && (
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "end" }}>
              <Campo etiqueta="Persona de contacto">
                <input className="inp" disabled={!editaProveedor} value={f.contacto} onChange={cambiar("contacto")} style={{ width: 240 }} />
              </Campo>
              {!nuevo && original?.es_proveedor && (
                <label style={{ display: "flex", gap: 8, alignItems: "center", height: 40 }}>
                  <input type="checkbox" disabled={!editaProveedor} checked={f.proveedor_activo} onChange={cambiar("proveedor_activo")} />
                  <span>Activo</span>
                </label>
              )}
            </div>
          )}
        </div>

        {!nuevo && f.usuario && <span className="muted" style={{ fontSize: 13 }}>Es el usuario {f.usuario} del sistema.</span>}
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-s" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-p">Guardar</button>
        </div>
      </form>
    </Modal>
  );
}
