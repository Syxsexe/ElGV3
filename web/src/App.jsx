import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Inicio from "./pages/Inicio";
import Usuarios from "./pages/Usuarios";
import Configuracion from "./pages/Configuracion";
import Auditoria from "./pages/Auditoria";
import Mas from "./pages/Mas";
import Inventario from "./pages/Inventario";
import Preparaciones from "./pages/Preparaciones";
import ConsultaPrecios from "./pages/ConsultaPrecios";
import Terceros from "./pages/Terceros";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Inicio />} />
        <Route path="/usuarios" element={<Usuarios />} />
        <Route path="/configuracion" element={<Configuracion />} />
        <Route path="/auditoria" element={<Auditoria />} />
        <Route path="/mas" element={<Mas />} />
        <Route path="/inventario" element={<Inventario />} />
        <Route path="/preparaciones" element={<Preparaciones />} />
        <Route path="/precios" element={<ConsultaPrecios />} />
        <Route path="/clientes" element={<Terceros key="cliente" rol="cliente" />} />
        <Route path="/proveedores" element={<Terceros key="proveedor" rol="proveedor" />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
