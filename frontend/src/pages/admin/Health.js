import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Activity, 
  RefreshCw, 
  Server, 
  Database, 
  Clock, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  Wifi,
  WifiOff,
  Camera,
  Download,
  Trash2,
  HardDrive,
  Cloud,
  CloudOff,
  ArrowDownToLine
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useAuth } from '../../context/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminHealth() {
  const { token } = useAuth();
  const [health, setHealth] = useState(null);
  const [backups, setBackups] = useState(null);
  const [screenshots, setScreenshots] = useState([]);
  const [configSync, setConfigSync] = useState(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [syncing, setSyncing] = useState(false);

  const fetchHealth = useCallback(async () => {
    try {
      const [healthRes, backupsRes, screenshotsRes, configRes] = await Promise.all([
        axios.get(`${API}/health/detailed`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/backups`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/health/screenshots`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/licensing/config-sync-status`).catch(() => ({ data: null })),
      ]);
      setHealth(healthRes.data);
      setBackups(backupsRes.data);
      setScreenshots(screenshotsRes.data);
      setConfigSync(configRes.data);
    } catch (error) {
      console.error('Failed to fetch health:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const createBackup = async () => {
    setCreating(true);
    try {
      await axios.post(`${API}/backups/create`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Backup erstellt');
      fetchHealth();
    } catch (error) {
      toast.error('Backup fehlgeschlagen');
    } finally {
      setCreating(false);
    }
  };

  const downloadBackup = async (filename) => {
    try {
      const response = await axios.get(`${API}/backups/download/${filename}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      toast.error('Download fehlgeschlagen');
    }
  };

  const deleteBackup = async (filename) => {
    if (!window.confirm(`Backup "${filename}" wirklich loeschen?`)) return;
    
    try {
      await axios.delete(`${API}/backups/${filename}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Backup geloescht');
      fetchHealth();
    } catch (error) {
      toast.error('Loeschen fehlgeschlagen');
    }
  };

  const forceConfigSync = async () => {
    setSyncing(true);
    try {
      const res = await axios.post(`${API}/licensing/force-config-sync`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(res.data.config_changed ? 'Config aktualisiert' : 'Config ist aktuell');
      fetchHealth();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Config-Sync fehlgeschlagen');
    } finally {
      setSyncing(false);
    }
  };

  const formatUptime = (seconds) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'healthy': return 'text-emerald-500';
      case 'degraded': return 'text-amber-500';
      case 'unhealthy': return 'text-red-500';
      default: return 'text-zinc-500';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'healthy': return <CheckCircle className="w-6 h-6 text-emerald-500" />;
      case 'degraded': return <AlertTriangle className="w-6 h-6 text-amber-500" />;
      case 'unhealthy': return <XCircle className="w-6 h-6 text-red-500" />;
      default: return <Activity className="w-6 h-6 text-zinc-500" />;
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
    <div data-testid="admin-health">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-mono tracking-wider text-cyan-400 uppercase">System & Health</h1>
          <p className="text-xs text-cyan-700 font-mono">Lokale Diagnostik & Services</p>
        </div>
        <Button
          onClick={fetchHealth}
          variant="outline"
          className="border-cyan-900/30 text-cyan-600 hover:text-cyan-400 hover:border-cyan-700 font-mono text-xs"
        >
          <RefreshCw className="w-3.5 h-3.5 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Status Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-6">
        <Card className="bg-[#0d1117] border-cyan-900/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              {getStatusIcon(health?.status)}
              <div>
                <p className="text-[10px] text-cyan-700 uppercase font-mono">System</p>
                <p className={`text-lg font-mono font-bold uppercase ${getStatusColor(health?.status)}`}>
                  {health?.status || 'Unknown'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-[#0d1117] border-cyan-900/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <Clock className="w-5 h-5 text-cyan-600" />
              <div>
                <p className="text-[10px] text-cyan-700 uppercase font-mono">Uptime</p>
                <p className="text-lg font-mono font-bold text-cyan-300">
                  {formatUptime(health?.uptime_seconds || 0)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-[#0d1117] border-cyan-900/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              {configSync?.configured
                ? <Cloud className="w-5 h-5 text-emerald-500" />
                : <CloudOff className="w-5 h-5 text-zinc-600" />
              }
              <div>
                <p className="text-[10px] text-cyan-700 uppercase font-mono">Config Sync</p>
                <p className={`text-lg font-mono font-bold ${configSync?.configured ? 'text-emerald-400' : 'text-zinc-500'}`}>
                  {configSync?.configured ? `v${configSync.config_version}` : 'Offline'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-[#0d1117] border-cyan-900/20">
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <HardDrive className="w-5 h-5 text-cyan-600" />
              <div>
                <p className="text-[10px] text-cyan-700 uppercase font-mono">Backups</p>
                <p className="text-lg font-mono font-bold text-cyan-300">
                  {backups?.stats?.total_backups || 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="services" className="space-y-4">
        <TabsList className="bg-[#0d1117] border border-cyan-900/20 p-1">
          <TabsTrigger value="services" className="data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400 text-cyan-700 font-mono text-xs">
            <Server className="w-3.5 h-3.5 mr-1.5" />
            Services
          </TabsTrigger>
          <TabsTrigger value="config" className="data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400 text-cyan-700 font-mono text-xs">
            <Cloud className="w-3.5 h-3.5 mr-1.5" />
            Config Sync
          </TabsTrigger>
          <TabsTrigger value="agents" className="data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400 text-cyan-700 font-mono text-xs">
            <Wifi className="w-3.5 h-3.5 mr-1.5" />
            Agents
          </TabsTrigger>
          <TabsTrigger value="backups" className="data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400 text-cyan-700 font-mono text-xs">
            <Database className="w-3.5 h-3.5 mr-1.5" />
            Backups
          </TabsTrigger>
          <TabsTrigger value="errors" className="data-[state=active]:bg-cyan-500/10 data-[state=active]:text-cyan-400 text-cyan-700 font-mono text-xs">
            <Camera className="w-3.5 h-3.5 mr-1.5" />
            Fehler
          </TabsTrigger>
        </TabsList>

        {/* Services Tab */}
        <TabsContent value="services">
          <Card className="bg-[#0d1117] border-cyan-900/20">
            <CardHeader>
              <CardTitle className="text-cyan-300 font-mono text-sm">Hintergrund-Services</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Scheduler */}
              <div className="flex items-center justify-between p-4 bg-zinc-800/50 rounded-sm">
                <div className="flex items-center gap-3">
                  <Clock className="w-5 h-5 text-zinc-500" />
                  <div>
                    <p className="text-white font-medium">Session Scheduler</p>
                    <p className="text-sm text-zinc-500">Auto-Lock & Expiry Check</p>
                  </div>
                </div>
                <div className={`flex items-center gap-2 px-3 py-1 rounded-sm ${health?.scheduler_running ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                  {health?.scheduler_running ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  <span className="text-sm">{health?.scheduler_running ? 'Running' : 'Stopped'}</span>
                </div>
              </div>

              {/* Backup Service */}
              <div className="flex items-center justify-between p-4 bg-zinc-800/50 rounded-sm">
                <div className="flex items-center gap-3">
                  <HardDrive className="w-5 h-5 text-zinc-500" />
                  <div>
                    <p className="text-white font-medium">Backup Service</p>
                    <p className="text-sm text-zinc-500">Auto-Backup alle {backups?.stats?.backup_interval_hours || 6}h</p>
                  </div>
                </div>
                <div className={`flex items-center gap-2 px-3 py-1 rounded-sm ${health?.backup_service_running ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                  {health?.backup_service_running ? <CheckCircle className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                  <span className="text-sm">{health?.backup_service_running ? 'Running' : 'Stopped'}</span>
                </div>
              </div>

              {/* Automation Metrics */}
              <div className="p-4 bg-zinc-800/50 rounded-sm">
                <div className="flex items-center gap-3 mb-4">
                  <Activity className="w-5 h-5 text-zinc-500" />
                  <p className="text-white font-medium">Autodarts Automation</p>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-zinc-500">Total</p>
                    <p className="text-xl font-mono text-white">{health?.automation_metrics?.total_attempts || 0}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500">Erfolgreich</p>
                    <p className="text-xl font-mono text-emerald-400">{health?.automation_metrics?.successful || 0}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500">Fehlgeschlagen</p>
                    <p className="text-xl font-mono text-red-400">{health?.automation_metrics?.failed || 0}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500">Erfolgsrate</p>
                    <p className="text-xl font-mono text-amber-400">{health?.automation_metrics?.success_rate?.toFixed(1) || 0}%</p>
                  </div>
                </div>
                {health?.automation_metrics?.last_error && (
                  <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-sm">
                    <p className="text-sm text-red-400">Letzter Fehler: {health.automation_metrics.last_error}</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Config Sync Tab */}
        <TabsContent value="config">
          <Card className="bg-[#0d1117] border-cyan-900/20">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-cyan-300 font-mono text-sm">Zentrale Konfiguration</CardTitle>
                <Button
                  onClick={forceConfigSync}
                  disabled={syncing || !configSync?.configured}
                  className="bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-900/30 font-mono text-xs"
                  data-testid="force-config-sync-btn"
                >
                  {syncing ? <RefreshCw className="w-3.5 h-3.5 mr-1.5 animate-spin" /> : <ArrowDownToLine className="w-3.5 h-3.5 mr-1.5" />}
                  Sync jetzt
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 bg-cyan-950/20 rounded border border-cyan-900/15">
                  <p className="text-[10px] text-cyan-700 uppercase font-mono">Status</p>
                  <p className={`text-sm font-mono font-bold ${configSync?.configured ? 'text-emerald-400' : 'text-zinc-500'}`}>
                    {configSync?.configured ? 'Verbunden' : 'Nicht konfiguriert'}
                  </p>
                </div>
                <div className="p-3 bg-cyan-950/20 rounded border border-cyan-900/15">
                  <p className="text-[10px] text-cyan-700 uppercase font-mono">Config Version</p>
                  <p className="text-sm font-mono font-bold text-cyan-300">v{configSync?.config_version || 0}</p>
                </div>
                <div className="p-3 bg-cyan-950/20 rounded border border-cyan-900/15">
                  <p className="text-[10px] text-cyan-700 uppercase font-mono">Letzter Sync</p>
                  <p className="text-sm font-mono text-cyan-300">
                    {configSync?.last_sync_at ? new Date(configSync.last_sync_at).toLocaleString('de-DE') : '—'}
                  </p>
                </div>
                <div className="p-3 bg-cyan-950/20 rounded border border-cyan-900/15">
                  <p className="text-[10px] text-cyan-700 uppercase font-mono">Sync Loop</p>
                  <p className={`text-sm font-mono font-bold ${configSync?.running ? 'text-emerald-400' : 'text-zinc-500'}`}>
                    {configSync?.running ? 'Aktiv' : 'Inaktiv'}
                  </p>
                </div>
              </div>
              {configSync?.last_error && (
                <div className="p-2.5 bg-red-500/5 border border-red-500/20 rounded">
                  <p className="text-xs font-mono text-red-400">{configSync.last_error}</p>
                </div>
              )}
              <p className="text-[10px] text-cyan-800 font-mono">
                Konfiguration wird zentral ueber /portal verwaltet. Lokale Aenderungen sind temporaer.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Agents Tab */}
        <TabsContent value="agents">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white">Agent-Verbindungen</CardTitle>
            </CardHeader>
            <CardContent>
              {Object.keys(health?.agent_status || {}).length > 0 ? (
                <div className="space-y-3">
                  {Object.entries(health.agent_status).map(([boardId, agent]) => (
                    <div key={boardId} className="flex items-center justify-between p-4 bg-zinc-800/50 rounded-sm">
                      <div className="flex items-center gap-3">
                        {agent.is_online ? <Wifi className="w-5 h-5 text-emerald-500" /> : <WifiOff className="w-5 h-5 text-red-500" />}
                        <div>
                          <p className="text-white font-medium">{boardId}</p>
                          <p className="text-sm text-zinc-500 font-mono">{agent.agent_url}</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className={`px-3 py-1 rounded-sm ${agent.is_online ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                          {agent.is_online ? 'Online' : 'Offline'}
                        </div>
                        {agent.latency_ms && (
                          <p className="text-xs text-zinc-500 mt-1">{agent.latency_ms}ms</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-zinc-500 py-8">Keine Agents konfiguriert</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Backups Tab */}
        <TabsContent value="backups">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-white">Datenbank-Backups</CardTitle>
                <Button
                  onClick={createBackup}
                  disabled={creating}
                  className="bg-amber-500 hover:bg-amber-400 text-black"
                >
                  {creating ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Database className="w-4 h-4 mr-2" />}
                  Backup erstellen
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[400px] overflow-y-auto">
                {backups?.backups?.length > 0 ? (
                  backups.backups.map((backup) => (
                    <div key={backup.filename} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm">
                      <div>
                        <p className="text-white font-mono text-sm">{backup.filename}</p>
                        <p className="text-xs text-zinc-500">
                          {new Date(backup.created_at).toLocaleString('de-DE')} • {backup.size_mb} MB
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => downloadBackup(backup.filename)}
                          className="text-zinc-400 hover:text-amber-500"
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => deleteBackup(backup.filename)}
                          className="text-zinc-400 hover:text-red-500"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-center text-zinc-500 py-8">Keine Backups vorhanden</p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Error Screenshots Tab */}
        <TabsContent value="errors">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white">Fehler-Screenshots</CardTitle>
            </CardHeader>
            <CardContent>
              {screenshots.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {screenshots.map((screenshot) => (
                    <div key={screenshot.filename} className="bg-zinc-800/50 rounded-sm overflow-hidden">
                      <a href={`${API}${screenshot.path}`} target="_blank" rel="noopener noreferrer">
                        <img 
                          src={`${API}${screenshot.path}`} 
                          alt={screenshot.filename}
                          className="w-full h-32 object-cover hover:opacity-80 transition-opacity"
                        />
                      </a>
                      <div className="p-3">
                        <p className="text-xs text-zinc-400 truncate">{screenshot.filename}</p>
                        <p className="text-xs text-zinc-500">
                          {new Date(screenshot.created_at).toLocaleString('de-DE')}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center text-zinc-500 py-8">Keine Fehler-Screenshots vorhanden</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
