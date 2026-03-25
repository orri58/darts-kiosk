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
  RotateCcw,
  HardDrive
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminHealth() {
  const { token } = useAuth();
  const { t } = useI18n();
  const [health, setHealth] = useState(null);
  const [backups, setBackups] = useState(null);
  const [screenshots, setScreenshots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const fetchHealth = useCallback(async () => {
    try {
      const [healthRes, backupsRes, screenshotsRes] = await Promise.all([
        axios.get(`${API}/health/detailed`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/backups`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/health/screenshots`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setHealth(healthRes.data);
      setBackups(backupsRes.data);
      setScreenshots(screenshotsRes.data);
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
    if (!window.confirm(`Backup "${filename}" wirklich löschen?`)) return;
    
    try {
      await axios.delete(`${API}/backups/${filename}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Backup gelöscht');
      fetchHealth();
    } catch (error) {
      toast.error('Löschen fehlgeschlagen');
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
          <h1 className="text-2xl font-heading uppercase tracking-wider text-white">{t('system_health')}</h1>
          <p className="text-zinc-500">Überwachung und Backups</p>
        </div>
        <Button
          onClick={fetchHealth}
          variant="outline"
          className="border-zinc-700 text-zinc-400 hover:text-white"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Aktualisieren
        </Button>
      </div>

      {/* Status Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        {/* Overall Status */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              {getStatusIcon(health?.status)}
              <div>
                <p className="text-sm text-zinc-500 uppercase">System Status</p>
                <p className={`text-2xl font-bold uppercase ${getStatusColor(health?.status)}`}>
                  {health?.status || 'Unknown'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Uptime */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <Clock className="w-6 h-6 text-blue-500" />
              <div>
                <p className="text-sm text-zinc-500 uppercase">Uptime</p>
                <p className="text-2xl font-mono font-bold text-white">
                  {formatUptime(health?.uptime_seconds || 0)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Automation Success Rate */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <Activity className="w-6 h-6 text-amber-500" />
              <div>
                <p className="text-sm text-zinc-500 uppercase">Automation</p>
                <p className="text-2xl font-mono font-bold text-white">
                  {health?.automation_metrics?.success_rate?.toFixed(0) || 0}%
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Backups */}
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <HardDrive className="w-6 h-6 text-purple-500" />
              <div>
                <p className="text-sm text-zinc-500 uppercase">Backups</p>
                <p className="text-2xl font-mono font-bold text-white">
                  {backups?.stats?.total_backups || 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="services" className="space-y-6">
        <TabsList className="bg-zinc-900 border border-zinc-800 p-1">
          <TabsTrigger value="services" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Server className="w-4 h-4 mr-2" />
            Services
          </TabsTrigger>
          <TabsTrigger value="agents" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Wifi className="w-4 h-4 mr-2" />
            Agents
          </TabsTrigger>
          <TabsTrigger value="backups" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Database className="w-4 h-4 mr-2" />
            Backups
          </TabsTrigger>
          <TabsTrigger value="errors" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Camera className="w-4 h-4 mr-2" />
            Fehler-Screenshots
          </TabsTrigger>
        </TabsList>

        {/* Services Tab */}
        <TabsContent value="services">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white">Hintergrund-Services</CardTitle>
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
