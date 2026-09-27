import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Cuentas from "./pages/Cuentas";
import Venta from "./pages/Venta";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/cuentas" replace />} />
        <Route path="/cuentas" element={<Cuentas />} />
        <Route path="/venta" element={<Venta />} />
      </Route>
      <Route path="*" element={<Navigate to="/cuentas" replace />} />
    </Routes>
  );
}
