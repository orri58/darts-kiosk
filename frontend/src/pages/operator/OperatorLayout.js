import { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Monitor, KeyRound, Building2, MapPin,
  ScrollText, LogOut, Menu, X
} from 'lucide-react';
import { useCentralAuth } from '../../context/CentralAuthContext';

const NAV_ITEMS = [
  { path: '/operator', icon: LayoutDashboard, label: 'Übersicht', tid: 'op-nav-dashboard', exact: true },
  { path: '/operator/devices', icon: Monitor, label: 'Geräte', tid: 'op-nav-devices' },
  { path: '/operator/licenses', icon: KeyRound, label: 'Lizenzen', tid: 'op-nav-licenses' },
  { path: '/operator/customers', icon: Building2, label: 'Kunden', tid: 'op-nav-customers' },
  { path: '/operator/locations', icon: MapPin, label: 'Standorte', tid: 'op-nav-locations' },
  { path: '/operator/audit', icon: ScrollText, label: 'Aktivität', tid: 'op-nav-audit' },
];

export default function OperatorLayout() {
  const navigate = useNavigate();
  const { user, logout, loading, isAuthenticated } = useCentralAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!loading && !isAuthenticated) navigate('/operator/login');
  }, [loading, isAuthenticated, navigate]);

  const handleLogout = () => { logout(); navigate('/operator/login'); };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-zinc-950" data-testid="operator-layout">
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between px-4 h-16 z-50" data-testid="op-mobile-header">
        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 text-zinc-400 hover:text-white" data-testid="op-mobile-menu-btn">
          {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
        <h1 className="text-lg font-semibold text-white tracking-tight">Betreiber-Portal</h1>
        <div className="w-10" />
      </div>

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-full w-64 bg-zinc-900 border-r border-zinc-800 z-40 transform transition-transform duration-200 flex flex-col
        lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="h-16 flex items-center px-6 border-b border-zinc-800 flex-shrink-0">
          <h1 className="text-lg font-semibold text-white tracking-tight">Betreiber-Portal</h1>
        </div>

        <nav className="flex-1 overflow-y-auto p-4 space-y-1" data-testid="op-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              onClick={() => setSidebarOpen(false)}
              data-testid={item.tid}
              className={({ isActive }) => `
                flex items-center gap-3 px-4 py-3 rounded-lg transition-all text-sm
                ${isActive
                  ? 'bg-indigo-500/10 text-indigo-400 font-medium'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                }
              `}
            >
              <item.icon className="w-5 h-5 flex-shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="flex-shrink-0 p-4 border-t border-zinc-800">
          <div className="flex items-center gap-3 mb-3 px-2">
            <div className="w-9 h-9 rounded-full bg-indigo-500/10 flex items-center justify-center flex-shrink-0">
              <span className="text-indigo-400 font-semibold text-sm">
                {user?.display_name?.[0]?.toUpperCase() || user?.username?.[0]?.toUpperCase() || 'B'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm font-medium truncate">{user?.display_name || user?.username}</p>
              <p className="text-xs text-zinc-500">{user?.role === 'superadmin' ? 'Administrator' : 'Betreiber'}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            data-testid="op-logout-btn"
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-zinc-800 hover:bg-red-500/10 hover:text-red-400 text-zinc-400 rounded-lg transition-all text-sm"
          >
            <LogOut className="w-4 h-4" />
            <span>Abmelden</span>
          </button>
        </div>
      </aside>

      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 bg-black/50 z-30" onClick={() => setSidebarOpen(false)} />
      )}

      <main className="lg:ml-64 min-h-screen pt-16 lg:pt-0">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
