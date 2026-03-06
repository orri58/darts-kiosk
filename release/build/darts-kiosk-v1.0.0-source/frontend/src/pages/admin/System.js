import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Server,
  HardDrive,
  Clock,
  RefreshCw,
  Download,
  Trash2,
  Database,
  FileText,
  RotateCcw,
  CheckCircle,
  XCircle,
  ArrowUpCircle,
  Terminal,
  Archive,
  Info,
  Cpu
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function formatUptime(seconds) {
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

export default function AdminSystem() {
  const { token } = useAuth();
  const { t } = useI18n();
  const [sysInfo, setSysInfo] = useState(null);
  const [backups, setBackups] = useState(null);
  const [updates, setUpdates] = useState(null);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [restoring, setRestoring] = useState(null);
  const headers = { Authorization: `Bearer ${token}` };

  const fetchAll = useCallback(async () => {
    try {
      const [infoRes, backupsRes, updatesRes, logsRes] = await Promise.all([
        axios.get(`${API}/system/info`, { headers }),
        axios.get(`${API}/backups`, { headers }),
        axios.get(`${API}/updates/status`, { headers }),
        axios.get(`${API}/system/logs?lines=150`, { headers }),
      ]);
      setSysInfo(infoRes.data);
      setBackups(backupsRes.data);
      setUpdates(updatesRes.data);
      setLogs(logsRes.data.lines || []);
    } catch (err) {
      console.error('System fetch error', err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 30000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  const createBackup = async () => {
    setCreating(true);
    try {
      await axios.post(`${API}/backups/create`, {}, { headers });
      toast.success('Backup erfolgreich erstellt');
      fetchAll();
    } catch {
      toast.error('Backup fehlgeschlagen');
    } finally {
      setCreating(false);
    }
  };

  const downloadBackup = async (filename) => {
    try {
      const res = await axios.get(`${API}/backups/download/${filename}`, {
        headers,
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch {
      toast.error('Download fehlgeschlagen');
    }
  };

  const restoreBackup = async (filename) => {
    if (!window.confirm(`Datenbank aus "${filename}" wiederherstellen? Ein Sicherheits-Backup wird vorher erstellt.`)) return;
    setRestoring(filename);
    try {
      await axios.post(`${API}/backups/restore/${filename}`, {}, { headers });
      toast.success('Datenbank wiederhergestellt. Neustart empfohlen.');
    } catch {
      toast.error('Wiederherstellung fehlgeschlagen');
    } finally {
      setRestoring(null);
    }
  };

  const deleteBackup = async (filename) => {
    if (!window.confirm(`Backup "${filename}" wirklich loeschen?`)) return;
    try {
      await axios.delete(`${API}/backups/${filename}`, { headers });
      toast.success('Backup geloescht');
      fetchAll();
    } catch {
      toast.error('Loeschen fehlgeschlagen');
    }
  };

  const downloadLogBundle = async () => {
    try {
      const res = await axios.get(`${API}/system/logs/bundle`, {
        headers,
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = `darts-logs_${new Date().toISOString().slice(0,10)}.tar.gz`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success('Log-Bundle heruntergeladen');
    } catch {
      toast.error('Download fehlgeschlagen');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  const diskPercent = sysInfo?.disk?.usage_percent || 0;
  const diskColor = diskPercent > 90 ? 'text-red-400' : diskPercent > 70 ? 'text-amber-400' : 'text-emerald-400';

  return (
    <div data-testid="admin-system">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-heading uppercase tracking-wider text-white">{t('system')}</h1>
          <p className="text-zinc-500">Verwaltung, Backups & Logs</p>
        </div>
        <Button onClick={fetchAll} variant="outline" className="border-zinc-700 text-zinc-400 hover:text-white" data-testid="system-refresh-btn">
          <RefreshCw className="w-4 h-4 mr-2" /> Aktualisieren
        </Button>
      </div>

      {/* Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <Info className="w-6 h-6 text-amber-500 flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 uppercase tracking-wider">Version</p>
                <p className="text-lg font-mono font-bold text-white truncate" data-testid="system-version">
                  v{sysInfo?.version} <span className="text-xs text-zinc-500">({sysInfo?.image_tag})</span>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <Clock className="w-6 h-6 text-blue-500 flex-shrink-0" />
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-wider">Uptime</p>
                <p className="text-lg font-mono font-bold text-white" data-testid="system-uptime">
                  {formatUptime(sysInfo?.uptime_seconds || 0)}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <HardDrive className={`w-6 h-6 flex-shrink-0 ${diskColor}`} />
              <div>
                <p className="text-xs text-zinc-500 uppercase tracking-wider">Festplatte</p>
                <p className={`text-lg font-mono font-bold ${diskColor}`} data-testid="system-disk">
                  {diskPercent}%
                  <span className="text-xs text-zinc-500 ml-1">({sysInfo?.disk?.free_gb} GB frei)</span>
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-5">
            <div className="flex items-center gap-3">
              <Cpu className="w-6 h-6 text-purple-500 flex-shrink-0" />
              <div className="min-w-0">
                <p className="text-xs text-zinc-500 uppercase tracking-wider">Modus</p>
                <p className="text-lg font-bold text-white uppercase" data-testid="system-mode">
                  {sysInfo?.mode}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="backups" className="space-y-6">
        <TabsList className="bg-zinc-900 border border-zinc-800 p-1">
          <TabsTrigger value="backups" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-backups">
            <Database className="w-4 h-4 mr-2" /> Backups
          </TabsTrigger>
          <TabsTrigger value="updates" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-updates">
            <ArrowUpCircle className="w-4 h-4 mr-2" /> Updates
          </TabsTrigger>
          <TabsTrigger value="logs" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-logs">
            <Terminal className="w-4 h-4 mr-2" /> Logs
          </TabsTrigger>
          <TabsTrigger value="details" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-details">
            <Server className="w-4 h-4 mr-2" /> Details
          </TabsTrigger>
        </TabsList>

        {/* ===== Backups Tab ===== */}
        <TabsContent value="backups">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-white flex items-center gap-2">
                  <Database className="w-5 h-5 text-amber-500" /> Datenbank-Backups
                </CardTitle>
                <Button onClick={createBackup} disabled={creating} className="bg-amber-500 hover:bg-amber-400 text-black" data-testid="backup-create-btn">
                  {creating ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Database className="w-4 h-4 mr-2" />}
                  Backup erstellen
                </Button>
              </div>
              {backups?.stats && (
                <p className="text-sm text-zinc-500 mt-1">
                  {backups.stats.total_backups} Backups | {backups.stats.total_size_mb} MB gesamt | Intervall: {backups.stats.backup_interval_hours}h
                </p>
              )}
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[420px] overflow-y-auto pr-1">
                {backups?.backups?.length > 0 ? (
                  backups.backups.map((b) => (
                    <div key={b.filename} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm group" data-testid={`backup-row-${b.filename}`}>
                      <div className="min-w-0 flex-1">
                        <p className="text-white font-mono text-sm truncate">{b.filename}</p>
                        <p className="text-xs text-zinc-500">
                          {new Date(b.created_at).toLocaleString('de-DE')} | {b.size_mb} MB
                          {b.compressed && <span className="ml-1 text-emerald-500">(gz)</span>}
                        </p>
                      </div>
                      <div className="flex gap-1 ml-3">
                        <Button variant="ghost" size="icon" onClick={() => downloadBackup(b.filename)} className="text-zinc-400 hover:text-amber-500" title="Herunterladen">
                          <Download className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => restoreBackup(b.filename)} disabled={restoring === b.filename} className="text-zinc-400 hover:text-blue-400" title="Wiederherstellen">
                          {restoring === b.filename ? <RefreshCw className="w-4 h-4 animate-spin" /> : <RotateCcw className="w-4 h-4" />}
                        </Button>
                        <Button variant="ghost" size="icon" onClick={() => deleteBackup(b.filename)} className="text-zinc-400 hover:text-red-500" title="Loeschen">
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

        {/* ===== Updates Tab ===== */}
        <TabsContent value="updates">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <ArrowUpCircle className="w-5 h-5 text-amber-500" /> Updates & Versionen
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Current Version */}
              <div className="p-4 bg-zinc-800/50 rounded-sm">
                <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Aktuelle Version</p>
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-emerald-500" />
                  <span className="text-xl font-mono text-white font-bold" data-testid="update-current-version">
                    v{updates?.current_version}
                  </span>
                  <span className="text-sm text-zinc-500">Image: {sysInfo?.image_tag}</span>
                </div>
              </div>

              {/* Available Versions */}
              <div>
                <p className="text-sm text-zinc-400 mb-3 uppercase tracking-wider">Verfuegbare Versionen</p>
                <div className="space-y-2">
                  {updates?.available_versions?.map((v) => (
                    <div key={v.version} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm" data-testid={`version-${v.version}`}>
                      <div className="flex items-center gap-3">
                        {v.is_current
                          ? <CheckCircle className="w-4 h-4 text-emerald-500" />
                          : <ArrowUpCircle className="w-4 h-4 text-zinc-500" />
                        }
                        <span className="text-white font-mono">v{v.version}</span>
                        <span className="text-xs px-2 py-0.5 rounded bg-zinc-700 text-zinc-300">{v.tag}</span>
                        {v.is_stable && <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400">stable</span>}
                        {v.is_current && <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">aktiv</span>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Update History */}
              {updates?.update_history?.length > 0 && (
                <div>
                  <p className="text-sm text-zinc-400 mb-3 uppercase tracking-wider">Update-Verlauf</p>
                  <div className="space-y-2">
                    {updates.update_history.map((h, i) => (
                      <div key={i} className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-sm text-sm">
                        {h.success ? <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0" /> : <XCircle className="w-4 h-4 text-red-500 flex-shrink-0" />}
                        <span className="text-zinc-400">{h.board_id}</span>
                        <span className="text-zinc-500">v{h.old_version} → v{h.new_version}</span>
                        <span className="text-xs text-zinc-600 ml-auto">{new Date(h.timestamp).toLocaleString('de-DE')}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Manual Update Instructions */}
              <div className="p-4 bg-zinc-800/30 border border-zinc-700/50 rounded-sm">
                <p className="text-sm text-zinc-400 mb-2 flex items-center gap-2">
                  <Info className="w-4 h-4" /> Manuelles Update (Docker)
                </p>
                <code className="block text-xs text-zinc-500 font-mono space-y-1">
                  <p>docker pull darts-kiosk:latest</p>
                  <p>cd /opt/darts-kiosk && docker compose down && docker compose up -d</p>
                </code>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===== Logs Tab ===== */}
        <TabsContent value="logs">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-white flex items-center gap-2">
                  <Terminal className="w-5 h-5 text-amber-500" /> Anwendungs-Logs
                </CardTitle>
                <div className="flex gap-2">
                  <Button onClick={fetchAll} variant="outline" size="sm" className="border-zinc-700 text-zinc-400 hover:text-white">
                    <RefreshCw className="w-3 h-3 mr-1" /> Refresh
                  </Button>
                  <Button onClick={downloadLogBundle} variant="outline" size="sm" className="border-zinc-700 text-zinc-400 hover:text-white" data-testid="logs-download-btn">
                    <Archive className="w-3 h-3 mr-1" /> Bundle
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div
                className="bg-zinc-950 border border-zinc-800 rounded-sm p-4 font-mono text-xs leading-relaxed max-h-[500px] overflow-y-auto"
                data-testid="log-viewer"
              >
                {logs.length > 0 ? (
                  logs.map((line, i) => {
                    const isError = line.includes('"ERROR"') || line.includes('"level": "ERROR"');
                    const isWarn = line.includes('"WARNING"') || line.includes('"level": "WARNING"');
                    return (
                      <div key={i} className={`whitespace-pre-wrap break-all ${isError ? 'text-red-400' : isWarn ? 'text-amber-400' : 'text-zinc-400'}`}>
                        {line}
                      </div>
                    );
                  })
                ) : (
                  <p className="text-zinc-600">Keine Logs vorhanden</p>
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===== Details Tab ===== */}
        <TabsContent value="details">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Server className="w-5 h-5 text-amber-500" /> System-Details
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[
                  ['Hostname', sysInfo?.hostname],
                  ['Betriebssystem', sysInfo?.os],
                  ['Python', sysInfo?.python_version],
                  ['Modus', sysInfo?.mode],
                  ['Daten-Verzeichnis', sysInfo?.data_dir],
                  ['Datenbank', `${sysInfo?.database?.size_mb} MB`],
                  ['Festplatte Total', `${sysInfo?.disk?.total_gb} GB`],
                  ['Festplatte Belegt', `${sysInfo?.disk?.used_gb} GB (${sysInfo?.disk?.usage_percent}%)`],
                  ['Festplatte Frei', `${sysInfo?.disk?.free_gb} GB`],
                  ['Gestartet', sysInfo?.start_time ? new Date(sysInfo.start_time).toLocaleString('de-DE') : '-'],
                ].map(([label, value]) => (
                  <div key={label} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm">
                    <span className="text-sm text-zinc-400">{label}</span>
                    <span className="text-sm text-white font-mono">{value || '-'}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
