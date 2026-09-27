import { NavLink } from "react-router-dom";
import { TABBAR_ITEMS } from "../nav";

export default function TabBar() {
  return (
    <nav aria-label="Navegación principal" className="tabbar-nav" style={{
      position: "fixed", left: 0, right: 0, bottom: 0, background: "#FFFFFF",
      borderTop: "1px solid var(--border)", alignItems: "center",
      padding: "0 8px 8px", zIndex: 10,
    }}>
      {TABBAR_ITEMS.map((it) =>
        it.path ? (
          <NavLink key={it.label} to={it.path} className={({ isActive }) => `tb${isActive ? " on" : ""}`}>
            <span className="ic">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"
                strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={it.d} /></svg>
            </span>
            <span>{it.label}</span>
          </NavLink>
        ) : (
          <span key={it.label} className="tb disabled">
            <span className="ic">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"
                strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={it.d} /></svg>
            </span>
            <span>{it.label}</span>
          </span>
        )
      )}
    </nav>
  );
}
