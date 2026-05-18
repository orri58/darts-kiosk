import { useEffect, useState, useCallback } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { AlertTriangle, Monitor, RefreshCw, Wifi, Activity } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { useNavigate, useLocation } from 'react-router-dom';
import { ProductPageHeader, ProductSection, ProductStatCard, SurfaceBadge } from '../../components/shell/ProductShell';
import { ProductFilterSummary, ProductPageState } from '../../components/shell/ProductDataDisplay';
import { ProductFleetCardGrid, ProductFleetEmptyState } from '../../components/shell/ProductSurfaceSystems';

export default function PortalDevices() {
  const navigate = useNavigate();
  const location = useLocation();
  const { centralFetch } = useCentralAuth();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await centralFetch('licensing/devices');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setDevices(await res.json());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [centralFetch]);

  useEffect(() => {
    refresh();
    const iv = setInterval(refresh, 30000);
    return () => clearInterval(iv);
  }, [refresh]);

  const onlineCount = devices.filter((d) => d.connectivity === 'online' || d.is_online).length;
  const degradedCount = devices.filter((d) => d.connectivity === 'degraded').length;
  const licensedCount = devices.filter((d) => Boolean(d.license_id)).length;
  const surfacePrefix = location.pathname.startsWith('/operator') ? '/operator' : '/portal';
  const currentListPath = `${location.pathname}${location.search || ''}`;
  const openDevice = (d) => navigate(`${surfacePrefix}/devices/${d.id}?returnTo=${encodeURIComponent(currentListPath)}&returnLabel=${encodeURIComponent('Geräte')}`);
  const openLicense = (d) => navigate(`${surfacePrefix}/licenses/${d.license_id}?intent=devices&returnTo=${encodeURIComponent(currentListPath)}&returnLabel=${encodeURIComponent('Geräte')}`);

  return (
    <div data-testid="portal-devices-page" className="space-y-6">
      <ProductPageHeader
        eyebrow="Fleet"
        title="Geräte"
        badge={<SurfaceBadge tone="amber">Read-only</SurfaceBadge>}
        description={`${devices.length} registriert, ${onlineCount} online${degradedCount ? `, ${degradedCount} degraded` : ''}. Dieselbe Fleet-Anatomie wie Operator, aber ohne Eingriffe.`}
        actions={
          <Button
            data-testid="portal-devices-refresh"
            variant="outline"
            size="sm"
            onClick={refresh}
            disabled={loading}
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw size={14} className={loading ? 'mr-1 animate-spin' : 'mr-1'} />
            Aktualisieren
          </Button>
        }
      />

      <div className="grid gap-3 md:grid-cols-4">
        <ProductStatCard icon={Monitor} label="Geräte gesamt" value={devices.length} hint="Registrierte Geräte" data-testid="portal-devices-total" />
        <ProductStatCard icon={Wifi} label="Online" value={onlineCount} hint="Geräte mit aktiver Verbindung" tone="emerald" data-testid="portal-devices-online" />
        <ProductStatCard icon={AlertTriangle} label="Degraded" value={degradedCount} hint="Instabiler Runtime-Zustand" tone="amber" data-testid="portal-devices-degraded" />
        <ProductStatCard icon={Activity} label="Lizenziert" value={licensedCount} hint="Mit Lizenzbezug" tone="blue" data-testid="portal-devices-licensed" />
      </div>

      {error && <ProductPageState kind="error" compact title="Geräte konnten nicht geladen werden" description={error} data-testid="portal-devices-error" />}

      {loading && devices.length === 0 ? (
        <ProductPageState kind="loading" title="Geräte werden geladen" description="Die read-only Fleet-Sicht wird mit Heartbeats, Bindings und Lizenzbezügen aufgebaut." data-testid="portal-devices-loading" />
      ) : devices.length === 0 ? (
        <ProductFleetEmptyState scopeLabel="Geräte" readOnly testId="portal-devices-empty" />
      ) : (
        <ProductSection eyebrow="Inventory" title="Fleet Cards" description="Shared Karten-Semantik für Heartbeat, Binding, Lizenz und Detail-Drill-in.">
          <div className="space-y-4 p-4">
            <ProductFilterSummary
              label="Scope"
              items={[
                { key: 'Geräte', value: String(devices.length) },
                { key: 'Online', value: String(onlineCount) },
                { key: 'Instabil', value: String(degradedCount) },
                { key: 'Lizenziert', value: String(licensedCount) },
              ]}
              data-testid="portal-devices-scope-summary"
            />

            <ProductFleetCardGrid
              devices={devices}
              onOpenDevice={openDevice}
              onOpenLicense={openLicense}
              surfacePrefix={surfacePrefix}
              currentListPath={currentListPath}
            />
          </div>
        </ProductSection>
      )}
    </div>
  );
}
