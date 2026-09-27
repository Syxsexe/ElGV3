import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../AuthContext";
import Sidebar from "./Sidebar";
import TabBar from "./TabBar";

export default function Layout() {
  const { token } = useAuth();
  if (!token) return <Navigate to="/login" replace />;

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Outlet />
      </main>
      <TabBar />
    </div>
  );
}
