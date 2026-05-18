import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { useLocation, useNavigate } from 'react-router-dom';
import { Activity, Monitor, Wifi, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import axios from 'axios';
import { ProductPageHeader, ProductSection, ProductStatCard } from '../../components/shell/ProductShell';
import { ProductFilterSummary, ProductPageState } from '../../components/shell/ProductDataDisplay';
import { ProductFleetEmptyState, ProductFleetTable } from '../../components/shell/ProductSurfaceSystems';

export default function OperatorDevices() {
  const navigate = useNavigate();
  const location = useLocation();
  const { apiBase, authHeaders, canManage } = useCentralAuth();
  const { data: devices, loading, error, refetch } = useCentralData('licensing/devices');

  const handleToggle = async (d) => {
    const newStatus = d.status === 'active' ? 'disabled' : 'active';
    try {
      await axios.put(`${apiBase}/licensing/devices/${d.id}`, { status: newStatus }, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
      toast.success(newStatus === 'active' ? 'Gerät aktiviert' : 'Gerät deaktiviert');
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Fehler');
    }
  };

  if (loading) return <ProductPageState kind="loading" title="Geräte werden geladen" description="Inventory, Bindings und letzte Syncs werden aus dem Central Scope gezogen." data-testid="operator-devices-loading" />;
  if (error) return <ProductPageState kind="error" title="Geräte konnten nicht geladen werden" description={error} data-testid="operator-devices-error" />;

  const list = devices || [];
  const onlineCount = list.filter((d) => d.connectivity === 'online' || d.is_online).length;
  const degradedCount = list.filter((d) => d.connectivity === 'degraded').length;
  const licensedCount = list.filter((d) => Boolean(d.license_id)).length;
  const surfacePrefix = location.pathname.startsWith('/portal') ? '/portal' : '/operator';
  const currentListPath = `${location.pathname}${location.search || ''}`;
  const openDevice = (d) => navigate(`${surfacePrefix}/devices/${d.id}?returnTo=${encodeURIComponent(currentListPath)}&returnLabel=${encodeURIComponent('Geräte')}`);
  const openLicense = (d) => navigate(`${surfacePrefix}/licenses/${d.license_id}?intent=devices&returnTo=${encodeURIComponent(currentListPath)}&returnLabel=${encodeURIComponent('Geräte')}`);
  const openRemoteActions = (d) => navigate(`/operator/remote-actions?device_id=${encodeURIComponent(d.id)}`);

  return (
    <div className="space-y-6" data-testid="operator-devices">
      <ProductPageHeader
        eyebrow="Fleet"
        title="Geräte"
        description={`${list.length} registriert, ${onlineCount} online${degradedCount ? `, ${degradedCount} degraded` : ''}. Dieselbe Fleet-Semantik wie Portal, aber mit direktem Steuerzugang.`}
      />

      <div className="grid gap-3 md:grid-cols-4">
        <ProductStatCard icon={Monitor} label="Geräte gesamt" value={list.length} hint="Im aktuellen Operator-Scope" data-testid="operator-devices-total" />
        <ProductStatCard icon={Wifi} label="Online" value={onlineCount} hint="Aktive Verbindung / Heartbeat" tone="emerald" data-testid="operator-devices-online" />
        <ProductStatCard icon={AlertTriangle} label="Degraded" value={degradedCount} hint="Beobachtung oder Störung" tone="amber" data-testid="operator-devices-degraded" />
        <ProductStatCard icon={Activity} label="Lizenziert" value={licensedCount} hint="Mit gebundener Lizenz" tone="blue" data-testid="operator-devices-licensed" />
      </div>

      <ProductSection eyebrow="Inventory" title="Fleet Table" description="Shared Tabellen-Semantik für Gerät, Binding, Lizenz, Sync und Drill-in.">
        <div className="space-y-4 p-4">
          <ProductFilterSummary
            label="Scope"
            items={[
              { key: 'Geräte', value: String(list.length) },
              { key: 'Online', value: String(onlineCount) },
              { key: 'Instabil', value: String(degradedCount) },
              { key: 'Lizenziert', value: String(licensedCount) },
            ]}
            data-testid="operator-devices-scope-summary"
          />

          {list.length === 0 ? (
            <ProductFleetEmptyState scopeLabel="Geräte" compact testId="operator-devices-empty" />
          ) : (
            <ProductFleetTable
              devices={list}
              canManage={canManage}
              onOpenDevice={openDevice}
              onOpenLicense={openLicense}
              onOpenRemoteActions={openRemoteActions}
              onToggleDevice={handleToggle}
            />
          )}
        </div>
      </ProductSection>
    </div>
  );
}
