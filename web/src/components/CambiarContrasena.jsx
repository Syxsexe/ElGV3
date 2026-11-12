import { useState } from "react";
import { api, setToken } from "../api";
import Modal, { Campo, ErrorBanner } from "./Modal";
import { unaVez } from "../formularios";

export default function CambiarContrasena({ onClose }) {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetida, setRepetida] = useState("");
  const [error, setError] = useState("");
  const [listo, setListo] = useState(false);

  const guardar = async (e) => {
    e.preventDefault();
    setError("");
    if (nueva !== repetida) return setError("Las contraseñas nuevas no coinciden.");
    try {
      // Las demás sesiones quedan cerradas; esta sigue con el token nuevo.
      const { token } = await api.cambiarMiContrasena(actual, nueva);
      setToken(token);
      setListo(true);
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <Modal titulo="Cambiar mi contraseña" onClose={onClose}>
      {listo ? (
        <>
          <p style={{ margin: 0 }}>Listo. Las sesiones abiertas en otros equipos se cerraron; aquí sigues adentro.</p>
          <button type="button" className="btn btn-p" onClick={onClose}>Cerrar</button>
        </>
      ) : (
        <form onSubmit={unaVez(guardar)} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Campo etiqueta="Contraseña actual">
            <input className="inp" type="password" autoComplete="current-password" required
              value={actual} onChange={(e) => setActual(e.target.value)} />
          </Campo>
          <Campo etiqueta="Contraseña nueva" ayuda="Al menos 8 caracteres.">
            <input className="inp" type="password" autoComplete="new-password" required minLength={8}
              value={nueva} onChange={(e) => setNueva(e.target.value)} />
          </Campo>
          <Campo etiqueta="Repítela">
            <input className="inp" type="password" autoComplete="new-password" required
              value={repetida} onChange={(e) => setRepetida(e.target.value)} />
          </Campo>
          <ErrorBanner mensaje={error} />
          <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
            <button type="button" className="btn btn-s" onClick={onClose}>Cancelar</button>
            <button type="submit" className="btn btn-p">Guardar</button>
          </div>
        </form>
      )}
    </Modal>
  );
}
