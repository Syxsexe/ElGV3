import { useState } from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../AuthContext";
import CambiarContrasena from "../components/CambiarContrasena";
import { SIDEBAR_GROUPS } from "../nav";

// En el celular la barra inferior solo tiene los módulos de todos los días;
// el resto del menú vive aquí.
export default function Mas() {
  const { usuario, logout, puede } = useAuth();
  const [cambiandoClave, setCambiandoClave] = useState(false);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <h1 style={{ fontSize: 26 }}>Más</h1>
      {SIDEBAR_GROUPS.map((g) => {
        const items = g.items.filter((it) => it.path && puede(it.permiso));
        if (!items.length) return null;
        return (
          <div key={g.name} className="card" style={{ overflow: "hidden" }}>
            <div className="th" style={{ gridTemplateColumns: "1fr" }}><span>{g.name}</span></div>
            {items.map((it) => (
              <NavLink key={it.label} to={it.path} end className="tr" style={{ gridTemplateColumns: "1fr", color: "var(--text)" }}>
                {it.label}
              </NavLink>
            ))}
          </div>
        );
      })}
      <div className="card" style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
        <span><strong>{usuario?.usuario}</strong> <span className="muted">· {usuario?.rol}</span></span>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button type="button" className="btn btn-s" onClick={() => setCambiandoClave(true)}>Cambiar contraseña</button>
          <button type="button" className="btn btn-d" onClick={logout}>Cerrar sesión</button>
        </div>
      </div>
      {cambiandoClave && <CambiarContrasena onClose={() => setCambiandoClave(false)} />}
    </div>
  );
}
