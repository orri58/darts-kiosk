import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useCentralAuth } from "../../context/CentralAuthContext";
import { Monitor, Wifi, WifiOff, AlertTriangle, RefreshCw, KeyRound, Clock, Sparkles, Gauge, Building2, MapPin } from "lucide-react";
import { Button } from "../../components/ui/button";
import { ProductPageHeader, ProductSection, ProductStatCard, SurfaceBadge } from "../../components/shell/ProductShell";
import { ProductCallout, ProductFocusList } from "../../components/shell/ProductDetail";

function ConnBadge({ connectivity }) {
  if (connectivity === "online")
    return (
      <span
        data-testid="device-status-online"
        className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20"
      >
        <Wifi size={12} /> Online
      </span>
    );
  if (connectivity === "degraded")
    return (
      <span
        data-testid="device-status-degraded"
        className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/20"
      >
        <AlertTriangle size={12} /> Degraded
      </span>
    );
  return (
    <span
      data-testid="device-status-offline"
      className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-zinc-500/15 text-zinc-400 border border-zinc-500/20"
    >
      <WifiOff size={12} /> Offline
    </span>
  );
}

function timeSince(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  const secs = Math.floor((Date.now() - d.getTime()) / 1000);
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h`;
  return `${Math.floor(secs / 86400)}d`;
}

export default function PortalDashboard() {
  const navigate = useNavigate();
  const { centralFetch } = useCentralAuth();
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await centralFetch("dashboard");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setDashboard(await res.json());
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

  const licensePortfolio = dashboard?.license_portfolio_summary || null;
  const counts = licensePortfolio?.counts || {};

  return (
    <div data-testid="portal-dashboard" className="space-y-6">
      <ProductPageHeader
        eyebrow="Portal Surface"
        title="Partnerübersicht"
        badge={<SurfaceBadge tone="amber">Read-only</SurfaceBadge>}
        description="Die gleiche Flotten- und Commercial-Sicht wie im Operator-Bereich — aber bewusst nur zum Beobachten und Eskalieren."
        actions={
          <Button
            data-testid="portal-refresh-btn"
            variant="outline"
            size="sm"
            onClick={refresh}
            disabled={loading}
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw size={14} className={loading ? "animate-spin mr-1" : "mr-1"} />
            Aktualisieren
          </Button>
        }
      />

      {error && (
        <div data-testid="portal-error" className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
          Fehler: {error}
        </div>
      )}

      {dashboard && (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <ProductStatCard icon={Building2} label="Kunden" value={dashboard.customers} hint="Portfolio im Scope" data-testid="stat-customers" />
          <ProductStatCard icon={MapPin} label="Standorte" value={dashboard.locations} hint="Aktive Einsatzorte" data-testid="stat-locations" />
          <ProductStatCard icon={Monitor} label="Geräte" value={dashboard.devices} hint="Gemeldete Geräte" tone="blue" data-testid="stat-devices" />
          <ProductStatCard icon={KeyRound} label="Lizenzen aktiv" value={`${dashboard.licenses_active}/${dashboard.licenses_total}`} hint="Read-only Commercial View" tone="amber" data-testid="stat-licenses" />
        </div>
      )}

      {licensePortfolio && (
        <ProductSection
          eyebrow="Commercial Readiness"
          title="Lizenzportfolio"
          description="Renewal-, Capacity- und Aktivierungsdruck im selben Raster wie Operator, aber ohne Schreibaktionen."
          actions={<Button variant="outline" size="sm" onClick={() => navigate('/portal/licenses')} className="border-zinc-700 text-zinc-300 hover:bg-zinc-800">Lizenzen öffnen</Button>}
          data-testid="portal-license-summary"
        >
          <div className="space-y-4 p-4">
            <ProductCallout
              tone={(counts.urgent ?? 0) > 0 ? 'red' : (counts.activation_gap ?? 0) > 0 ? 'amber' : 'blue'}
              eyebrow="Readiness advisory"
              title={(counts.urgent ?? 0) > 0 ? `${counts.urgent} Lizenz(en) brauchen sofort Eskalation` : 'Portfolio im Blick'}
              description={(counts.urgent ?? 0) > 0 ? 'Portal zeigt denselben Eskalationsdruck wie die Operator-Surface, aber bewusst ohne Schreibpfade.' : 'Read-only Blick auf Renewals, Aktivierungslücken und Kapazitätsdruck.'}
            />
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <ProductStatCard icon={AlertTriangle} label="Dringend" value={counts.urgent ?? 0} hint="blockiert oder inaktiv" tone="red" />
              <ProductStatCard icon={Clock} label="Renewal / Grace" value={(counts.renewal_due ?? 0) + (counts.in_grace ?? 0)} hint="bald fällig" tone="amber" />
              <ProductStatCard icon={Sparkles} label="Aktivierungslücken" value={counts.activation_gap ?? 0} hint="noch nicht live" tone="blue" />
              <ProductStatCard icon={Gauge} label="Kapazitätsdruck" value={counts.full_or_over_capacity ?? 0} hint="voll oder überzogen" />
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              <ProductFocusList title="Jetzt eskalieren" hint="Read-only Queue für kritische Fälle." items={licensePortfolio.focus_queues?.urgent || []} empty="Keine akuten Lizenzblocker." onOpen={(item) => navigate(`/portal/licenses/${item.license_id}`)} accent="red" />
              <ProductFocusList title="Renewal & Aktivierung" hint="Die nächsten kommerziellen Hebel." items={[...(licensePortfolio.focus_queues?.renewals || []), ...(licensePortfolio.focus_queues?.activation_gaps || [])].slice(0, 5)} empty="Kein unmittelbarer kommerzieller Druck." onOpen={(item) => navigate(`/portal/licenses/${item.license_id}`)} accent="amber" />
            </div>
          </div>
        </ProductSection>
      )}

      <ProductSection eyebrow="Fleet" title="Registrierte Geräte" description="Letzte Heartbeats und Konnektivität ohne Bedienlogik.">
        <div className="p-4">
          {loading && !dashboard ? (
            <div className="py-8 text-center text-zinc-500">Laden...</div>
          ) : dashboard?.recent_devices?.length === 0 ? (
            <div className="py-8 text-center text-zinc-500">Keine Geräte registriert</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="portal-device-table">
                <thead>
                  <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                    <th className="px-3 py-2">Gerät</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Konnektivität</th>
                    <th className="px-3 py-2">Letzter Heartbeat</th>
                    <th className="px-3 py-2">Syncs</th>
                  </tr>
                </thead>
                <tbody>
                  {(dashboard?.recent_devices || []).map((d) => (
                    <tr key={d.id} className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors" data-testid={`device-row-${d.id}`}>
                      <td className="px-3 py-2.5 font-medium text-zinc-200">{d.device_name || d.id?.slice(0, 8)}</td>
                      <td className="px-3 py-2.5 text-zinc-400">{d.status}</td>
                      <td className="px-3 py-2.5"><ConnBadge connectivity={d.connectivity || "offline"} /></td>
                      <td className="px-3 py-2.5 text-zinc-400">{d.last_heartbeat_at ? timeSince(d.last_heartbeat_at) + " her" : "Nie"}</td>
                      <td className="px-3 py-2.5 text-zinc-400">{d.sync_count ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </ProductSection>
    </div>
  );
}

