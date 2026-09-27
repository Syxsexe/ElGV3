import { NavLink } from "react-router-dom";
import { useAuth } from "../AuthContext";
import { SIDEBAR_GROUPS } from "../nav";

function Icon({ d }) {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export default function Sidebar() {
  const { usuario, logout } = useAuth();
  const inicial = (usuario?.usuario || "?").charAt(0).toUpperCase();

  return (
    <nav aria-label="Módulos" className="sidebar-nav" style={{
      width: 240, flexShrink: 0, height: "100vh", position: "sticky", top: 0,
      boxSizing: "border-box", flexDirection: "column",
      background: "#FFFFFF", borderRight: "1px solid var(--border)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "22px 20px 18px" }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12, background: "var(--accent)", color: "#fff",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontWeight: 700, fontSize: 20,
        }}>G</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
          <div style={{ fontFamily: "'Bricolage Grotesque', Figtree, sans-serif", fontWeight: 700, fontSize: 20, lineHeight: 1.1 }}>El G</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Punto de venta</div>
        </div>
      </div>
      <div style={{ flexGrow: 1, display: "flex", flexDirection: "column", gap: 10, padding: "4px 12px", overflowY: "auto" }}>
        {SIDEBAR_GROUPS.map((g) => (
          <div key={g.name} style={{ display: "flex", flexDirection: "column", gap: 2 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--text-muted)", padding: "6px 12px 4px" }}>
              {g.name}
            </div>
            {g.items.map((it) =>
              it.path ? (
                <NavLink key={it.label} to={it.path} className={({ isActive }) => `sb-nav${isActive ? " on" : ""}`}>
                  <Icon d={it.d} /><span>{it.label}</span>
                </NavLink>
              ) : (
                <span key={it.label} className="sb-nav disabled" title="Próximamente">
                  <Icon d={it.d} /><span>{it.label}</span>
                </span>
              )
            )}
          </div>
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "14px 16px", borderTop: "1px solid var(--border-2)" }}>
        <div style={{
          width: 36, height: 36, borderRadius: 999, background: "#FCE7D6", color: "#9A4A12",
          display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 14,
        }}>{inicial}</div>
        <div style={{ display: "flex", flexDirection: "column", flexGrow: 1 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{usuario?.usuario}</div>
          <div style={{ fontSize: 12, color: "var(--text-muted)" }}>
            {usuario?.rol === "admin" ? "Administrador" : "Vendedor"}
          </div>
        </div>
        <button type="button" onClick={logout} aria-label="Cerrar sesión" style={{
          width: 36, height: 36, borderRadius: 10, display: "flex", alignItems: "center", justifyContent: "center",
          color: "var(--text-muted)", background: "none", border: 0, cursor: "pointer",
        }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
            strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M15 4h4v16h-4M10 8l-4 4 4 4M6 12h11" />
          </svg>
        </button>
      </div>
    </nav>
  );
}
