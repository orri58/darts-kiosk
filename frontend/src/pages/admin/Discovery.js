import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Activity,
  AlertTriangle,
  Fingerprint,
  Link2,
  Monitor,
  RefreshCw,
  Search,
  Server,
  ShieldCheck,
  ShieldX,
  Unlink,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import {
  AdminEmptyState,
  AdminLinkTile,
  AdminPage,
  AdminSection,
  AdminStatCard,
  AdminStatsGrid,
  AdminStatusPill,
} from '../../components/admin/AdminShell';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function formatDateTime(value) {
  if (!value) return '–';
  return new Date(value).toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function shortFingerprint(value) {
  if (!value) return '–';
  if (value.length <= 18) return value;
  return `${value.slice(0, 10)}…${value.slice(-6)}`;
}

export default function Discovery() {
  const { token } = useAuth();
  const { t } = useI18n();
  const [agents, setAgents] = useState([]);
  const [peers, setPeers] = useState([]);
  const [discoveryActive, setDiscoveryActive] = useState(false);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [rescanning, setRescanning] = useState(false);
  const [pairDialog, setPairDialog] = useState(null);
  const [pairCode, setPairCode] = useState('');
  const [pairing, setPairing] = useState(false);

  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const fetchAll = useCallback(async () => {
    try {
      const [agentRes, peerRes] = await Promise.all([
        axios.get(`${API}/discovery/agents`, { headers }),
        axios.get(`${API}/discovery/peers`, { headers }),
      ]);

      setAgents(agentRes.data.agents || []);
      setDiscoveryActive(Boolean(agentRes.data.discovery_active));
      setStats(agentRes.data.stats || null);
      setPeers(peerRes.data.peers || []);
    } catch (error) {
      console.error('Discovery fetch error', error);
      toast.error('Discovery-Daten konnten nicht geladen werden');
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 10000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleRescan = async () => {
    setRescanning(true);
    try {
      await axios.post(`${API}/discovery/rescan`, {}, { headers });
      toast.success('LAN-Scan neu gestartet');
      setTimeout(fetchAll, 2000);
    } catch {
      toast.error('Neu-Scan fehlgeschlagen');
    } finally {
      setRescanning(false);
    }
  };

  const openPairDialog = (agent) => {
    setPairDialog(agent);
    setPairCode('');
  };

  const doPair = async () => {
    if (!pairDialog || pairCode.length !== 6) return;

    setPairing(true);
    try {
      await axios.post(
        `${API}/discovery/pair`,
        {
          board_id: pairDialog.board_id,
          code: pairCode,
        },
        { headers }
      );
      toast.success(`${pairDialog.board_id} erfolgreich gepairt`);
      setPairDialog(null);
      fetchAll();
    } catch (error) {
      const detail = error.response?.data?.detail || 'Pairing fehlgeschlagen';
      toast.error(detail);
    } finally {
      setPairing(false);
    }
  };

  const unpair = async (peerId, boardId) => {
    if (!window.confirm(`Vertrauensbeziehung zu "${boardId}" wirklich aufheben?`)) return;

    try {
      await axios.delete(`${API}/discovery/peers/${peerId}`, { headers });
      toast.success(`${boardId} entkoppelt`);
      fetchAll();
    } catch {
      toast.error('Entkoppeln fehlgeschlagen');
    }
  };

  const metrics = useMemo(() => {
    const staleAgents = agents.filter((agent) => agent.is_stale).length;
    const pairedAgents = agents.filter((agent) => agent.is_paired).length;

    return {
      visibleAgents: agents.length,
      staleAgents,
      pairedAgents,
      scanCount: stats?.scan_count || 0,
    };
  }, [agents, stats]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <AdminPage
      eyebrow="LAN discovery"
      title={t('discovery')}
      description="Lokale mDNS-/Pairing-Oberfläche für Boards im selben Netzwerk. Nützlich für Inbetriebnahme und Vertrauensbeziehungen — ausdrücklich keine zentrale Fleet-Verwaltung über WAN oder Tailnet."
      actions={
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={handleRescan}
            disabled={rescanning}
            variant="outline"
            className="border-zinc-700 text-zinc-300 hover:text-white"
            data-testid="discovery-rescan-btn"
          >
            <Search className={`w-4 h-4 mr-2 ${rescanning ? 'animate-spin' : ''}`} />
            {rescanning ? 'Scan läuft…' : 'Neu scannen'}
          </Button>
          <Button
            onClick={fetchAll}
            variant="outline"
            className="border-zinc-700 text-zinc-300 hover:text-white"
            data-testid="discovery-refresh-btn"
          >
            <RefreshCw className="w-4 h-4 mr-2" /> Aktualisieren
          </Button>
        </div>
      }
    >
      <AdminStatsGrid>
        <AdminStatCard
          icon={Monitor}
          label="Sichtbare Agents"
          value={metrics.visibleAgents}
          hint={discoveryActive ? 'mDNS-Discovery aktiv' : 'Discovery derzeit nicht aktiv'}
          tone={discoveryActive ? 'emerald' : 'red'}
        />
        <AdminStatCard
          icon={ShieldCheck}
          label="Bereits gepairt"
          value={peers.length}
          hint="Aktive Vertrauensbeziehungen in der lokalen DB"
          tone="blue"
        />
        <AdminStatCard
          icon={AlertTriangle}
          label="Instabil / bald stale"
          value={metrics.staleAgents}
          hint="Gefunden, aber nicht mehr frisch gesehen"
          tone={metrics.staleAgents > 0 ? 'amber' : 'neutral'}
        />
        <AdminStatCard
          icon={Activity}
          label="Discovery-Scans"
          value={metrics.scanCount}
          hint={stats?.stale_timeout_seconds ? `Timeout: ${stats.stale_timeout_seconds}s` : 'mDNS-Statistik'}
          tone="violet"
        />
      </AdminStatsGrid>

      {!discoveryActive && (
        <AdminSection>
          <div className="flex items-start gap-3 rounded-2xl border border-red-500/20 bg-red-500/10 px-4 py-4 text-sm text-red-100">
            <WifiOff className="mt-0.5 h-5 w-5 flex-shrink-0 text-red-300" />
            <div>
              <p className="font-medium text-red-200">Discovery meldet sich als inaktiv</p>
              <p className="mt-1 text-red-100/80">
                Diese Ansicht sieht dann keine neuen Agents im LAN. Bereits gespeicherte Vertrauensbeziehungen bleiben zwar sichtbar,
                aber Pairing und Live-Erkennung sind in diesem Zustand nur eingeschränkt hilfreich.
              </p>
            </div>
          </div>
        </AdminSection>
      )}

      <div className="grid gap-6 xl:grid-cols-[1.25fr,0.75fr]">
        <AdminSection
          title="Erkannte Agents"
          description="Geräte, die aktuell per mDNS im lokalen Netz gesehen wurden. Stale bedeutet: gesehen, aber nicht mehr frisch."
          actions={
            <AdminStatusPill tone={discoveryActive ? 'emerald' : 'red'}>
              {discoveryActive ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
              {discoveryActive ? 'Discovery aktiv' : 'Discovery inaktiv'}
            </AdminStatusPill>
          }
        >
          {agents.length > 0 ? (
            <div className="space-y-4">
              {agents.map((agent) => {
                const tone = agent.is_paired ? 'emerald' : agent.is_stale ? 'amber' : 'blue';

                return (
                  <div
                    key={agent.board_id}
                    className="rounded-3xl border border-zinc-800 bg-zinc-900/60 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]"
                    data-testid={`agent-${agent.board_id}`}
                  >
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-lg font-semibold text-white font-mono">{agent.board_id}</p>
                          <AdminStatusPill tone={tone}>
                            {agent.is_paired ? 'Gepairt' : agent.is_stale ? 'Instabil' : 'Online'}
                          </AdminStatusPill>
                          {agent.role && <AdminStatusPill tone="neutral">{agent.role}</AdminStatusPill>}
                        </div>

                        <div className="mt-4 grid gap-3 md:grid-cols-2">
                          <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                            <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Netzwerk</p>
                            <p className="mt-2 text-sm text-zinc-200">{agent.ip}:{agent.port}</p>
                            <p className="text-xs text-zinc-500 mt-1">Version {agent.version || 'unbekannt'}</p>
                          </div>
                          <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                            <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Identität</p>
                            <p className="mt-2 text-sm text-zinc-200">Fingerprint {shortFingerprint(agent.fingerprint)}</p>
                            <p className="text-xs text-zinc-500 mt-1">Gesehen: {agent.seen_count || 0}x · zuletzt {formatDateTime(agent.last_seen)}</p>
                          </div>
                        </div>
                      </div>

                      {!agent.is_paired && (
                        <div className="flex flex-col gap-2 lg:min-w-[180px]">
                          <Button
                            size="sm"
                            onClick={() => openPairDialog(agent)}
                            className="bg-amber-500 hover:bg-amber-400 text-black"
                            data-testid={`pair-btn-${agent.board_id}`}
                          >
                            <Link2 className="w-4 h-4 mr-2" /> Pairing starten
                          </Button>
                          <p className="text-xs leading-5 text-zinc-500">
                            Benötigt den 6-stelligen Code vom Agent-/Kiosk-Screen im gleichen LAN.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <AdminEmptyState
              icon={Wifi}
              title="Keine Agents im LAN gefunden"
              description="Wenn hier nichts auftaucht, läuft entweder kein Agent im selben Netz oder die lokale Discovery ist gerade nicht aktiv."
              action={
                <Button
                  onClick={handleRescan}
                  variant="outline"
                  className="border-zinc-700 text-zinc-300 hover:text-white"
                >
                  <Search className="w-4 h-4 mr-2" /> LAN erneut scannen
                </Button>
              }
            />
          )}
        </AdminSection>

        <div className="space-y-6">
          <AdminSection title="Vertrauensbeziehungen" description="Persistierte Pairings, mit denen der Master dem jeweiligen Agent vertraut.">
            {peers.length > 0 ? (
              <div className="space-y-3">
                {peers.map((peer) => (
                  <div
                    key={peer.id}
                    className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-4"
                    data-testid={`peer-${peer.board_id}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-medium text-white font-mono">{peer.board_id}</p>
                          <AdminStatusPill tone="emerald">{peer.role || 'agent'}</AdminStatusPill>
                        </div>
                        <p className="mt-2 text-sm text-zinc-300">{peer.ip}{peer.port ? `:${peer.port}` : ''}</p>
                        <p className="mt-1 text-xs text-zinc-500">Fingerprint {shortFingerprint(peer.fingerprint)}</p>
                        <p className="mt-1 text-xs text-zinc-500">
                          Gepairt: {formatDateTime(peer.paired_at)}
                          {peer.last_seen ? ` · zuletzt gesehen ${formatDateTime(peer.last_seen)}` : ''}
                        </p>
                      </div>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => unpair(peer.id, peer.board_id)}
                        className="text-zinc-400 hover:text-red-400"
                        data-testid={`unpair-btn-${peer.board_id}`}
                      >
                        <Unlink className="w-4 h-4 mr-1" /> Entkoppeln
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <AdminEmptyState
                icon={ShieldX}
                title="Noch keine aktiven Pairings"
                description="Erst nach erfolgreichem Pairing wird ein Agent als vertrauenswürdiger Peer gespeichert."
              />
            )}
          </AdminSection>

          <AdminSection title="Was diese Seite wirklich kann" description="Lieber ehrlich als pseudo-magisch.">
            <div className="space-y-3 text-sm leading-6 text-zinc-400">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
                Discovery sieht nur Geräte, die per mDNS im gleichen lokalen Netzwerk announced werden.
              </div>
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
                Pairing erstellt eine lokale Vertrauensbeziehung. Es ersetzt keine zentrale Geräteverwaltung und löst keine Remote-Reichweitenprobleme außerhalb des LANs.
              </div>
            </div>
          </AdminSection>

          <AdminSection title="Direkt weiter" description="Benachbarte Oberflächen für den Operator-Flow.">
            <div className="space-y-3">
              <AdminLinkTile
                icon={ShieldCheck}
                title="Health"
                description="Nach dem Pairing prüfen, ob Agents und Runtime-Signale sauber laufen."
                href="/admin/health"
                tone="blue"
                cta="Health öffnen"
              />
              <AdminLinkTile
                icon={Server}
                title="System"
                description="Für Logs, Backups, Updates und host-nahe Eingriffe auf die Maintenance-Seite wechseln."
                href="/admin/system"
                tone="amber"
                cta="Zu System"
              />
            </div>
          </AdminSection>
        </div>
      </div>

      <Dialog open={!!pairDialog} onOpenChange={() => setPairDialog(null)}>
        <DialogContent className="bg-zinc-950 border-zinc-800 text-white sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-white">
              <Link2 className="w-5 h-5 text-amber-400" /> Agent pairen · {pairDialog?.board_id}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-5 py-4">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4 text-sm leading-6 text-zinc-400">
              Gib den 6-stelligen Code ein, der auf dem Agent- bzw. Kiosk-Screen angezeigt wird. Ohne gültigen Code gibt es hier bewusst kein stilles Auto-Trust.
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Netzwerk</p>
                <p className="mt-2 text-sm text-zinc-200">{pairDialog?.ip}:{pairDialog?.port}</p>
              </div>
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Fingerprint</p>
                <p className="mt-2 text-sm text-zinc-200 flex items-center gap-2">
                  <Fingerprint className="w-4 h-4 text-zinc-500" /> {shortFingerprint(pairDialog?.fingerprint)}
                </p>
              </div>
            </div>

            <Input
              value={pairCode}
              onChange={(e) => setPairCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000"
              maxLength={6}
              className="h-16 bg-zinc-900 border-zinc-700 text-center text-3xl font-mono tracking-[0.45em] text-white"
              data-testid="pair-code-input"
            />
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setPairDialog(null)} className="border-zinc-700 text-zinc-300">
              Abbrechen
            </Button>
            <Button
              onClick={doPair}
              disabled={pairCode.length !== 6 || pairing}
              className="bg-amber-500 hover:bg-amber-400 text-black"
              data-testid="pair-confirm-btn"
            >
              {pairing ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Link2 className="w-4 h-4 mr-2" />}
              {pairing ? 'Pairing läuft…' : 'Jetzt pairen'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AdminPage>
  );
}
