import { useEffect, useState, useCallback } from "react";
import { useCentralAuth } from "../../context/CentralAuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import { Monitor, Wifi, WifiOff, AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "../../components/ui/button";

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

  return (
    <div data-testid="portal-dashboard" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Portal Dashboard</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Geraete-Uebersicht (Layer A — nur Lesen)
          </p>
        </div>
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
      </div>

      {error && (
        <div
          data-testid="portal-error"
          className="p-3 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm"
        >
          Fehler: {error}
        </div>
      )}

      {/* Summary Cards */}
      {dashboard && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="bg-zinc-900/80 border-zinc-800">
            <CardContent className="pt-4 pb-3 px-4">
              <div className="text-2xl font-bold text-zinc-100" data-testid="stat-customers">
                {dashboard.customers}
              </div>
              <div className="text-xs text-zinc-500">Kunden</div>
            </CardContent>
          </Card>
          <Card className="bg-zinc-900/80 border-zinc-800">
            <CardContent className="pt-4 pb-3 px-4">
              <div className="text-2xl font-bold text-zinc-100" data-testid="stat-locations">
                {dashboard.locations}
              </div>
              <div className="text-xs text-zinc-500">Standorte</div>
            </CardContent>
          </Card>
          <Card className="bg-zinc-900/80 border-zinc-800">
            <CardContent className="pt-4 pb-3 px-4">
              <div className="text-2xl font-bold text-zinc-100" data-testid="stat-devices">
                {dashboard.devices}
              </div>
              <div className="text-xs text-zinc-500">Geraete</div>
            </CardContent>
          </Card>
          <Card className="bg-zinc-900/80 border-zinc-800">
            <CardContent className="pt-4 pb-3 px-4">
              <div className="text-2xl font-bold text-zinc-100" data-testid="stat-licenses">
                {dashboard.licenses_active}/{dashboard.licenses_total}
              </div>
              <div className="text-xs text-zinc-500">Lizenzen (aktiv)</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Device List */}
      <Card className="bg-zinc-900/80 border-zinc-800">
        <CardHeader className="pb-3">
          <CardTitle className="text-base text-zinc-200 flex items-center gap-2">
            <Monitor size={16} />
            Registrierte Geraete
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading && !dashboard ? (
            <div className="text-center py-8 text-zinc-500">Laden...</div>
          ) : dashboard?.recent_devices?.length === 0 ? (
            <div className="text-center py-8 text-zinc-500">
              Keine Geraete registriert
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm" data-testid="portal-device-table">
                <thead>
                  <tr className="border-b border-zinc-800 text-zinc-500 text-xs">
                    <th className="text-left py-2 px-3">Geraet</th>
                    <th className="text-left py-2 px-3">Status</th>
                    <th className="text-left py-2 px-3">Konnektivitaet</th>
                    <th className="text-left py-2 px-3">Letzter Heartbeat</th>
                    <th className="text-left py-2 px-3">Syncs</th>
                  </tr>
                </thead>
                <tbody>
                  {(dashboard?.recent_devices || []).map((d) => (
                    <tr
                      key={d.id}
                      className="border-b border-zinc-800/50 hover:bg-zinc-800/30 transition-colors"
                      data-testid={`device-row-${d.id}`}
                    >
                      <td className="py-2.5 px-3">
                        <span className="text-zinc-200 font-medium">
                          {d.device_name || d.id?.slice(0, 8)}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className="text-zinc-400">{d.status}</span>
                      </td>
                      <td className="py-2.5 px-3">
                        <ConnBadge connectivity={d.connectivity || "offline"} />
                      </td>
                      <td className="py-2.5 px-3 text-zinc-400">
                        {d.last_heartbeat_at
                          ? timeSince(d.last_heartbeat_at) + " her"
                          : "Nie"}
                      </td>
                      <td className="py-2.5 px-3 text-zinc-400">
                        {d.sync_count ?? 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
