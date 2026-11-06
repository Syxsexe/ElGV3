const API_BASE = import.meta.env.VITE_API_BASE;
const TOKEN_KEY = "elg_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

// AuthContext escucha este evento para sincronizar su estado en React: sin
// esto, un 401 limpia localStorage pero el `token` en memoria de React sigue
// viendo la sesión como activa (Layout no redirige a /login) hasta recargar.
export const UNAUTHORIZED_EVENT = "elg:unauthorized";

function notificarNoAutorizado() {
  window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
}

// FastAPI manda `detail` como string en nuestros errores de negocio (400/403),
// pero como un ARRAY de objetos {msg,...} en errores 422 de validación de
// Pydantic — sin esto, `new Error(array)` se convierte en "[object Object]" y
// el mensaje real nunca le llega al usuario.
function mensajeDeError(data, status) {
  const detail = data?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d?.msg || JSON.stringify(d)).join("; ");
  }
  if (detail) return JSON.stringify(detail);
  return `Error ${status}`;
}

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  // Un 401 con token es una sesión vencida o revocada. Sin token (el propio
  // login) es "usuario o contraseña incorrectos": se muestra el detail del servidor.
  if (res.status === 401 && token) {
    clearToken();
    notificarNoAutorizado();
    throw new ApiError("Sesión expirada, vuelve a ingresar.", 401);
  }

  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    throw new ApiError(mensajeDeError(data, res.status), res.status);
  }
  return data;
}

export const api = {
  login: (usuario, contrasena) =>
    request("/auth/login", { method: "POST", body: { usuario, contrasena } }),
  yo: () => request("/auth/yo"),
  cambiarMiContrasena: (actual, nueva) =>
    request("/auth/contrasena", { method: "POST", body: { actual, nueva } }),

  usuarios: () => request("/usuarios"),
  crearUsuario: (body) => request("/usuarios", { method: "POST", body }),
  editarUsuario: (id, body) => request(`/usuarios/${id}`, { method: "PATCH", body }),
  restablecerContrasena: (id, contrasena) =>
    request(`/usuarios/${id}/contrasena`, { method: "POST", body: { contrasena } }),
  roles: () => request("/roles"),
  permisos: () => request("/permisos"),
  crearRol: (body) => request("/roles", { method: "POST", body }),
  editarRol: (id, body) => request(`/roles/${id}`, { method: "PATCH", body }),
  borrarRol: (id) => request(`/roles/${id}`, { method: "DELETE" }),

  empresa: () => request("/config/empresa"),
  editarEmpresa: (body) => request("/config/empresa", { method: "PATCH", body }),
  tiposIdentificacion: () => request("/config/tipos-identificacion"),
  municipios: (q) => request(`/config/municipios?q=${encodeURIComponent(q)}`),
  cajas: () => request("/config/cajas"),
  crearCaja: (body) => request("/config/cajas", { method: "POST", body }),
  editarCaja: (id, body) => request(`/config/cajas/${id}`, { method: "PATCH", body }),
  crearMetodoPago: (body) => request("/config/metodos-pago", { method: "POST", body }),
  editarMetodoPago: (id, body) => request(`/config/metodos-pago/${id}`, { method: "PATCH", body }),
  // catalogo: "mesas" | "categorias-gasto" | "juegos"
  catalogo: (catalogo, todos = false) => request(`/config/${catalogo}${todos ? "?todos=true" : ""}`),
  crearEnCatalogo: (catalogo, nombre) => request(`/config/${catalogo}`, { method: "POST", body: { nombre } }),
  editarEnCatalogo: (catalogo, id, body) => request(`/config/${catalogo}/${id}`, { method: "PATCH", body }),

  auditoria: (filtros) => {
    const params = new URLSearchParams(Object.entries(filtros).filter(([, v]) => v));
    return request(`/auditoria?${params}`);
  },
};

export { ApiError };
