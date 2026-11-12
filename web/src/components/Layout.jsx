import { useEffect, useRef } from "react";
import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../AuthContext";
import Sidebar from "./Sidebar";
import TabBar from "./TabBar";

// Al cambiar de pantalla el contenido entra con un leve fundido
// (no bloquea: se puede tocar mientras anima). Sin animación si el sistema
// pide menos movimiento.
function useTransicionDePagina(ref, listo) {
  const { pathname } = useLocation();
  useEffect(() => {
    const el = ref.current;
    if (!el?.animate || matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;
    const tokens = getComputedStyle(document.documentElement);
    const anim = el.animate(
      // Solo opacidad: un transform en <main> movería los elementos fijos de
      // adentro (el botón "Ver venta" del celular) mientras dura.
      [{ opacity: 0 }, { opacity: 1 }],
      { duration: parseFloat(tokens.getPropertyValue("--dur")) || 200, easing: tokens.getPropertyValue("--ease").trim() || "ease-out" },
    );
    return () => anim.cancel();
  }, [pathname, ref, listo]); // listo: <main> recién aparece tras cargar el usuario
}

export default function Layout() {
  const { token, usuario, errorSesion, cargarUsuario, logout } = useAuth();
  const main = useRef(null);
  useTransicionDePagina(main, Boolean(token && usuario && !errorSesion));
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
      <main ref={main} id="contenido" tabIndex={-1} className="app-main">
        <Outlet />
      </main>
      <TabBar />
    </div>
  );
}
