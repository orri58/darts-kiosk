import { useState, useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Monitor, KeyRound, Building2, MapPin,
  ScrollText, Users, Shield, Workflow
} from 'lucide-react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import ScopeSwitcher from '../../components/central/ScopeSwitcher';
import ProductShell, { SurfaceBadge } from '../../components/shell/ProductShell';

export default function OperatorLayout() {
  const navigate = useNavigate();
  const { user, logout, loading, isAuthenticated, canManage, canManageStaff, canReviewRemoteActions, roleLabel } = useCentralAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (!loading && !isAuthenticated) navigate('/operator/login');
  }, [loading, isAuthenticated, navigate]);

  const handleLogout = () => { logout(); navigate('/operator/login'); };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--color-bg)] text-[var(--color-text)]">
        <div className="h-10 w-10 rounded-full border-4 border-[var(--color-primary)] border-t-transparent animate-spin" />
      </div>
    );
  }
  if (!isAuthenticated) return null;

  const navItems = [
    { path: '/operator', icon: LayoutDashboard, label: 'Übersicht', tid: 'op-nav-dashboard', exact: true, description: 'Betrieb, Umsatz, Queue-Druck' },
  ];
  if (canManage) navItems.push({ path: '/operator/customers', icon: Building2, label: 'Kunden', tid: 'op-nav-customers', description: 'Verträge und Portfolio' });
  navItems.push({ path: '/operator/locations', icon: MapPin, label: 'Standorte', tid: 'op-nav-locations', description: 'Filtern nach Einsatzort' });
  navItems.push({ path: '/operator/devices', icon: Monitor, label: 'Geräte', tid: 'op-nav-devices', description: 'Live-Zustand und Bindings' });
  if (canManage) navItems.push({ path: '/operator/licenses', icon: KeyRound, label: 'Lizenzen', tid: 'op-nav-licenses', description: 'Kommerzieller Druck' });
  if (canManageStaff) navItems.push({ path: '/operator/users', icon: Users, label: 'Benutzer', tid: 'op-nav-users', description: 'Operator-Zugänge' });
  if (canReviewRemoteActions || canManage) navItems.push({ path: '/operator/remote-actions', icon: Workflow, label: 'Remote Actions', tid: 'op-nav-remote-actions', description: 'Review und Delivery' });
  navItems.push({ path: '/operator/audit', icon: ScrollText, label: 'Aktivität', tid: 'op-nav-audit', description: 'Nachvollziehbarkeit' });

  return (
    <ProductShell
      testId="operator-layout"
      sidebarOpen={sidebarOpen}
      setSidebarOpen={setSidebarOpen}
      mobileTitle="Operator Console"
      mobileSubtitle="Darts Control"
      brandEyebrow="Darts Control"
      brandTitle="Operator Console"
      sidebarBadge={<SurfaceBadge tone="blue">Active Operations</SurfaceBadge>}
      sidebarHint="Steuert Kunden, Geräte und Remote-Workflows mit derselben Produktlogik wie Admin und Portal."
      navSections={[{ label: 'Betreiberfläche', items: navItems }]}
      topbar={<ScopeSwitcher />}
      footer={
        <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.74)] p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[rgb(var(--color-bg-rgb)/0.5)] text-[var(--color-primary)]">
              <Shield className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{user?.display_name || user?.username}</p>
              <p className="truncate text-xs uppercase tracking-[0.2em] text-zinc-500">{roleLabel}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            data-testid="op-logout-btn"
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl border border-[rgb(var(--color-border-rgb)/0.8)] bg-[rgb(var(--color-bg-rgb)/0.5)] px-4 py-2.5 text-sm text-zinc-300 transition hover:border-[rgb(var(--color-accent-rgb)/0.3)] hover:bg-[rgb(var(--color-accent-rgb)/0.12)] hover:text-[var(--color-accent)]"
          >
            Abmelden
          </button>
        </div>
      }
    >
      <Outlet />
    </ProductShell>
  );
}
