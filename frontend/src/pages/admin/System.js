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
  RotateCcw,
  CheckCircle,
  XCircle,
  ArrowUpCircle,
  Terminal,
  Archive,
  Info,
  Cpu,
  FileDown,
  History,
  ShieldCheck,
  AlertTriangle,
  ExternalLink,
  Package,
  ChevronDown,
  ChevronRight
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
  if (!bytes || bytes === 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(isoStr) {
  if (!isoStr) return '-';
  return new Date(isoStr).toLocaleString('de-DE');
}

function ChangelogBlock({ body }) {
  const [expanded, setExpanded] = useState(false);
  if (!body) return null;
  const lines = body.split('\n');
  const preview = lines.slice(0, 5).join('\n');
  const hasMore = lines.length > 5;

  return (
    <div className="mt-2">
      <pre className="text-xs text-zinc-400 whitespace-pre-wrap font-sans leading-relaxed">
        {expanded ? body : preview}
      </pre>
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs text-amber-500 hover:text-amber-400 mt-1 flex items-center gap-1"
        >
          {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
          {expanded ? 'Weniger' : `Mehr anzeigen (${lines.length} Zeilen)`}
        </button>
      )}
    </div>
  );
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
  const [checkingUpdates, setCheckingUpdates] = useState(false);
  const [githubReleases, setGithubReleases] = useState(null);
  const [preparingUpdate, setPreparingUpdate] = useState(false);
  const [updatePrep, setUpdatePrep] = useState(null);
  const [downloading, setDownloading] = useState(null);
  const [downloadProgress, setDownloadProgress] = useState(null);
  const [downloadedAssets, setDownloadedAssets] = useState([]);
  const [updateHistory, setUpdateHistory] = useState([]);
  const [expandedRelease, setExpandedRelease] = useState(null);
  const [installing, setInstalling] = useState(false);
  const [rollbackInProgress, setRollbackInProgress] = useState(false);
  const [appBackups, setAppBackups] = useState([]);
  const [updateResult, setUpdateResult] = useState(null);
  const [creatingAppBackup, setCreatingAppBackup] = useState(false);
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
      setUpdateHistory(updatesRes.data.update_history || []);
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

  // Poll download progress
  useEffect(() => {
    if (!downloading) return;
    const iv = setInterval(async () => {
      try {
        const res = await axios.get(`${API}/updates/download/${downloading}`, { headers });
        setDownloadProgress(res.data);
        if (res.data.status === 'completed' || res.data.status === 'failed') {
          setDownloading(null);
          if (res.data.status === 'completed') {
            toast.success(`Download abgeschlossen: ${res.data.asset_name}`);
            fetchDownloads();
          } else {
            toast.error(`Download fehlgeschlagen: ${res.data.error}`);
          }
        }
      } catch {
        setDownloading(null);
      }
    }, 1500);
    return () => clearInterval(iv);
  }, [downloading]);

  const fetchDownloads = async () => {
    try {
      const res = await axios.get(`${API}/updates/downloads`, { headers });
      setDownloadedAssets(res.data.assets || []);
    } catch { /* ignore */ }
  };

  const fetchAppBackups = async () => {
    try {
      const res = await axios.get(`${API}/updates/backups`, { headers });
      setAppBackups(res.data.backups || []);
    } catch { /* ignore */ }
  };

  const fetchUpdateResult = async () => {
    try {
      const res = await axios.get(`${API}/updates/result`, { headers });
      if (res.data.has_result) {
        setUpdateResult(res.data.result);
      }
    } catch { /* ignore */ }
  };

  useEffect(() => { fetchDownloads(); fetchAppBackups(); fetchUpdateResult(); }, []);

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

  const handleCheckUpdates = async () => {
    setCheckingUpdates(true);
    try {
      const res = await axios.get(`${API}/updates/check`, { headers });
      setGithubReleases(res.data);
      if (res.data.update_available) {
        toast.success(`Neue Version v${res.data.latest_version} verfuegbar!`);
      } else if (!res.data.message) {
        toast.info('Keine neuen Updates verfuegbar');
      }
    } catch {
      toast.error('Update-Pruefung fehlgeschlagen');
    } finally {
      setCheckingUpdates(false);
    }
  };

  const handlePrepareUpdate = async (version) => {
    setPreparingUpdate(true);
    try {
      const res = await axios.post(`${API}/updates/prepare?target_version=${version}`, {}, { headers });
      setUpdatePrep(res.data);
      if (res.data.backup_created) {
        toast.success('Backup erstellt. Update-Anleitung bereit.');
      }
    } catch {
      toast.error('Update-Vorbereitung fehlgeschlagen');
    } finally {
      setPreparingUpdate(false);
    }
  };

  const handleDownloadAsset = async (url, name) => {
    try {
      const res = await axios.post(
        `${API}/updates/download?asset_url=${encodeURIComponent(url)}&asset_name=${encodeURIComponent(name)}`,
        {},
        { headers }
      );
      setDownloading(res.data.download_id);
      setDownloadProgress({ status: 'downloading', percent: 0, asset_name: name });
      toast.info(`Download gestartet: ${name}`);
    } catch {
      toast.error('Download konnte nicht gestartet werden');
    }
  };

  const handleDeleteDownload = async (filename) => {
    if (!window.confirm(`"${filename}" wirklich loeschen?`)) return;
    try {
      await axios.delete(`${API}/updates/downloads/${encodeURIComponent(filename)}`, { headers });
      toast.success('Datei geloescht');
      fetchDownloads();
    } catch {
      toast.error('Loeschen fehlgeschlagen');
    }
  };

  const handleInstallUpdate = async (assetFilename, targetVersion) => {
    if (!window.confirm(
      `Update auf v${targetVersion} installieren?\n\n` +
      `Das System erstellt ein Backup, stoppt alle Dienste, ersetzt die Dateien und startet neu.\n` +
      `Laufzeitdaten (Datenbank, Chrome-Profil, .env) werden NICHT ueberschrieben.`
    )) return;
    setInstalling(true);
    try {
      const res = await axios.post(
        `${API}/updates/install?asset_filename=${encodeURIComponent(assetFilename)}&target_version=${encodeURIComponent(targetVersion)}`,
        {},
        { headers }
      );
      toast.success(res.data.message || 'Update gestartet');
      // Poll for result after a delay
      setTimeout(() => {
        const pollInterval = setInterval(async () => {
          try {
            const r = await axios.get(`${API}/updates/result`, { headers });
            if (r.data.has_result) {
              setUpdateResult(r.data.result);
              clearInterval(pollInterval);
              setInstalling(false);
            }
          } catch {
            // Backend might be restarting — keep polling
          }
        }, 5000);
        // Stop polling after 3 minutes
        setTimeout(() => { clearInterval(pollInterval); setInstalling(false); }, 180000);
      }, 10000);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Installation fehlgeschlagen');
      setInstalling(false);
    }
  };

  const handleRollback = async (backupFilename) => {
    if (!window.confirm(
      `Rollback mit Backup "${backupFilename}" durchfuehren?\n\n` +
      `Das System stoppt alle Dienste, stellt die Dateien wieder her und startet neu.`
    )) return;
    setRollbackInProgress(true);
    try {
      const res = await axios.post(
        `${API}/updates/rollback?backup_filename=${encodeURIComponent(backupFilename)}`,
        {},
        { headers }
      );
      toast.success(res.data.message || 'Rollback gestartet');
      setTimeout(() => {
        const pollInterval = setInterval(async () => {
          try {
            const r = await axios.get(`${API}/updates/result`, { headers });
            if (r.data.has_result) {
              setUpdateResult(r.data.result);
              clearInterval(pollInterval);
              setRollbackInProgress(false);
            }
          } catch { /* Backend restarting */ }
        }, 5000);
        setTimeout(() => { clearInterval(pollInterval); setRollbackInProgress(false); }, 180000);
      }, 10000);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Rollback fehlgeschlagen');
      setRollbackInProgress(false);
    }
  };

  const handleCreateAppBackup = async () => {
    setCreatingAppBackup(true);
    try {
      const res = await axios.post(`${API}/updates/backups/create`, {}, { headers });
      toast.success(`App-Backup erstellt: ${res.data.filename}`);
      fetchAppBackups();
    } catch {
      toast.error('App-Backup fehlgeschlagen');
    } finally {
      setCreatingAppBackup(false);
    }
  };

  const handleDeleteAppBackup = async (filename) => {
    if (!window.confirm(`App-Backup "${filename}" wirklich loeschen?`)) return;
    try {
      await axios.delete(`${API}/updates/backups/${encodeURIComponent(filename)}`, { headers });
      toast.success('Backup geloescht');
      fetchAppBackups();
    } catch {
      toast.error('Loeschen fehlgeschlagen');
    }
  };

  const handleClearUpdateResult = async () => {
    try {
      await axios.post(`${API}/updates/result/clear`, {}, { headers });
      setUpdateResult(null);
      fetchAll();
    } catch { /* ignore */ }
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
          <p className="text-zinc-500">Verwaltung, Backups & Updates</p>
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
      <Tabs defaultValue="updates" className="space-y-6">
        <TabsList className="bg-zinc-900 border border-zinc-800 p-1">
          <TabsTrigger value="updates" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-updates">
            <ArrowUpCircle className="w-4 h-4 mr-2" /> Updates
          </TabsTrigger>
          <TabsTrigger value="backups" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-backups">
            <Database className="w-4 h-4 mr-2" /> Backups
          </TabsTrigger>
          <TabsTrigger value="logs" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-logs">
            <Terminal className="w-4 h-4 mr-2" /> Logs
          </TabsTrigger>
          <TabsTrigger value="details" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-details">
            <Server className="w-4 h-4 mr-2" /> Details
          </TabsTrigger>
        </TabsList>

        {/* ===== Updates Tab ===== */}
        <TabsContent value="updates">
          <div className="space-y-6">
            {/* Update Result Banner (from external updater) */}
            {updateResult && (
              <Card className={`border ${updateResult.success ? 'bg-emerald-500/10 border-emerald-500/30' : updateResult.rolled_back ? 'bg-amber-500/10 border-amber-500/30' : 'bg-red-500/10 border-red-500/30'}`} data-testid="update-result-banner">
                <CardContent className="p-5">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-start gap-3 flex-1">
                      {updateResult.success ? (
                        <CheckCircle className="w-6 h-6 text-emerald-500 mt-0.5 flex-shrink-0" />
                      ) : updateResult.rolled_back ? (
                        <RotateCcw className="w-6 h-6 text-amber-500 mt-0.5 flex-shrink-0" />
                      ) : (
                        <XCircle className="w-6 h-6 text-red-500 mt-0.5 flex-shrink-0" />
                      )}
                      <div>
                        <p className={`font-medium text-lg ${updateResult.success ? 'text-emerald-400' : updateResult.rolled_back ? 'text-amber-400' : 'text-red-400'}`}>
                          {updateResult.action === 'install_update'
                            ? updateResult.success
                              ? `Update auf v${updateResult.target_version} erfolgreich`
                              : updateResult.rolled_back
                                ? `Update fehlgeschlagen — Rollback auf v${updateResult.previous_version} durchgefuehrt`
                                : `Update auf v${updateResult.target_version} fehlgeschlagen`
                            : updateResult.success
                              ? `Rollback erfolgreich (${updateResult.backup_used})`
                              : 'Rollback fehlgeschlagen'
                          }
                        </p>
                        {updateResult.error && (
                          <p className="text-sm text-red-400/80 mt-1">Fehler: {updateResult.error}</p>
                        )}
                        {updateResult.files_replaced > 0 && (
                          <p className="text-xs text-zinc-500 mt-1">{updateResult.files_replaced} Dateien ersetzt</p>
                        )}
                        {updateResult.completed_at && (
                          <p className="text-xs text-zinc-600 mt-1">{formatDate(updateResult.completed_at)}</p>
                        )}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleClearUpdateResult}
                      className="border-zinc-700 text-zinc-400 hover:text-white flex-shrink-0"
                      data-testid="clear-update-result-btn"
                    >
                      Bestaetigen
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Installing/Rollback Progress */}
            {(installing || rollbackInProgress) && (
              <Card className="bg-blue-500/10 border border-blue-500/30" data-testid="update-progress-banner">
                <CardContent className="p-5">
                  <div className="flex items-center gap-3">
                    <RefreshCw className="w-6 h-6 text-blue-400 animate-spin flex-shrink-0" />
                    <div>
                      <p className="text-blue-400 font-medium text-lg">
                        {installing ? 'Update wird installiert...' : 'Rollback wird durchgefuehrt...'}
                      </p>
                      <p className="text-sm text-zinc-400 mt-1">
                        Dienste werden gestoppt, Dateien ersetzt, und neu gestartet.
                        Diese Seite laedt automatisch neu wenn der Vorgang abgeschlossen ist.
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}
            {/* Current Version & Check */}
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-white flex items-center gap-2">
                    <ArrowUpCircle className="w-5 h-5 text-amber-500" /> Updates & Versionen
                  </CardTitle>
                  <Button
                    onClick={handleCheckUpdates}
                    disabled={checkingUpdates}
                    className="bg-amber-500 hover:bg-amber-400 text-black"
                    data-testid="check-updates-btn"
                  >
                    <RefreshCw className={`w-4 h-4 mr-2 ${checkingUpdates ? 'animate-spin' : ''}`} />
                    {checkingUpdates ? 'Pruefe...' : 'Auf Updates pruefen'}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Current Version Banner */}
                <div className="p-4 bg-zinc-800/50 rounded-sm border border-zinc-700/30">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <CheckCircle className="w-6 h-6 text-emerald-500" />
                      <div>
                        <p className="text-xs text-zinc-500 uppercase tracking-wider">Installierte Version</p>
                        <span className="text-2xl font-mono text-white font-bold" data-testid="update-current-version">
                          v{updates?.current_version || '1.0.0'}
                        </span>
                        <p className="text-xs text-emerald-500/80 mt-1 font-mono" data-testid="update-build-tag">
                          Build: production-hardened | Update-System aktiv
                        </p>
                      </div>
                    </div>
                    {updates?.github_repo && (
                      <div className="text-right">
                        <p className="text-xs text-zinc-500">Repository</p>
                        <a
                          href={`https://github.com/${updates.github_repo}`}
                          target="_blank"
                          rel="noreferrer"
                          className="text-sm text-amber-500 hover:text-amber-400 flex items-center gap-1"
                        >
                          {updates.github_repo} <ExternalLink className="w-3 h-3" />
                        </a>
                      </div>
                    )}
                  </div>
                </div>

                {/* GitHub Not Configured */}
                {githubReleases && !githubReleases.configured && (
                  <div className="p-4 bg-zinc-800/30 border border-zinc-700/50 rounded-sm">
                    <p className="text-sm text-zinc-400 mb-2 flex items-center gap-2">
                      <Info className="w-4 h-4" /> GitHub-Repository konfigurieren
                    </p>
                    <p className="text-xs text-zinc-500">
                      Setze <code className="text-amber-400 bg-zinc-800 px-1 rounded">GITHUB_REPO=owner/darts-kiosk</code> in der .env Datei.
                      Optional: <code className="text-amber-400 bg-zinc-800 px-1 rounded">GITHUB_TOKEN</code> fuer private Repos und hoehere Rate-Limits.
                    </p>
                  </div>
                )}

                {/* API Error/Message */}
                {githubReleases?.message && (
                  <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-sm flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                    <p className="text-sm text-amber-400">{githubReleases.message}</p>
                  </div>
                )}

                {/* New Version Available */}
                {githubReleases?.update_available && (
                  <div className="p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-sm" data-testid="update-available-banner">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <p className="text-emerald-400 font-medium flex items-center gap-2 text-lg">
                          <ArrowUpCircle className="w-5 h-5" />
                          v{githubReleases.latest_version} verfuegbar
                        </p>
                        <p className="text-sm text-zinc-400 mt-1">{githubReleases.latest_name}</p>
                        <ChangelogBlock body={githubReleases.latest_body} />
                      </div>
                      <Button
                        onClick={() => handlePrepareUpdate(githubReleases.latest_version)}
                        disabled={preparingUpdate}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white flex-shrink-0"
                        data-testid="prepare-update-btn"
                      >
                        <ShieldCheck className="w-4 h-4 mr-2" />
                        {preparingUpdate ? 'Vorbereiten...' : 'Update vorbereiten'}
                      </Button>
                    </div>
                  </div>
                )}

                {/* Update Preparation Result */}
                {updatePrep && (
                  <div className="p-4 bg-zinc-800/30 border border-zinc-700/50 rounded-sm space-y-4" data-testid="update-prep-result">
                    <div className="flex items-center gap-2">
                      <Package className="w-5 h-5 text-amber-500" />
                      <p className="text-white font-medium">Update auf v{updatePrep.target_version}</p>
                    </div>

                    {/* Backup Status */}
                    {updatePrep.backup_created ? (
                      <div className="flex items-center gap-2 text-emerald-400 text-sm">
                        <CheckCircle className="w-4 h-4" />
                        Backup erstellt: <span className="font-mono text-xs">{updatePrep.backup_filename}</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2 text-amber-400 text-sm">
                        <AlertTriangle className="w-4 h-4" />
                        Kein automatisches Backup erstellt. Bitte manuell erstellen!
                      </div>
                    )}

                    {/* Changelog */}
                    {updatePrep.changelog && (
                      <div>
                        <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Changelog</p>
                        <ChangelogBlock body={updatePrep.changelog} />
                      </div>
                    )}

                    {/* Download Links */}
                    {updatePrep.download_links?.length > 0 && (
                      <div>
                        <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Verfuegbare Pakete</p>
                        <div className="space-y-2">
                          {updatePrep.download_links.map((dl, i) => (
                            <div key={i} className="flex items-center justify-between p-2 bg-zinc-800/50 rounded-sm">
                              <div className="flex items-center gap-2 min-w-0">
                                <FileDown className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                                <span className="text-sm text-zinc-300 truncate">{dl.label}</span>
                                <span className="text-xs text-zinc-600">{formatBytes(dl.size)}</span>
                              </div>
                              <div className="flex gap-2 flex-shrink-0">
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => handleDownloadAsset(dl.url, dl.name)}
                                  disabled={!!downloading}
                                  className="border-zinc-700 text-zinc-400 hover:text-white text-xs"
                                  data-testid={`download-asset-${i}`}
                                >
                                  <Download className="w-3 h-3 mr-1" /> Server
                                </Button>
                                {!dl.url.includes('api.github.com') && (
                                  <a
                                    href={dl.url}
                                    target="_blank"
                                    rel="noreferrer"
                                    className="inline-flex items-center gap-1 px-2 py-1 text-xs rounded border border-zinc-700 text-zinc-400 hover:text-amber-500 hover:border-amber-500/50"
                                  >
                                    <ExternalLink className="w-3 h-3" /> Browser
                                  </a>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Download Progress */}
                    {downloadProgress && downloadProgress.status === 'downloading' && (
                      <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-sm" data-testid="download-progress">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-sm text-blue-400 flex items-center gap-2">
                            <RefreshCw className="w-3 h-3 animate-spin" />
                            {downloadProgress.asset_name}
                          </span>
                          <span className="text-sm text-blue-400 font-mono">{downloadProgress.percent}%</span>
                        </div>
                        <div className="w-full bg-zinc-800 rounded-full h-2">
                          <div
                            className="bg-blue-500 h-2 rounded-full transition-all duration-500"
                            style={{ width: `${downloadProgress.percent}%` }}
                          />
                        </div>
                        <p className="text-xs text-zinc-500 mt-1">
                          {formatBytes(downloadProgress.bytes_downloaded || 0)} / {formatBytes(downloadProgress.total_bytes || 0)}
                        </p>
                      </div>
                    )}

                    {/* Manual Steps */}
                    <div>
                      <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Update-Anleitung</p>
                      <div className="space-y-1">
                        {updatePrep.manual_steps?.map((step, i) => (
                          <p key={i} className="text-xs text-zinc-400 pl-2 border-l border-zinc-700">{step}</p>
                        ))}
                      </div>
                    </div>

                    {/* Rollback Info */}
                    {updatePrep.rollback_info && (
                      <div className="p-3 bg-zinc-800/30 border border-zinc-700/30 rounded-sm">
                        <p className="text-xs text-zinc-500 flex items-center gap-1 mb-1">
                          <RotateCcw className="w-3 h-3" /> Rollback-Info
                        </p>
                        <p className="text-xs text-zinc-400">{updatePrep.rollback_info.instruction}</p>
                        {updatePrep.rollback_info.backup_filename && (
                          <p className="text-xs text-zinc-500 mt-1 font-mono">{updatePrep.rollback_info.backup_filename}</p>
                        )}
                      </div>
                    )}

                    {updatePrep.release_url && (
                      <a
                        href={updatePrep.release_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-sm text-amber-500 hover:text-amber-400"
                      >
                        <ExternalLink className="w-3 h-3" /> GitHub Release-Seite oeffnen
                      </a>
                    )}
                  </div>
                )}

                {/* Downloaded Assets */}
                {downloadedAssets.length > 0 && (
                  <div>
                    <p className="text-sm text-zinc-400 mb-3 uppercase tracking-wider flex items-center gap-2">
                      <FileDown className="w-4 h-4" /> Heruntergeladene Pakete
                    </p>
                    <div className="space-y-2">
                      {downloadedAssets.map((a) => {
                        // Extract version from filename: darts-kiosk-v1.7.0-windows.zip → 1.7.0
                        const vMatch = a.name?.match(/v?([\d.]+)/);
                        const assetVersion = vMatch ? vMatch[1] : '';
                        return (
                          <div key={a.name} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm" data-testid={`downloaded-${a.name}`}>
                            <div className="flex items-center gap-2 min-w-0">
                              <Package className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                              <span className="text-sm text-white font-mono truncate">{a.name}</span>
                              <span className="text-xs text-zinc-500">{formatBytes(a.size)}</span>
                            </div>
                            <div className="flex gap-2 items-center">
                              <span className="text-xs text-zinc-600">{formatDate(a.downloaded_at)}</span>
                              {assetVersion && a.name?.includes('windows') && (
                                <Button
                                  size="sm"
                                  onClick={() => handleInstallUpdate(a.name, assetVersion)}
                                  disabled={installing || rollbackInProgress}
                                  className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
                                  data-testid={`install-btn-${a.name}`}
                                >
                                  <ArrowUpCircle className="w-3 h-3 mr-1" />
                                  {installing ? 'Installiert...' : `v${assetVersion} installieren`}
                                </Button>
                              )}
                              <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleDeleteDownload(a.name)}
                                className="text-zinc-400 hover:text-red-500 h-6 w-6"
                              >
                                <Trash2 className="w-3 h-3" />
                              </Button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Release List */}
                {githubReleases?.releases?.length > 0 && (
                  <div>
                    <p className="text-sm text-zinc-400 mb-3 uppercase tracking-wider">Alle Releases</p>
                    <div className="space-y-2">
                      {githubReleases.releases.map((r) => (
                        <div key={r.tag} data-testid={`release-${r.tag}`}>
                          <div
                            className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm cursor-pointer hover:bg-zinc-800/70 transition-colors"
                            onClick={() => setExpandedRelease(expandedRelease === r.tag ? null : r.tag)}
                          >
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                              {r.is_current
                                ? <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                                : r.is_newer
                                  ? <ArrowUpCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                                  : <Clock className="w-4 h-4 text-zinc-600 flex-shrink-0" />
                              }
                              <span className="text-white font-mono">{r.tag}</span>
                              <span className="text-xs text-zinc-500 truncate">{r.name}</span>
                              {r.is_prerelease && <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">pre</span>}
                              {r.is_current && <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400">aktiv</span>}
                              {r.published_at && <span className="text-xs text-zinc-600 ml-auto">{formatDate(r.published_at)}</span>}
                            </div>
                            <div className="flex items-center gap-2 ml-2">
                              {r.is_newer && !r.is_prerelease && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={(e) => { e.stopPropagation(); handlePrepareUpdate(r.version); }}
                                  disabled={preparingUpdate}
                                  className="border-zinc-700 text-zinc-400 hover:text-white text-xs"
                                >
                                  Update
                                </Button>
                              )}
                              {expandedRelease === r.tag
                                ? <ChevronDown className="w-4 h-4 text-zinc-500" />
                                : <ChevronRight className="w-4 h-4 text-zinc-500" />
                              }
                            </div>
                          </div>
                          {expandedRelease === r.tag && (
                            <div className="ml-4 p-3 border-l-2 border-zinc-700 mt-1 mb-2">
                              <ChangelogBlock body={r.body} />
                              {r.assets?.length > 0 && (
                                <div className="mt-2 space-y-1">
                                  <p className="text-xs text-zinc-500 uppercase">Assets ({r.assets.length})</p>
                                  {r.assets.map((a, i) => (
                                    <div key={i} className="flex items-center gap-2 text-xs">
                                      <FileDown className="w-3 h-3 text-zinc-600" />
                                      <a href={a.download_url} target="_blank" rel="noreferrer" className="text-amber-500 hover:text-amber-400">
                                        {a.name}
                                      </a>
                                      <span className="text-zinc-600">{formatBytes(a.size)}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                              {r.html_url && (
                                <a href={r.html_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-amber-500 mt-2">
                                  <ExternalLink className="w-3 h-3" /> GitHub
                                </a>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {githubReleases?.last_check && (
                  <p className="text-xs text-zinc-600">
                    Zuletzt geprueft: {formatDate(githubReleases.last_check)}
                  </p>
                )}
              </CardContent>
            </Card>

            {/* Update History */}
            {updateHistory.length > 0 && (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardHeader>
                  <CardTitle className="text-white flex items-center gap-2">
                    <History className="w-5 h-5 text-amber-500" /> Update-Verlauf
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-[300px] overflow-y-auto">
                    {[...updateHistory].reverse().map((h, i) => (
                      <div key={i} className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-sm text-sm" data-testid={`history-${i}`}>
                        {h.action === 'prepare_update' ? (
                          <ShieldCheck className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                        ) : h.action === 'download_started' ? (
                          <Download className="w-4 h-4 text-blue-500 flex-shrink-0" />
                        ) : h.action === 'install_started' ? (
                          <ArrowUpCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                        ) : h.action === 'rollback_started' ? (
                          <RotateCcw className="w-4 h-4 text-orange-500 flex-shrink-0" />
                        ) : h.action === 'app_backup_created' ? (
                          <Archive className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                        ) : h.action === 'update_result_acknowledged' ? (
                          <CheckCircle className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                        ) : (
                          <Clock className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                        )}
                        <div className="flex-1 min-w-0">
                          <span className="text-zinc-300">
                            {h.action === 'prepare_update' && `Update vorbereitet: v${h.target_version}`}
                            {h.action === 'download_started' && `Download: ${h.asset_name}`}
                            {h.action === 'install_started' && `Installation gestartet: v${h.target_version}`}
                            {h.action === 'rollback_started' && `Rollback gestartet: ${h.backup_filename}`}
                            {h.action === 'app_backup_created' && `App-Backup: ${h.filename}`}
                            {h.action === 'update_result_acknowledged' && `Update ${h.success ? 'erfolgreich' : 'fehlgeschlagen'}: v${h.target_version || '?'}`}
                            {!['prepare_update', 'download_started', 'install_started', 'rollback_started', 'app_backup_created', 'update_result_acknowledged'].includes(h.action) && h.action}
                          </span>
                          {h.backup_created && (
                            <span className="text-xs text-emerald-500 ml-2">+ Backup</span>
                          )}
                        </div>
                        <span className="text-xs text-zinc-600 flex-shrink-0">{formatDate(h.timestamp)}</span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </TabsContent>

        {/* ===== Backups Tab ===== */}
        <TabsContent value="backups">
          <div className="space-y-6">
            {/* App Backups (for Updates & Rollback) */}
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-white flex items-center gap-2">
                    <Archive className="w-5 h-5 text-amber-500" /> Anwendungs-Backups
                  </CardTitle>
                  <Button
                    onClick={handleCreateAppBackup}
                    disabled={creatingAppBackup}
                    className="bg-amber-500 hover:bg-amber-400 text-black"
                    data-testid="app-backup-create-btn"
                  >
                    {creatingAppBackup ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Archive className="w-4 h-4 mr-2" />}
                    App-Backup erstellen
                  </Button>
                </div>
                <p className="text-xs text-zinc-500 mt-1">
                  Vollstaendiges Backup von Backend, Frontend, Scripts und VERSION. Fuer Updates und Rollback.
                </p>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                  {appBackups.length > 0 ? (
                    appBackups.map((b) => (
                      <div key={b.filename} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm group" data-testid={`app-backup-${b.filename}`}>
                        <div className="min-w-0 flex-1">
                          <p className="text-white font-mono text-sm truncate">{b.filename}</p>
                          <p className="text-xs text-zinc-500">
                            {formatDate(b.created_at)} | {b.size_mb} MB
                          </p>
                        </div>
                        <div className="flex gap-2 ml-3">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleRollback(b.filename)}
                            disabled={rollbackInProgress || installing}
                            className="border-zinc-700 text-zinc-400 hover:text-amber-500 hover:border-amber-500/50 text-xs"
                            data-testid={`rollback-btn-${b.filename}`}
                          >
                            <RotateCcw className="w-3 h-3 mr-1" />
                            {rollbackInProgress ? 'Rollback...' : 'Rollback'}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteAppBackup(b.filename)}
                            className="text-zinc-400 hover:text-red-500 h-8 w-8"
                            title="Loeschen"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="text-center text-zinc-500 py-6">Keine App-Backups vorhanden</p>
                  )}
                </div>
              </CardContent>
            </Card>

            {/* DB Backups */}
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
          </div>
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
