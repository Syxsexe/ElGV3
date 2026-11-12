// Íconos SVG compartidos, con el mismo trazo que los del menú (stroke 1.8-2,
// puntas redondeadas). Decorativos: el botón que los usa lleva su aria-label.

export function IconoQuitar({ size = 16 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
      strokeLinecap="round" aria-hidden="true">
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

// Ícono de módulo (menú lateral y "Más"): un solo trazo `d` en 24×24.
export function IconoNav({ d, size = 18, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={d} />
    </svg>
  );
}

export function IconoFlecha({ size = 16, color = "currentColor" }) {
  return <IconoNav d="M9 6l6 6-6 6" size={size} color={color} />;
}

export function IconoCheck({ size = 16, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.4"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M5 12.5l4.5 4.5L19 7.5" />
    </svg>
  );
}
