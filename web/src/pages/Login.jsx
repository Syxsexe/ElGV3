import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext";

export default function Login() {
  const { token, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [usuario, setUsuario] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [verClave, setVerClave] = useState(false);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);

  if (token) return <Navigate to={location.state?.from || "/cuentas"} replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setCargando(true);
    try {
      await login(usuario, contrasena);
      navigate("/cuentas", { replace: true });
    } catch (err) {
      setError(err.message || "Usuario o contraseña incorrectos.");
    } finally {
      setCargando(false);
    }
  };

  return (
    <div className="login-shell">
      <section className="login-hero">
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{
            width: 52, height: 52, borderRadius: 16, background: "#FFFFFF", color: "var(--accent)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: "'Bricolage Grotesque', sans-serif", fontWeight: 700, fontSize: 28,
          }}>G</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: "#CDE8E1" }}>Punto de venta</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14, position: "relative" }}>
          <h1 style={{ fontSize: 96, lineHeight: 0.95, color: "#FFFFFF" }}>El G</h1>
          <div style={{ fontSize: 22, color: "#E4F3EF" }}>TCG · Juegos de mesa · Comidas rápidas</div>
        </div>
      </section>
      <section className="login-form-side">
        <form className="login-form" onSubmit={submit}>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <h2 style={{ fontSize: 34 }}>Hola de nuevo</h2>
            <p style={{ margin: 0, fontSize: 16, color: "var(--text-muted)" }}>
              Ingresa con tu usuario para abrir el punto de venta.
            </p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <label className="lbl" htmlFor="u">Usuario</label>
            <input className="inp" id="u" type="text" autoComplete="username" style={{ height: 48 }}
              value={usuario} onChange={(e) => setUsuario(e.target.value)} required />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <label className="lbl" htmlFor="p">Contraseña</label>
            <div style={{ position: "relative" }}>
              <input className="inp" id="p" type={verClave ? "text" : "password"} autoComplete="current-password"
                style={{ height: 48, paddingRight: 96 }}
                value={contrasena} onChange={(e) => setContrasena(e.target.value)} required />
              <button type="button" onClick={() => setVerClave((v) => !v)} style={{
                position: "absolute", right: 6, top: 6, height: 36, padding: "0 12px", border: 0, borderRadius: 9,
                background: "var(--neu-bg)", color: "var(--text)", font: "600 13px Figtree, sans-serif", cursor: "pointer",
              }}>{verClave ? "Ocultar" : "Mostrar"}</button>
            </div>
          </div>
          <button className="btn btn-p" type="submit" disabled={cargando} style={{ width: "100%", height: 48, fontSize: 15 }}>
            {cargando ? "Ingresando…" : "Ingresar"}
          </button>
          {error && (
            <div role="alert" className="error-banner">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                strokeLinecap="round" aria-hidden="true"><path d="M12 8v5M12 16.5h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z" /></svg>
              {error}
            </div>
          )}
        </form>
      </section>
    </div>
  );
}
