import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { api, clearToken, getToken, setToken, UNAUTHORIZED_EVENT } from "./api";

const AuthContext = createContext(null);

function decodeUsuario(token) {
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return { usuario: payload.usuario, rol: payload.rol };
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setTokenState] = useState(() => getToken());
  const [usuario, setUsuario] = useState(() => decodeUsuario(getToken()));

  const login = async (nombre, contrasena) => {
    const data = await api.login(nombre, contrasena);
    setToken(data.token);
    setTokenState(data.token);
    setUsuario({ usuario: data.usuario, rol: data.rol });
  };

  const logout = () => {
    clearToken();
    setTokenState(null);
    setUsuario(null);
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

  const value = useMemo(() => ({ token, usuario, login, logout }), [token, usuario]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
