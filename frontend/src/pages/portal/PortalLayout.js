import { useState } from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { Monitor, LayoutDashboard, KeyRound, Building2, MapPin, Users, Shield, LogOut } from 'lucide-react';
import ProductShell, { SurfaceBadge } from '../../components/shell/ProductShell';

export default function PortalLayout() {
  const { isAuthenticated, user, logout } = useCentralAuth();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  if (!isAuthenticated) {
    return <Navigate to="/portal/login" replace />;
  }

  return (
    <ProductShell
      testId="portal-layout"
      sidebarOpen={sidebarOpen}
      setSidebarOpen={setSidebarOpen}
      mobileTitle="Partner Portal"
      mobileSubtitle="Read-only surface"
      brandEyebrow="Darts Control"
      brandTitle="Partner Portal"
      sidebarBadge={<SurfaceBadge tone="amber">Read-only</SurfaceBadge>}
      sidebarHint="Gleiche Informationsarchitektur wie Operator — aber bewusst ohne Steuerflächen oder riskante Aktionen."
      navSections={[
        {
          label: 'Portal',
          items: [
            { path: '/portal', icon: LayoutDashboard, label: 'Übersicht', tid: 'portal-nav-dashboard', exact: true, description: 'Portfolio, Geräte, Status' },
            { path: '/portal/customers', icon: Building2, label: 'Kunden', tid: 'portal-nav-customers', description: 'Nur Lesesicht' },
            { path: '/portal/locations', icon: MapPin, label: 'Standorte', tid: 'portal-nav-locations', description: 'Scope ohne Eingriff' },
            { path: '/portal/devices', icon: Monitor, label: 'Geräte', tid: 'portal-nav-devices', description: 'Heartbeat und Bindings' },
            { path: '/portal/licenses', icon: KeyRound, label: 'Lizenzen', tid: 'portal-nav-licenses', description: 'Renewal und Capacity' },
            { path: '/portal/users', icon: Users, label: 'Benutzer', tid: 'portal-nav-users', description: 'Zugänge im Blick' },
          ],
        },
      ]}
      footer={
        <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.74)] p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[rgb(var(--color-bg-rgb)/0.5)] text-amber-300">
              <Shield className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-white">{user?.display_name || user?.username || 'Portal'}</p>
              <p className="truncate text-xs uppercase tracking-[0.2em] text-zinc-500">Read-only access</p>
            </div>
          </div>
          <button
            data-testid="portal-logout-btn"
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-2xl border border-[rgb(var(--color-border-rgb)/0.8)] bg-[rgb(var(--color-bg-rgb)/0.5)] px-4 py-2.5 text-sm text-zinc-300 transition hover:border-[rgb(var(--color-accent-rgb)/0.3)] hover:bg-[rgb(var(--color-accent-rgb)/0.12)] hover:text-[var(--color-accent)]"
            onClick={logout}
          >
            <LogOut className="h-4 w-4" /> Abmelden
          </button>
        </div>
      }
    >
      <Outlet />
    </ProductShell>
  );
}
