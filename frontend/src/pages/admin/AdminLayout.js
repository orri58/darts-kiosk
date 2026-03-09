import { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Target, 
  Settings, 
  Users, 
  FileText, 
  TrendingUp, 
  LogOut,
  Menu,
  X,
  Activity,
  Server,
  Wifi,
  Trophy,
  BarChart3
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useI18n } from '../../context/I18nContext';

const NAV_ITEMS = [
  { path: '/admin', icon: LayoutDashboard, labelKey: 'dashboard', tid: 'nav-dashboard', exact: true },
  { path: '/admin/boards', icon: Target, labelKey: 'boards', tid: 'nav-boards' },
  { path: '/admin/settings', icon: Settings, labelKey: 'settings', tid: 'nav-settings', adminOnly: true },
  { path: '/admin/users', icon: Users, labelKey: 'users', tid: 'nav-users', adminOnly: true },
  { path: '/admin/logs', icon: FileText, labelKey: 'logs', tid: 'nav-logs', adminOnly: true },
  { path: '/admin/revenue', icon: TrendingUp, labelKey: 'revenue', tid: 'nav-revenue', adminOnly: true },
  { path: '/admin/health', icon: Activity, labelKey: 'health', tid: 'nav-health', adminOnly: true },
  { path: '/admin/system', icon: Server, labelKey: 'system', tid: 'nav-system', adminOnly: true },
  { path: '/admin/discovery', icon: Wifi, labelKey: 'discovery', tid: 'nav-discovery', adminOnly: true },
  { path: '/admin/leaderboard', icon: Trophy, labelKey: 'leaderboard', tid: 'nav-leaderboard' },
  { path: '/admin/reports', icon: BarChart3, labelKey: 'reports', tid: 'nav-reports', adminOnly: true },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const { user, logout, loading, isAdmin, isAuthenticated } = useAuth();
  const { branding } = useSettings();
  const { t } = useI18n();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Redirect if not authenticated
  useEffect(() => {
    if (!loading && !isAuthenticated) {
      navigate('/admin/login');
    }
  }, [loading, isAuthenticated, navigate]);

  // Switch PWA manifest to admin version so "Add to Home Screen" opens /admin
  useEffect(() => {
    const link = document.querySelector('link[rel="manifest"]');
    const appleName = document.querySelector('meta[name="apple-mobile-web-app-title"]');
    if (link) link.setAttribute('href', '/manifest-admin.json');
    if (appleName) appleName.setAttribute('content', 'Darts Admin');
    document.title = 'Darts Admin';
    return () => {
      if (link) link.setAttribute('href', '/manifest.json');
      if (appleName) appleName.setAttribute('content', 'Darts Kiosk');
      document.title = 'Darts Kiosk';
    };
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/admin/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return null;
  }

  return (
    <div className="min-h-screen bg-zinc-950" data-testid="admin-layout">
      {/* Mobile Header */}
      <div className="lg:hidden fixed top-0 left-0 right-0 h-16 bg-zinc-900 border-b border-zinc-800 flex items-center justify-between px-4 z-50">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 text-zinc-400 hover:text-white"
          data-testid="mobile-menu-btn"
        >
          {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
        <h1 className="font-heading text-lg uppercase tracking-wider text-white">
          {branding.cafe_name}
        </h1>
        <div className="w-10"></div>
      </div>

      {/* Sidebar */}
      <aside
        className={`
          fixed top-0 left-0 h-full w-64 bg-zinc-900 border-r border-zinc-800 z-40 transform transition-transform duration-200 flex flex-col
          lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* Logo - fixed top */}
        <div className="h-16 flex items-center px-6 border-b border-zinc-800 flex-shrink-0">
          <h1 className="font-heading text-xl uppercase tracking-wider text-white truncate">
            {branding.cafe_name}
          </h1>
        </div>

        {/* Navigation - scrollable */}
        <nav className="flex-1 overflow-y-auto p-4 space-y-1" data-testid="admin-nav">
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
                  flex items-center gap-3 px-4 py-3 rounded-sm transition-all
                  ${isActive
                    ? 'bg-amber-500/10 text-amber-500 border-l-2 border-amber-500'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                  }
                `}
              >
                <item.icon className="w-5 h-5 flex-shrink-0" />
                <span className="font-medium truncate">{t(item.labelKey)}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* User Info & Logout - fixed bottom */}
        <div className="flex-shrink-0 p-4 border-t border-zinc-800">
          <div className="flex items-center gap-3 mb-3 px-2">
            <div className="w-9 h-9 rounded-full bg-zinc-800 flex items-center justify-center flex-shrink-0">
              <span className="text-amber-500 font-heading text-sm">
                {user?.username?.[0]?.toUpperCase() || 'U'}
              </span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm font-medium truncate">{user?.display_name || user?.username}</p>
              <p className="text-xs text-zinc-500 uppercase">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            data-testid="logout-btn"
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-zinc-800 hover:bg-red-500/20 hover:text-red-400 text-zinc-400 rounded-sm transition-all text-sm"
          >
            <LogOut className="w-4 h-4" />
            <span>{t('logout')}</span>
          </button>
        </div>
      </aside>

      {/* Overlay for mobile */}
      {sidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <main className="lg:ml-64 pt-16 lg:pt-0 min-h-screen">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
