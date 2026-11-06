import { cloneElement, isValidElement, useEffect, useId } from "react";

// Ventana modal con fondo oscuro. Escape o clic afuera la cierran (onClose).
export default function Modal({ titulo, onClose, children, ancho = 440 }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div onMouseDown={(e) => e.target === e.currentTarget && onClose()} style={{
      position: "fixed", inset: 0, background: "rgba(42,38,34,.45)", display: "flex",
      alignItems: "center", justifyContent: "center", zIndex: 50, padding: 16,
    }}>
      <div role="dialog" aria-modal="true" aria-label={titulo} className="card" style={{
        width: ancho, maxWidth: "100%", maxHeight: "calc(100vh - 32px)", overflowY: "auto",
        padding: 24, display: "flex", flexDirection: "column", gap: 16,
      }}>
        <h2 style={{ fontSize: 22 }}>{titulo}</h2>
        {children}
      </div>
    </div>
  );
}

// Campo con etiqueta, para formularios dentro de modales y páginas. La
// etiqueta se asocia por id (no envolviendo el control): así el nombre
// accesible de un <select> es la etiqueta y no el texto de todas sus opciones.
// El hijo recibe `id`: si es un componente propio (ej. BuscarMunicipio), debe
// pasarlo a su control real para que la etiqueta lo nombre.
export function Campo({ etiqueta, children, ayuda }) {
  const idPropio = useId();
  const hijo = isValidElement(children) ? children : null;
  const id = hijo?.props.id || idPropio;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <label className="lbl" htmlFor={id}>{etiqueta}</label>
      {hijo ? cloneElement(hijo, { id }) : children}
      {ayuda && <span className="muted" style={{ fontSize: 12 }}>{ayuda}</span>}
    </div>
  );
}

export function ErrorBanner({ mensaje }) {
  if (!mensaje) return null;
  return <div role="alert" className="error-banner">{mensaje}</div>;
}

// Como Campo, pero para grupos con varios controles (listas de componentes):
// un <label> con varios controles adentro les roba los clics.
export function Seccion({ etiqueta, children }) {
  return (
    <div role="group" aria-label={etiqueta} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <span className="lbl">{etiqueta}</span>
      {children}
    </div>
  );
}
