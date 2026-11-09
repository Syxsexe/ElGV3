import { useCallback, useEffect, useState } from "react";
import { api } from "./api";

// El turno de caja abierto, para las pantallas que cobran. Las ventas van al
// turno que se ve en pantalla (su id): si se cierra desde otra pantalla, la
// venta falla y `recargar` trae el estado nuevo.
// turno: undefined = cargando, null = no hay turno abierto.
export function useTurno() {
  const [turno, setTurno] = useState(undefined);
  const [error, setError] = useState("");

  const recargar = useCallback(() => api.turnoCaja()
    .then((r) => {
      setError("");
      // cajas: las del turno; un método de pago de otra caja no se puede usar.
      setTurno(r.turno ? { id: r.turno.id, numero: r.turno.numero, cajas: r.turno.cajas.map((c) => c.caja_id) } : null);
    })
    .catch((err) => setError(err.message)), []);

  useEffect(() => { recargar(); }, [recargar]);

  return { turno, error, recargar };
}
