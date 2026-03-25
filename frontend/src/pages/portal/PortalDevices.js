import { useEffect, useState, useCallback } from "react";
import { useCentralAuth } from "../../context/CentralAuthContext";
import { Card, CardContent, CardHeader, CardTitle } from "../../components/ui/card";
import {
  Monitor,
  Wifi,
  WifiOff,
  AlertTriangle,
  RefreshCw,
  Activity,
  Clock,
} from "lucide-react";
import { Button } from "../../components/ui/button";

function ConnBadge({ connectivity }) {
  if (connectivity === "online")
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
        <Wifi size={12} /> Online
      </span>
    );
  if (connectivity === "degraded")
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/20">
        <AlertTriangle size={12} /> Degraded
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-zinc-500/15 text-zinc-400 border border-zinc-500/20">
      <WifiOff size={12} /> Offline
    </span>
  );
}

function formatDt(isoStr) {
  if (!isoStr) return "—";
  try {
    return new Date(isoStr).toLocaleString("de-DE", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return isoStr;
  }
}

export default function PortalDevices() {
  const { centralFetch } = useCentralAuth();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await centralFetch("licensing/devices");
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

  const onlineCount = devices.filter((d) => d.connectivity === "online" || d.is_online).length;

  return (
    <div data-testid="portal-devices-page" className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-zinc-100">Geraete</h1>
          <p className="text-sm text-zinc-500 mt-1">
            {devices.length} registriert, {onlineCount} online
          </p>
        </div>
        <Button
          data-testid="portal-devices-refresh"
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
        <div className="p-3 rounded bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
          Fehler: {error}
        </div>
      )}

      {loading && devices.length === 0 ? (
        <div className="text-center py-12 text-zinc-500">Laden...</div>
      ) : devices.length === 0 ? (
        <Card className="bg-zinc-900/80 border-zinc-800">
          <CardContent className="py-12 text-center text-zinc-500">
            Keine Geraete registriert. Geraete erscheinen hier sobald sie sich beim
            Central Server registrieren.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {devices.map((d) => (
            <Card
              key={d.id}
              className="bg-zinc-900/80 border-zinc-800 hover:border-zinc-700 transition-colors"
              data-testid={`portal-device-card-${d.id}`}
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between">
                  <CardTitle className="text-sm text-zinc-200 flex items-center gap-2">
                    <Monitor size={15} className="text-zinc-500" />
                    {d.device_name || d.id?.slice(0, 8)}
                  </CardTitle>
                  <ConnBadge connectivity={d.connectivity || (d.is_online ? "online" : "offline")} />
                </div>
              </CardHeader>
              <CardContent className="space-y-2 text-xs text-zinc-400">
                <div className="flex justify-between">
                  <span className="flex items-center gap-1">
                    <Activity size={12} /> Status
                  </span>
                  <span className="text-zinc-300">{d.status || "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span>Version</span>
                  <span className="text-zinc-300 font-mono text-xs">
                    {d.reported_version || "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="flex items-center gap-1">
                    <Clock size={12} /> Heartbeat
                  </span>
                  <span className="text-zinc-300">{formatDt(d.last_heartbeat_at)}</span>
                </div>
                <div className="flex justify-between">
                  <span>Binding</span>
                  <span className="text-zinc-300">{d.binding_status || "—"}</span>
                </div>
                <div className="flex justify-between">
                  <span>Syncs</span>
                  <span className="text-zinc-300">{d.sync_count ?? 0}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
