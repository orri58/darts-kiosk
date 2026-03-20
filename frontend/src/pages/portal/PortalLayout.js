import { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Monitor, KeyRound, Building2, MapPin,
  ScrollText, LogOut, Menu, X, Users, Shield
} from 'lucide-react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import ScopeSwitcher from '../../components/central/ScopeSwitcher';

export default function PortalLayout() {
  const navigate = useNavigate();
  const { user, logout, loading, isAuthenticated, isSuperadmin, canManage, canManageStaff, roleLabel } = useCentralAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!loading && !isAuthenticated) navigate('/portal/login');
  }, [loading, isAuthenticated, navigate]);

  const handleLogout = () => { logout(); navigate('/portal/login'); };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!isAuthenticated) return null;

  // Dynamic nav based on role
  const NAV_ITEMS = [
    { path: '/portal', icon: LayoutDashboard, label: 'Uebersicht', tid: 'portal-nav-dashboard', exact: true },
  ];
  if (canManage) {
    NAV_ITEMS.push({ path: '/portal/customers', icon: Building2, label: 'Kunden', tid: 'portal-nav-customers' });
  }
  NAV_ITEMS.push({ path: '/portal/locations', icon: MapPin, label: 'Standorte', tid: 'portal-nav-locations' });
  NAV_ITEMS.push({ path: '/portal/devices', icon: Monitor, label: 'Geraete', tid: 'portal-nav-devices' });
  if (canManage) {
    NAV_ITEMS.push({ path: '/portal/licenses', icon: KeyRound, label: 'Lizenzen', tid: 'portal-nav-licenses' });
  }
  if (canManageStaff) {
    NAV_ITEMS.push({ path: '/portal/users', icon: Users, label: 'Benutzer', tid: 'portal-nav-users' });
  }
  NAV_ITEMS.push({ path: '/portal/audit', icon: ScrollText, label: 'Aktivitaet', tid: 'portal-nav-audit' });

  return (
    <div className="min-h-screen bg-zinc-950" data-testid="portal-layout">
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between px-4 h-14 z-50" data-testid="portal-mobile-header">
        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 text-zinc-400 hover:text-white" data-testid="portal-mobile-menu-btn">
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
        <h1 className="text-base font-semibold text-white tracking-tight">DartControl</h1>
        <div className="w-10" />
      </div>

      {/* Sidebar */}
      <aside className={`
        fixed top-0 left-0 h-full w-60 bg-zinc-900 border-r border-zinc-800 z-40 transform transition-transform duration-200 flex flex-col
        lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="h-14 flex items-center px-5 border-b border-zinc-800 flex-shrink-0 gap-2">
          <Shield className="w-5 h-5 text-indigo-400" />
          <h1 className="text-base font-semibold text-white tracking-tight">DartControl</h1>
        </div>

        <nav className="flex-1 overflow-y-auto p-3 space-y-0.5" data-testid="portal-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              onClick={() => setSidebarOpen(false)}
              data-testid={item.tid}
              className={({ isActive }) => `
                flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-sm
                ${isActive
                  ? 'bg-indigo-500/10 text-indigo-400 font-medium'
                  : 'text-zinc-400 hover:text-white hover:bg-zinc-800/60'
                }
              `}
            >
              <item.icon className="w-4.5 h-4.5 flex-shrink-0" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="flex-shrink-0 p-3 border-t border-zinc-800">
          <div className="flex items-center gap-2.5 mb-2.5 px-2">
            <div className="w-8 h-8 rounded-full bg-indigo-500/10 flex items-center justify-center flex-shrink-0">
              <span className="text-indigo-400 font-semibold text-xs">
                {user?.display_name?.[0]?.toUpperCase() || user?.username?.[0]?.toUpperCase() || 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm font-medium truncate">{user?.display_name || user?.username}</p>
              <p className="text-xs text-zinc-500">{roleLabel}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            data-testid="portal-logout-btn"
            className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-zinc-800 hover:bg-red-500/10 hover:text-red-400 text-zinc-400 rounded-lg transition-all text-sm"
          >
            <LogOut className="w-4 h-4" />
            <span>Abmelden</span>
          </button>
        </div>
      </aside>

      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 bg-black/50 z-30" onClick={() => setSidebarOpen(false)} />
      )}

      <main className="lg:ml-60 min-h-screen pt-14 lg:pt-0">
        {/* Scope Switcher Bar */}
        <div className="sticky top-0 z-20 bg-zinc-950/90 backdrop-blur-sm border-b border-zinc-800/50 px-5 py-2.5" data-testid="scope-bar">
          <ScopeSwitcher />
        </div>
        <div className="p-5">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
