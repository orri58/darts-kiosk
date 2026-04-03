import { useEffect, useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  Crown,
  LayoutDashboard,
  LogOut,
  Menu,
  MonitorSpeaker,
  RadioTower,
  Server,
  Settings,
  ShieldCheck,
  Target,
  Trophy,
  TrendingUp,
  Users,
  Wifi,
  X,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useI18n } from '../../context/I18nContext';
import { AdminStatusPill } from '../../components/admin/AdminShell';

const NAV_SECTIONS = [
  {
    label: 'Dart Control',
    items: [
      { path: '/admin', icon: LayoutDashboard, labelKey: 'dashboard', tid: 'nav-dashboard', exact: true },
      { path: '/admin/boards', icon: Target, labelKey: 'boards', tid: 'nav-boards' },
      { path: '/admin/revenue', icon: TrendingUp, labelKey: 'revenue', tid: 'nav-revenue', adminOnly: true },
      { path: '/admin/reports', icon: BarChart3, labelKey: 'reports', tid: 'nav-reports', adminOnly: true },
    ],
  },
  {
    label: 'Anzeige',
    items: [
      { path: '/admin/settings', icon: Settings, labelKey: 'settings', tid: 'nav-settings', adminOnly: true },
      { path: '/admin/leaderboard', icon: Trophy, labelKey: 'leaderboard', tid: 'nav-leaderboard' },
    ],
  },
  {
    label: 'Verwaltung',
    items: [
      { path: '/admin/users', icon: Users, labelKey: 'users', tid: 'nav-users', adminOnly: true },
      { path: '/admin/discovery', icon: Wifi, labelKey: 'discovery', tid: 'nav-discovery', adminOnly: true },
      { path: '/admin/health', icon: Activity, labelKey: 'health', tid: 'nav-health', adminOnly: true },
      { path: '/admin/system', icon: Server, labelKey: 'system', tid: 'nav-system', adminOnly: true },
    ],
  },
];

export default function AdminLayout() {
  const navigate = useNavigate();
  const { user, logout, loading, isAdmin, isAuthenticated } = useAuth();
  const { branding } = useSettings();
  const { t } = useI18n();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!loading && !isAuthenticated) {
      navigate('/admin/login');
    }
  }, [loading, isAuthenticated, navigate]);

  const handleLogout = () => {
    logout();
    navigate('/admin/login');
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] text-[var(--color-text)]">
        <div className="h-10 w-10 rounded-full border-4 border-[var(--color-primary)] border-t-transparent animate-spin"></div>
      </div>
    );
  }

  if (!isAuthenticated) return null;

  return (
    <div className="min-h-screen bg-[var(--color-bg)] text-[var(--color-text)]" data-testid="admin-layout">
      <div
        className="fixed left-0 right-0 top-0 z-50 flex items-center justify-between border-b border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.94)] px-4 backdrop-blur lg:hidden"
        style={{
          paddingTop: 'var(--sat, 0px)',
          height: 'calc(4.25rem + var(--sat, 0px))',
        }}
        data-testid="mobile-header"
      >
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="p-2 text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
          data-testid="mobile-menu-btn"
        >
          {sidebarOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
        <div className="text-center">
          <p className="text-[10px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Darts Control</p>
          <h1 className="font-heading text-base uppercase tracking-[0.12em] text-[var(--color-text)] sm:text-lg">{branding.cafe_name}</h1>
        </div>
        <div className="w-10"></div>
      </div>

      <aside
        className={`
          fixed top-0 left-0 z-40 flex h-full w-72 transform flex-col border-r border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.98)] shadow-[0_24px_80px_rgba(0,0,0,0.45)] transition-transform duration-200
          lg:translate-x-0
          ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
        style={{ paddingTop: 'var(--sat, 0px)' }}
      >
        <div className="border-b border-[rgb(var(--color-border-rgb)/0.82)] px-5 py-5">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.3em] text-[var(--color-text-muted)]">Darts Control</p>
              <h1 className="mt-2 truncate font-heading text-2xl uppercase tracking-[0.08em] text-[var(--color-text)]">
                {branding.cafe_name}
              </h1>
            </div>
            <AdminStatusPill tone={isAdmin ? 'amber' : 'blue'}>
              {isAdmin ? 'Admin' : 'Staff'}
            </AdminStatusPill>
          </div>

          <div className="mt-4 rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.72)] p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-[var(--color-text)]">
              <MonitorSpeaker className="h-4 w-4 text-[var(--color-primary)]" />
              Operator-Fokus
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <AdminStatusPill tone="emerald">Local mode</AdminStatusPill>
              <AdminStatusPill tone="blue">Kiosk ready</AdminStatusPill>
              {isAdmin && <AdminStatusPill tone="amber">Config write</AdminStatusPill>}
            </div>
            <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
              Schnell freischalten, Credits nachbuchen, Boards prüfen. Der Rest steht hinten an.
            </p>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-4 py-5" data-testid="admin-nav">
          <div className="space-y-5">
            {NAV_SECTIONS.map((section) => {
              const visibleItems = section.items.filter((item) => !(item.adminOnly && !isAdmin));
              if (!visibleItems.length) return null;

              return (
                <div key={section.label} className="space-y-2">
                  <p className="px-3 text-[10px] font-semibold uppercase tracking-[0.28em] text-[var(--color-text-muted)]">{section.label}</p>
                  <div className="space-y-1">
                    {visibleItems.map((item) => (
                      <NavLink
                        key={item.path}
                        to={item.path}
                        end={item.exact}
                        onClick={() => setSidebarOpen(false)}
                        data-testid={item.tid}
                        className={({ isActive }) =>
                          `group flex items-center gap-3 rounded-2xl px-4 py-3 transition-all ${
                            isActive
                              ? 'bg-[rgb(var(--color-primary-rgb)/0.12)] text-[var(--color-primary)] shadow-[inset_0_0_0_1px_rgb(var(--color-primary-rgb)/0.24)]'
                              : 'text-[var(--color-text-secondary)] hover:bg-[rgb(var(--color-surface-rgb)/0.68)] hover:text-[var(--color-text)]'
                          }`
                        }
                      >
                        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[rgb(var(--color-bg-rgb)/0.46)] group-hover:bg-[rgb(var(--color-surface-rgb)/0.96)]">
                          <item.icon className="w-5 h-5 flex-shrink-0" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <span className="block font-medium truncate">{t(item.labelKey)}</span>
                          <span className="block text-xs text-[var(--color-text-muted)] truncate">
                            {item.path === '/admin'
                                ? 'Live-Status & Schnellaktionen'
                              : item.path === '/admin/boards'
                                ? 'Boards, Ziele und Kiosk'
                              : item.path === '/admin/revenue'
                                  ? 'Umsatz und Trends'
                                  : item.path === '/admin/reports'
                                    ? 'Session-Reports & CSV'
                                    : item.path === '/admin/settings'
                                      ? 'Branding, Pricing, Triggers'
                                      : item.path === '/admin/leaderboard'
                                        ? 'Spielerbindung & Rankings'
                                        : item.path === '/admin/users'
                                          ? 'Logins und Rollen'
                                          : item.path === '/admin/discovery'
                                            ? 'LAN-Discovery & Pairing'
                                            : item.path === '/admin/health'
                                              ? 'Runtime, Agents & Diagnose'
                                              : 'Wartung, Updates & Hostzugriff'}
                          </span>
                        </div>
                      </NavLink>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </nav>

        <div className="border-t border-[rgb(var(--color-border-rgb)/0.82)] p-4">
          <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.74)] p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[rgb(var(--color-bg-rgb)/0.5)] text-[var(--color-primary)]">
                {isAdmin ? <Crown className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-[var(--color-text)]">{user?.display_name || user?.username}</p>
                <p className="truncate text-xs uppercase tracking-[0.2em] text-[var(--color-text-muted)]">{user?.role}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              data-testid="logout-btn"
              className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl border border-[rgb(var(--color-border-rgb)/0.8)] bg-[rgb(var(--color-bg-rgb)/0.5)] px-4 py-2.5 text-sm text-[var(--color-text-secondary)] transition hover:border-[rgb(var(--color-accent-rgb)/0.3)] hover:bg-[rgb(var(--color-accent-rgb)/0.12)] hover:text-[var(--color-accent)]"
            >
              <LogOut className="w-4 h-4" />
              <span>{t('logout')}</span>
            </button>
          </div>
        </div>
      </aside>

      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 bg-black/60 z-30" onClick={() => setSidebarOpen(false)} />
      )}

      <main className="min-h-screen pwa-main-content lg:ml-72">
        <div className="p-3 md:p-5 lg:p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
