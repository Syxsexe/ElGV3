import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../AuthContext";
import Sidebar from "./Sidebar";
import TabBar from "./TabBar";

export default function Layout() {
  const { token, usuario, errorSesion, cargarUsuario, logout } = useAuth();
  if (!token) return <Navigate to="/login" replace />;
  if (errorSesion) {
    return (
      <div style={{ maxWidth: 420, margin: "96px auto", padding: "0 16px", display: "flex", flexDirection: "column", gap: 14 }}>
        <div role="alert" className="error-banner">{errorSesion}</div>
        <div style={{ display: "flex", gap: 10 }}>
          <button type="button" className="btn btn-p" onClick={cargarUsuario}>Reintentar</button>
          <button type="button" className="btn btn-s" onClick={logout}>Cerrar sesión</button>
        </div>
      </div>
    );
  }
  if (!usuario) return null; // mientras llega /auth/yo

  return (
    <div className="app-shell">
      <a href="#contenido" className="saltar">Saltar al contenido</a>
      <Sidebar />
      <main id="contenido" tabIndex={-1} className="app-main">
        <Outlet />
      </main>
      <TabBar />
    </div>
  );
}
