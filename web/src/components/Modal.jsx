import { cloneElement, isValidElement, useEffect, useId, useRef, useState } from "react";
import { IconoQuitar } from "./Iconos";

const ENFOCABLES = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
const abiertas = []; // pila: Escape y Tab solo los atiende la ventana de encima
let overflowGuardado = ""; // el de la página antes de la primera ventana

// Último control enfocado fuera de toda ventana: a dónde volver si la ventana
// se abrió desde otra que ya no existe (p. ej. "Pagar" en el detalle de una
// compra cambia esa ventana por la del pago).
let ultimoFuera = null;
if (typeof document !== "undefined") {
  document.addEventListener("focusin", (e) => {
    if (!e.target.closest?.('[role="dialog"]')) ultimoFuera = e.target;
  });
}

// Ventana modal con fondo oscuro. Se cierra con el botón ×, con Escape o con
// un clic afuera (onClose). Al abrir lleva el foco adentro (respetando un
// autoFocus del contenido), Tab no se sale de ella y al cerrar el foco vuelve
// al control que la abrió. Mientras haya ventanas abiertas la página de atrás
// no se desplaza.
export default function Modal({ titulo, onClose, children, ancho = 440 }) {
  const caja = useRef(null);
  const tituloId = useId();
  const cerrar = useRef(onClose);
  // El control que abrió la ventana: se toma en el primer render, antes de
  // que un autoFocus del contenido mueva el foco.
  const [anterior] = useState(() => document.activeElement);
  useEffect(() => { cerrar.current = onClose; });

  useEffect(() => {
    const yo = {};
    const nodo = caja.current;
    if (abiertas.length === 0) {
      overflowGuardado = document.body.style.overflow;
      document.body.style.overflow = "hidden";
    }
    abiertas.push(yo);
    if (!nodo.contains(document.activeElement)) nodo.focus();

    const onKey = (e) => {
      if (abiertas[abiertas.length - 1] !== yo) return;
      if (e.key === "Escape") {
        cerrar.current();
      } else if (e.key === "Tab") {
        const lista = [...nodo.querySelectorAll(ENFOCABLES)].filter((el) => el.offsetParent !== null);
        if (!lista.length) return;
        const primero = lista[0], ultimo = lista[lista.length - 1];
        if (e.shiftKey && (document.activeElement === primero || document.activeElement === nodo)) {
          e.preventDefault();
          ultimo.focus();
        } else if (!e.shiftKey && document.activeElement === ultimo) {
          e.preventDefault();
          primero.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      abiertas.splice(abiertas.indexOf(yo), 1);
      if (abiertas.length === 0) document.body.style.overflow = overflowGuardado;
      // Después del commit: si la ventana sigue en la página (StrictMode
      // vuelve a montar el efecto en desarrollo) no se toca el foco.
      setTimeout(() => {
        if (nodo.isConnected) return;
        const destino = anterior?.isConnected ? anterior : ultimoFuera?.isConnected ? ultimoFuera : null;
        if (destino && !document.querySelector('[role="dialog"]')?.contains(document.activeElement)) {
          destino.focus({ preventScroll: true });
        }
      });
    };
  }, [anterior]);

  return (
    <div className="modal-fondo" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={caja} role="dialog" aria-modal="true" aria-labelledby={tituloId} tabIndex={-1}
        className="card modal-caja" style={{ width: ancho }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12 }}>
          <h2 id={tituloId} style={{ fontSize: 22, minWidth: 0, overflowWrap: "anywhere" }}>{titulo}</h2>
          <button type="button" className="modal-cerrar" aria-label="Cerrar" onClick={onClose}>
            <IconoQuitar size={18} />
          </button>
        </div>
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
