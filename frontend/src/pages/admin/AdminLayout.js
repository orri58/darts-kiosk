import { useEffect, useState } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import {
  Activity,
  BarChart3,
  Crown,
  LayoutDashboard,
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
  LogOut,
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useI18n } from '../../context/I18nContext';
import ProductShell, { SurfaceBadge } from '../../components/shell/ProductShell';

const NAV_SECTIONS = [
  {
    label: 'Dart Control',
    items: [
      { path: '/admin', icon: LayoutDashboard, labelKey: 'dashboard', tid: 'nav-dashboard', exact: true, description: 'Kasse, Sessions, Health' },
      { path: '/admin/boards', icon: Target, labelKey: 'boards', tid: 'nav-boards', description: 'Boards und Aktivität' },
      { path: '/admin/revenue', icon: TrendingUp, labelKey: 'revenue', tid: 'nav-revenue', adminOnly: true, description: 'Umsatz direkt am Standort' },
      { path: '/admin/reports', icon: BarChart3, labelKey: 'reports', tid: 'nav-reports', adminOnly: true, description: 'Trends und Exporte' },
    ],
  },
  {
    label: 'Anzeige',
    items: [
      { path: '/admin/settings', icon: Settings, labelKey: 'settings', tid: 'nav-settings', adminOnly: true, description: 'Branding, Display, Regeln' },
      { path: '/admin/leaderboard', icon: Trophy, labelKey: 'leaderboard', tid: 'nav-leaderboard', description: 'Public-facing Surface' },
    ],
  },
  {
    label: 'Verwaltung',
    items: [
      { path: '/admin/users', icon: Users, labelKey: 'users', tid: 'nav-users', adminOnly: true, description: 'Zugänge am Gerät' },
      { path: '/admin/discovery', icon: Wifi, labelKey: 'discovery', tid: 'nav-discovery', adminOnly: true, description: 'Verbindungen prüfen' },
      { path: '/admin/health', icon: Activity, labelKey: 'health', tid: 'nav-health', adminOnly: true, description: 'Betriebszustand' },
      { path: '/admin/system', icon: Server, labelKey: 'system', tid: 'nav-system', adminOnly: true, description: 'Runtime und Service' },
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

  const navSections = NAV_SECTIONS.map((section) => ({
    ...section,
    items: section.items
      .filter((item) => !(item.adminOnly && !isAdmin))
      .map((item) => ({ ...item, label: t(item.labelKey) })),
  })).filter((section) => section.items.length > 0);

  return (
    <ProductShell
      testId="admin-layout"
      sidebarOpen={sidebarOpen}
      setSidebarOpen={setSidebarOpen}
      mobileTitle={branding.cafe_name}
      mobileSubtitle="Darts Control"
      brandEyebrow="Darts Control"
      brandTitle={branding.cafe_name}
      sidebarBadge={<SurfaceBadge tone={isAdmin ? 'amber' : 'blue'}>{isAdmin ? 'Admin' : 'Staff'}</SurfaceBadge>}
      sidebarHint={<span className="inline-flex items-center gap-2"><MonitorSpeaker className="h-4 w-4 text-[var(--color-primary)]" /> Schnell freischalten, nachbuchen, prüfen.</span>}
      navSections={navSections}
      footer={
        <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.74)] p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[rgb(var(--color-bg-rgb)/0.5)] text-[var(--color-primary)]">
              {isAdmin ? <Crown className="h-5 w-5" /> : <ShieldCheck className="h-5 w-5" />}
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{user?.display_name || user?.username}</p>
              <p className="truncate text-xs uppercase tracking-[0.2em] text-zinc-500">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            data-testid="logout-btn"
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl border border-[rgb(var(--color-border-rgb)/0.8)] bg-[rgb(var(--color-bg-rgb)/0.5)] px-4 py-2.5 text-sm text-zinc-300 transition hover:border-[rgb(var(--color-accent-rgb)/0.3)] hover:bg-[rgb(var(--color-accent-rgb)/0.12)] hover:text-[var(--color-accent)]"
          >
            <LogOut className="h-4 w-4" />
            <span>{t('logout')}</span>
          </button>
        </div>
      }
    >
      <Outlet />
    </ProductShell>
  );
}
