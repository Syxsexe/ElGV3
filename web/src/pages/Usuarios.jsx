import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../AuthContext";
import Modal, { Campo, ErrorBanner } from "../components/Modal";

// Agrupa "inventario.editar" bajo "inventario" para mostrar los permisos por módulo.
function porModulo(permisos) {
  const grupos = {};
  for (const p of permisos) (grupos[p.codigo.split(".")[0]] ||= []).push(p);
  return Object.entries(grupos);
}

function ModalUsuario({ usuario, roles, onClose, onGuardado }) {
  const nuevo = !usuario;
  const [nombre, setNombre] = useState("");
  const [rolId, setRolId] = useState(usuario?.rol_id || roles.find((r) => r.nombre === "vendedor")?.id || "");
  const [activo, setActivo] = useState(usuario?.activo ?? true);
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState("");

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    try {
      if (nuevo) {
        await api.crearUsuario({ usuario: nombre, contrasena, rol_id: rolId });
      } else {
        const cambios = {};
        if (rolId !== usuario.rol_id) cambios.rol_id = rolId;
        if (activo !== usuario.activo) cambios.activo = activo;
        if (Object.keys(cambios).length) await api.editarUsuario(usuario.id, cambios);
        if (contrasena) await api.restablecerContrasena(usuario.id, contrasena);
      }
      onGuardado();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Modal titulo={nuevo ? "Nuevo usuario" : `Editar ${usuario.usuario}`} onClose={onClose}>
      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {nuevo && (
          <Campo etiqueta="Usuario">
            <input className="inp" required autoComplete="off" value={nombre} onChange={(e) => setNombre(e.target.value)} />
          </Campo>
        )}
        <Campo etiqueta="Rol">
          <select className="inp" value={rolId} onChange={(e) => setRolId(e.target.value)}>
            {roles.map((r) => <option key={r.id} value={r.id}>{r.nombre}</option>)}
          </select>
        </Campo>
        <Campo etiqueta={nuevo ? "Contraseña" : "Nueva contraseña"}
          ayuda={nuevo ? "Al menos 8 caracteres." : "Déjala vacía para no cambiarla."}>
          <input className="inp" type="password" autoComplete="new-password" required={nuevo}
            minLength={contrasena || nuevo ? 8 : undefined}
            value={contrasena} onChange={(e) => setContrasena(e.target.value)} />
        </Campo>
        {!nuevo && (
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" checked={activo} onChange={(e) => setActivo(e.target.checked)} />
            <span>Activo (puede iniciar sesión)</span>
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

function ModalRol({ rol, permisos, onClose, onGuardado }) {
  const nuevo = !rol;
  const [nombre, setNombre] = useState(rol?.nombre || "");
  const [descripcion, setDescripcion] = useState(rol?.descripcion || "");
  const [elegidos, setElegidos] = useState(new Set(rol?.permisos || []));
  const [error, setError] = useState("");

  const alternar = (codigo) => setElegidos((s) => {
    const copia = new Set(s);
    if (copia.has(codigo)) copia.delete(codigo); else copia.add(codigo);
    return copia;
  });

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    const body = { nombre, descripcion, permisos: [...elegidos] };
    try {
      if (nuevo) await api.crearRol(body); else await api.editarRol(rol.id, body);
      onGuardado();
    } catch (err) {
      setError(err.message);
    }
  };

  const borrar = async () => {
    setError("");
    try {
      await api.borrarRol(rol.id);
      onGuardado();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Modal titulo={nuevo ? "Nuevo rol" : `Rol ${rol.nombre}`} onClose={onClose} ancho={520}>
      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <Campo etiqueta="Nombre">
          <input className="inp" required value={nombre} onChange={(e) => setNombre(e.target.value)} />
        </Campo>
        <Campo etiqueta="Descripción">
          <input className="inp" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
        </Campo>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <span className="lbl">Permisos</span>
          {porModulo(permisos).map(([modulo, lista]) => (
            <div key={modulo} style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <span className="muted" style={{ fontSize: 12, textTransform: "uppercase", fontWeight: 700 }}>{modulo}</span>
              {lista.map((p) => (
                <label key={p.codigo} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14 }}>
                  <input type="checkbox" checked={elegidos.has(p.codigo)} onChange={() => alternar(p.codigo)} />
                  <span>{p.descripcion}</span>
                </label>
              ))}
            </div>
          ))}
        </div>
        <ErrorBanner mensaje={error} />
        <div style={{ display: "flex", gap: 10, justifyContent: "flex-end", flexWrap: "wrap" }}>
          {!nuevo && <button type="button" className="btn btn-d" onClick={borrar} style={{ marginRight: "auto" }}>Borrar rol</button>}
          <button type="button" className="btn btn-s" onClick={onClose}>Cancelar</button>
          <button type="submit" className="btn btn-p">Guardar</button>
        </div>
      </form>
    </Modal>
  );
}

export default function Usuarios() {
  const { usuario: yo } = useAuth();
  const [vista, setVista] = useState("usuarios");
  const [usuarios, setUsuarios] = useState([]);
  const [roles, setRoles] = useState([]);
  const [permisos, setPermisos] = useState([]);
  const [editando, setEditando] = useState(null); // {tipo: "usuario"|"rol", dato}
  const [error, setError] = useState("");

  const cargar = useCallback(() => {
    Promise.all([api.usuarios(), api.roles(), api.permisos()])
      .then(([u, r, p]) => {
        setUsuarios(u);
        setRoles(r);
        setPermisos(p);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    cargar();
  }, [cargar]);

  const alGuardar = () => {
    setEditando(null);
    cargar();
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontSize: 28, marginRight: "auto" }}>Usuarios</h1>
        <div className="seg">
          <button type="button" className={vista === "usuarios" ? "on" : ""} onClick={() => setVista("usuarios")}>Usuarios</button>
          <button type="button" className={vista === "roles" ? "on" : ""} onClick={() => setVista("roles")}>Roles</button>
        </div>
        <button type="button" className="btn btn-p" onClick={() => setEditando({ tipo: vista === "usuarios" ? "usuario" : "rol", dato: null })}>
          {vista === "usuarios" ? "+ Nuevo usuario" : "+ Nuevo rol"}
        </button>
      </div>
      <ErrorBanner mensaje={error} />

      {vista === "usuarios" ? (
        <div className="card" style={{ overflow: "hidden" }}>
          <div className="th" style={{ gridTemplateColumns: "1fr 140px 100px" }}>
            <span>Usuario</span><span>Rol</span><span>Estado</span>
          </div>
          {usuarios.map((u) => (
            <div key={u.id} className="tr" style={{ gridTemplateColumns: "1fr 140px 100px", cursor: "pointer" }}
              onClick={() => setEditando({ tipo: "usuario", dato: u })}>
              <span style={{ fontWeight: 600 }}>
                {u.usuario}{u.id === yo?.id && <span className="muted" style={{ fontWeight: 400 }}> (tú)</span>}
                {u.persona && <span className="muted" style={{ display: "block", fontSize: 12, fontWeight: 400 }}>{u.persona}</span>}
              </span>
              <span>{u.rol}</span>
              <span><span className={`chip ${u.activo ? "ok" : "neu"}`}>{u.activo ? "Activo" : "Inactivo"}</span></span>
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 12 }}>
          {roles.map((r) => (
            <button key={r.id} type="button" className="mesa" disabled={r.nombre === "admin"}
              onClick={() => setEditando({ tipo: "rol", dato: r })} style={{ cursor: r.nombre === "admin" ? "default" : "pointer" }}>
              <div style={{ display: "flex", justifyContent: "space-between", width: "100%" }}>
                <strong style={{ fontSize: 16 }}>{r.nombre}</strong>
                <span className="chip neu">{r.usuarios} {r.usuarios === 1 ? "usuario" : "usuarios"}</span>
              </div>
              {r.descripcion && <span className="muted" style={{ fontSize: 13 }}>{r.descripcion}</span>}
              <span style={{ fontSize: 13 }}>
                {r.nombre === "admin" ? "Todos los permisos (no se edita)"
                  : r.permisos.length ? `${r.permisos.length} permisos: ${r.permisos.join(", ")}` : "Sin permisos especiales"}
              </span>
            </button>
          ))}
        </div>
      )}

      {editando?.tipo === "usuario" && (
        <ModalUsuario usuario={editando.dato} roles={roles} onClose={() => setEditando(null)} onGuardado={alGuardar} />
      )}
      {editando?.tipo === "rol" && (
        <ModalRol rol={editando.dato} permisos={permisos} onClose={() => setEditando(null)} onGuardado={alGuardar} />
      )}
    </div>
  );
}
