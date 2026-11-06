import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, clearToken, getToken, setToken, UNAUTHORIZED_EVENT } from "./api";

const AuthContext = createContext(null);

// El token solo lleva el id del usuario: nombre, rol y permisos se piden al
// servidor (/auth/yo), que los lee de la base en cada request. Así un cambio
// de rol se ve al recargar, sin volver a iniciar sesión.
export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => getToken());
  const [usuario, setUsuario] = useState(null);
  const [errorSesion, setErrorSesion] = useState("");

  // Un 401 lo maneja api.js (cierra la sesión); cualquier otro error (API
  // reiniciando, sin red) se muestra con opción de reintentar.
  const cargarUsuario = useCallback(() => {
    return api.yo().then((u) => {
      setErrorSesion("");
      setUsuario(u);
    }).catch((err) => {
      if (err.status !== 401) setErrorSesion(err.message || "No se pudo cargar la sesión.");
    });
  }, []);

  // Al abrir la app con un token guardado. Tras un login el usuario ya viene
  // en la respuesta, así que no se vuelve a pedir.
  useEffect(() => {
    if (token && !usuario) cargarUsuario();
  }, [token, usuario, cargarUsuario]);

  const login = async (nombre, contrasena) => {
    const { token: nuevo, ...datos } = await api.login(nombre, contrasena);
    setToken(nuevo);
    setUsuario(datos);
    setTokenState(nuevo);
  };

  const logout = () => {
    clearToken();
    setTokenState(null);
    setUsuario(null);
    setErrorSesion("");
  };

  // api.js dispara este evento cuando un 401 ya limpió localStorage; sin este
  // listener el estado en memoria de React seguiría creyendo que hay sesión.
  useEffect(() => {
    const onUnauthorized = () => {
      setTokenState(null);
      setUsuario(null);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  const value = useMemo(() => {
    // La web oculta lo que el usuario no puede usar; el servidor igual lo valida.
    const puede = (permiso) => !permiso || Boolean(usuario?.permisos?.includes(permiso));
    return { token, usuario, errorSesion, cargarUsuario, login, logout, puede };
  }, [token, usuario, errorSesion, cargarUsuario]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
