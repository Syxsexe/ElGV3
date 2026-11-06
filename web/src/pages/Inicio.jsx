import { useAuth } from "../AuthContext";

// Provisional: el tablero de Inicio (turno, ventas del día, alertas) llega en
// el paso de reportes. Mientras tanto, los módulos se van activando en el menú.
export default function Inicio() {
  const { usuario } = useAuth();
  return (
    <div style={{ padding: "32px 24px", display: "flex", flexDirection: "column", gap: 8 }}>
      <h1 style={{ fontSize: 28 }}>Hola, {usuario?.usuario}</h1>
      <p style={{ margin: 0, color: "var(--text-muted)" }}>
        El punto de venta se está pasando a la base nueva: los módulos aparecen en el menú a medida que quedan listos.
      </p>
    </div>
  );
}
