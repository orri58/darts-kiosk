import { Outlet, NavLink, Navigate } from "react-router-dom";
import { useCentralAuth } from "../../context/CentralAuthContext";
import { Button } from "../../components/ui/button";
import { Monitor, LogOut, LayoutDashboard } from "lucide-react";

export default function PortalLayout() {
  const { isAuthenticated, user, logout } = useCentralAuth();

  if (!isAuthenticated) {
    return <Navigate to="/portal/login" replace />;
  }

  return (
    <div className="min-h-screen flex" style={{ background: "#0a0a0f" }} data-testid="portal-layout">
      {/* Sidebar */}
      <aside className="w-56 border-r border-zinc-800 flex flex-col bg-zinc-900/50">
        <div className="p-4 border-b border-zinc-800">
          <h2 className="text-base font-semibold text-zinc-100">Central Portal</h2>
          <span className="text-xs text-amber-500/80">Layer A — Read-Only</span>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          <NavLink
            to="/portal"
            end
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
                isActive
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
              }`
            }
            data-testid="portal-nav-dashboard"
          >
            <LayoutDashboard size={16} />
            Dashboard
          </NavLink>
          <NavLink
            to="/portal/devices"
            className={({ isActive }) =>
              `flex items-center gap-2 px-3 py-2 rounded text-sm transition-colors ${
                isActive
                  ? "bg-zinc-800 text-zinc-100"
                  : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50"
              }`
            }
            data-testid="portal-nav-devices"
          >
            <Monitor size={16} />
            Geraete
          </NavLink>
        </nav>

        <div className="p-3 border-t border-zinc-800">
          <div className="text-xs text-zinc-500 mb-2 truncate">
            {user?.display_name || user?.username || "Portal"}
          </div>
          <Button
            data-testid="portal-logout-btn"
            variant="ghost"
            size="sm"
            className="w-full text-zinc-400 hover:text-zinc-100"
            onClick={logout}
          >
            <LogOut size={14} className="mr-2" />
            Abmelden
          </Button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-auto p-6">
        <Outlet />
      </main>
    </div>
  );
}
