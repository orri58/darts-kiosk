import { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  LogOut,
  Menu,
  X,
  Activity,
  KeyRound,
  Terminal,
  ExternalLink
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useI18n } from '../../context/I18nContext';

// Stripped-down nav: diagnostics + board control only
const NAV_ITEMS = [
  { path: '/admin', icon: LayoutDashboard, label: 'Board-Kontrolle', tid: 'nav-dashboard', exact: true },
  { path: '/admin/health', icon: Activity, label: 'System & Health', tid: 'nav-health', adminOnly: true },
  { path: '/admin/licensing', icon: KeyRound, label: 'Lizenz-Status', tid: 'nav-licensing', adminOnly: true },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const { user, logout, loading, isAdmin, isAuthenticated } = useAuth();
  const { branding } = useSettings();
  const { t } = useI18n();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!loading && !isAuthenticated) navigate('/admin/login');
  }, [loading, isAuthenticated, navigate]);

  const handleLogout = () => { logout(); navigate('/admin/login'); };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0e14] flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }
  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-[#0a0e14]" data-testid="admin-layout">
      {/* Mobile Header */}
      <div
        className="lg:hidden fixed top-0 left-0 right-0 bg-[#0d1117] border-b border-cyan-900/30 flex items-center justify-between px-4 z-50"
        style={{ paddingTop: 'var(--sat, 0px)', height: 'calc(3.5rem + var(--sat, 0px))' }}
        data-testid="mobile-header"
      >
        <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 text-cyan-600 hover:text-cyan-400" data-testid="mobile-menu-btn">
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-cyan-500" />
          <span className="text-sm font-mono text-cyan-400 tracking-wider">LOCAL SERVICE</span>
        </div>
        <div className="w-10" />
      </div>

      {/* Sidebar — technical/debug style */}
      <aside className={`
        fixed top-0 left-0 h-full w-56 bg-[#0d1117] border-r border-cyan-900/20 z-40 transform transition-transform duration-200 flex flex-col
        lg:translate-x-0 ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="h-14 flex items-center px-4 border-b border-cyan-900/20 flex-shrink-0 gap-2">
          <Terminal className="w-4 h-4 text-cyan-500" />
          <span className="text-sm font-mono text-cyan-400 tracking-wider">LOCAL SERVICE</span>
        </div>

        {/* Device info badge */}
        <div className="mx-3 mt-3 p-2.5 rounded bg-cyan-950/30 border border-cyan-900/20">
          <p className="text-[10px] font-mono text-cyan-600 uppercase tracking-wider">Geraet</p>
          <p className="text-xs font-mono text-cyan-300 truncate">{branding.cafe_name || 'Kiosk'}</p>
        </div>

        <nav className="flex-1 overflow-y-auto p-3 mt-2 space-y-0.5" data-testid="admin-nav">
          {NAV_ITEMS.map((item) => {
            if (item.adminOnly && !isAdmin) return null;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                end={item.exact}
                onClick={() => setSidebarOpen(false)}
                data-testid={item.tid}
                className={({ isActive }) => `
                  flex items-center gap-2.5 px-3 py-2 rounded transition-all text-sm font-mono
                  ${isActive
                    ? 'bg-cyan-500/10 text-cyan-400 border-l-2 border-cyan-500'
                    : 'text-zinc-500 hover:text-cyan-300 hover:bg-cyan-950/30'
                  }
                `}
              >
                <item.icon className="w-4 h-4 flex-shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Portal link */}
        <div className="p-3">
          <a
            href="/portal/login"
            className="flex items-center gap-2 px-3 py-2 rounded text-xs font-mono text-indigo-400/70 hover:text-indigo-400 hover:bg-indigo-500/5 transition-colors"
            data-testid="portal-link"
          >
            <ExternalLink className="w-3.5 h-3.5" />
            Zentrales Portal
          </a>
        </div>

        {/* User & Logout */}
        <div className="flex-shrink-0 p-3 border-t border-cyan-900/20">
          <div className="flex items-center gap-2 mb-2 px-1">
            <div className="w-7 h-7 rounded bg-cyan-950/50 border border-cyan-900/30 flex items-center justify-center flex-shrink-0">
              <span className="text-cyan-500 font-mono text-xs">{user?.username?.[0]?.toUpperCase() || '?'}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-cyan-300 text-xs font-mono truncate">{user?.username}</p>
              <p className="text-[10px] text-cyan-700 font-mono uppercase">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            data-testid="logout-btn"
            className="w-full flex items-center justify-center gap-2 px-3 py-1.5 bg-cyan-950/30 hover:bg-red-500/10 hover:text-red-400 text-cyan-700 rounded transition-all text-xs font-mono"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Abmelden</span>
          </button>
        </div>
      </aside>

      {sidebarOpen && <div className="lg:hidden fixed inset-0 bg-black/60 z-30" onClick={() => setSidebarOpen(false)} />}

      <main className="lg:ml-56 min-h-screen pwa-main-content">
        <div className="p-5">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
