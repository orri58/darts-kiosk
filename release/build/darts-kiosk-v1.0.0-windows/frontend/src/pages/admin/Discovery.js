import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Wifi,
  WifiOff,
  Shield,
  ShieldCheck,
  ShieldX,
  RefreshCw,
  Link2,
  Unlink,
  Fingerprint,
  Clock,
  Monitor,
  Server,
  Activity,
  Search,
  AlertTriangle
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/dialog';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function AgentStatusBadge({ agent }) {
  if (agent.is_paired) {
    return <span className="text-xs px-2 py-1 rounded bg-emerald-500/20 text-emerald-400">Gepairt</span>;
  }
  if (agent.is_stale) {
    return <span className="text-xs px-2 py-1 rounded bg-amber-500/20 text-amber-400">Instabil</span>;
  }
  return <span className="text-xs px-2 py-1 rounded bg-blue-500/20 text-blue-400">Online</span>;
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
  const headers = { Authorization: `Bearer ${token}` };

  const fetchAll = useCallback(async () => {
    try {
      const [agentRes, peerRes] = await Promise.all([
        axios.get(`${API}/discovery/agents`, { headers }),
        axios.get(`${API}/discovery/peers`, { headers }),
      ]);
      setAgents(agentRes.data.agents || []);
      setDiscoveryActive(agentRes.data.discovery_active);
      setStats(agentRes.data.stats || null);
      setPeers(peerRes.data.peers || []);
    } catch (err) {
      console.error('Discovery fetch error', err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 10000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  const handleRescan = async () => {
    setRescanning(true);
    try {
      await axios.post(`${API}/discovery/rescan`, {}, { headers });
      toast.success('Netzwerk-Scan neu gestartet');
      setTimeout(fetchAll, 2000);
    } catch {
      toast.error('Re-Scan fehlgeschlagen');
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
      await axios.post(`${API}/discovery/pair`, {
        board_id: pairDialog.board_id,
        code: pairCode,
      }, { headers });
      toast.success(`${pairDialog.board_id} erfolgreich gepairt!`);
      setPairDialog(null);
      fetchAll();
    } catch (err) {
      const detail = err.response?.data?.detail || 'Pairing fehlgeschlagen';
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <div data-testid="admin-discovery">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-heading uppercase tracking-wider text-white">{t('board_discovery')}</h1>
          <p className="text-zinc-500 flex items-center gap-2">
            mDNS Netzwerk-Erkennung
            {discoveryActive
              ? <span className="inline-flex items-center gap-1 text-xs text-emerald-500"><Wifi className="w-3 h-3" /> Aktiv</span>
              : <span className="inline-flex items-center gap-1 text-xs text-red-500"><WifiOff className="w-3 h-3" /> Inaktiv</span>
            }
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={handleRescan}
            disabled={rescanning}
            variant="outline"
            className="border-zinc-700 text-zinc-400 hover:text-white"
            data-testid="discovery-rescan-btn"
          >
            <Search className={`w-4 h-4 mr-2 ${rescanning ? 'animate-spin' : ''}`} />
            {rescanning ? 'Scanne...' : 'Neu scannen'}
          </Button>
          <Button onClick={fetchAll} variant="outline" className="border-zinc-700 text-zinc-400 hover:text-white" data-testid="discovery-refresh-btn">
            <RefreshCw className="w-4 h-4 mr-2" /> Aktualisieren
          </Button>
        </div>
      </div>

      {/* Discovery Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-sm">
            <p className="text-xs text-zinc-500 uppercase">Aktive Agents</p>
            <p className="text-xl font-mono font-bold text-white" data-testid="stat-active-agents">{stats.active_agents}</p>
          </div>
          <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-sm">
            <p className="text-xs text-zinc-500 uppercase">Gepairt</p>
            <p className="text-xl font-mono font-bold text-emerald-400" data-testid="stat-paired-agents">{stats.paired_agents}</p>
          </div>
          <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-sm">
            <p className="text-xs text-zinc-500 uppercase">Gesamt entdeckt</p>
            <p className="text-xl font-mono font-bold text-zinc-300">{stats.total_discovered}</p>
          </div>
          <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-sm">
            <p className="text-xs text-zinc-500 uppercase">Scans</p>
            <p className="text-xl font-mono font-bold text-zinc-300">{stats.scan_count}</p>
          </div>
        </div>
      )}

      {/* Discovered Agents */}
      <Card className="bg-zinc-900 border-zinc-800 mb-6">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Monitor className="w-5 h-5 text-amber-500" /> Erkannte Agents ({agents.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {agents.length > 0 ? (
            <div className="space-y-3">
              {agents.map((agent) => (
                <div
                  key={agent.board_id}
                  className={`flex items-center justify-between p-4 rounded-sm border ${
                    agent.is_stale
                      ? 'bg-amber-500/5 border-amber-500/20'
                      : 'bg-zinc-800/50 border-zinc-700/50'
                  }`}
                  data-testid={`agent-${agent.board_id}`}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded flex items-center justify-center ${
                      agent.is_paired ? 'bg-emerald-500/20' : agent.is_stale ? 'bg-amber-500/20' : 'bg-blue-500/20'
                    }`}>
                      {agent.is_paired
                        ? <ShieldCheck className="w-5 h-5 text-emerald-500" />
                        : agent.is_stale
                          ? <AlertTriangle className="w-5 h-5 text-amber-500" />
                          : <Shield className="w-5 h-5 text-blue-500" />
                      }
                    </div>
                    <div>
                      <p className="text-white font-mono font-bold">{agent.board_id}</p>
                      <p className="text-xs text-zinc-500">
                        {agent.ip}:{agent.port} | v{agent.version} | fp: {agent.fingerprint}
                      </p>
                      <p className="text-xs text-zinc-600 flex items-center gap-2">
                        <Activity className="w-3 h-3" />
                        Gesehen: {agent.seen_count}x | Zuletzt: {new Date(agent.last_seen).toLocaleTimeString('de-DE')}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <AgentStatusBadge agent={agent} />
                    {!agent.is_paired && (
                      <Button
                        size="sm"
                        onClick={() => openPairDialog(agent)}
                        className="bg-amber-500 hover:bg-amber-400 text-black"
                        data-testid={`pair-btn-${agent.board_id}`}
                      >
                        <Link2 className="w-3 h-3 mr-1" /> Pairen
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-zinc-500">
              <Wifi className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>Keine Agents im Netzwerk gefunden</p>
              <p className="text-xs mt-1">Stellen Sie sicher, dass Agent-PCs im selben LAN laufen</p>
              <Button
                onClick={handleRescan}
                variant="outline"
                size="sm"
                className="mt-3 border-zinc-700 text-zinc-400 hover:text-white"
              >
                <Search className="w-3 h-3 mr-1" /> Netzwerk erneut scannen
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Paired Peers */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-500" /> Vertrauensbeziehungen ({peers.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {peers.length > 0 ? (
            <div className="space-y-3">
              {peers.map((peer) => (
                <div
                  key={peer.id}
                  className="flex items-center justify-between p-4 bg-zinc-800/50 rounded-sm"
                  data-testid={`peer-${peer.board_id}`}
                >
                  <div className="flex items-center gap-4">
                    <Fingerprint className="w-5 h-5 text-emerald-500" />
                    <div>
                      <p className="text-white font-mono">{peer.board_id} <span className="text-xs text-zinc-500">({peer.role})</span></p>
                      <p className="text-xs text-zinc-500">
                        {peer.ip}{peer.port ? `:${peer.port}` : ''} | v{peer.version || '?'} | fp: {peer.fingerprint}
                      </p>
                      <p className="text-xs text-zinc-600">
                        Gepairt: {peer.paired_at ? new Date(peer.paired_at).toLocaleString('de-DE') : '-'}
                        {peer.last_seen && <span className="ml-2">Zuletzt: {new Date(peer.last_seen).toLocaleString('de-DE')}</span>}
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => unpair(peer.id, peer.board_id)}
                    className="text-zinc-400 hover:text-red-500"
                    data-testid={`unpair-btn-${peer.board_id}`}
                  >
                    <Unlink className="w-4 h-4 mr-1" /> Entkoppeln
                  </Button>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-zinc-500">
              <ShieldX className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>Noch keine Agents gepairt</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pairing Dialog */}
      <Dialog open={!!pairDialog} onOpenChange={() => setPairDialog(null)}>
        <DialogContent className="bg-zinc-900 border-zinc-800 text-white">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-amber-500" />
              Agent pairen: {pairDialog?.board_id}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <p className="text-sm text-zinc-400">
              Geben Sie den 6-stelligen Code ein, der auf dem Kiosk-Bildschirm des Agents angezeigt wird.
            </p>
            <div className="flex items-center gap-2">
              <Server className="w-5 h-5 text-zinc-500" />
              <span className="text-sm text-zinc-400">{pairDialog?.ip}:{pairDialog?.port}</span>
            </div>
            <Input
              value={pairCode}
              onChange={(e) => setPairCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="000000"
              maxLength={6}
              className="text-center text-3xl font-mono tracking-[0.5em] bg-zinc-800 border-zinc-700 text-white h-16"
              data-testid="pair-code-input"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPairDialog(null)} className="border-zinc-700 text-zinc-400">
              Abbrechen
            </Button>
            <Button
              onClick={doPair}
              disabled={pairCode.length !== 6 || pairing}
              className="bg-amber-500 hover:bg-amber-400 text-black"
              data-testid="pair-confirm-btn"
            >
              {pairing ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Link2 className="w-4 h-4 mr-2" />}
              Pairen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
