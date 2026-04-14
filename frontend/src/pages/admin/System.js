import { useState, useEffect, useCallback, useMemo } from 'react';
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
  ChevronRight,
  Monitor,
  Zap
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import {
  AdminPage,
  AdminSection,
  AdminStatCard,
  AdminStatsGrid,
  AdminStatusPill,
} from '../../components/admin/AdminShell';
import AgentTab from '../../components/admin/AgentTab';

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

function parseAssetVersion(name = '') {
  const versionMatch = name.match(/^darts-kiosk-v(.+?)-(windows|linux|source)(?:\.|$)/i);
  const fallbackMatch = name.match(/v?(\d+\.\d+\.\d+(?:[-+][\w.-]+)?)/i);
  return versionMatch?.[1] || fallbackMatch?.[1] || '';
}

function getPreferredWindowsAsset(release) {
  return (release?.assets || []).find((asset) => /-windows\.zip$/i.test(asset.name || '')) || null;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
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
  const [supportSnapshot, setSupportSnapshot] = useState(null);
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
  const [installingTarget, setInstallingTarget] = useState('');
  const [rollbackInProgress, setRollbackInProgress] = useState(false);
  const [appBackups, setAppBackups] = useState([]);
  const [updateResult, setUpdateResult] = useState(null);
  const [creatingAppBackup, setCreatingAppBackup] = useState(false);
  const [agentStatus, setAgentStatus] = useState(null);
  const headers = useMemo(() => ({ Authorization: `Bearer ${token}` }), [token]);

  const fetchAll = useCallback(async () => {
    try {
      const [infoRes, backupsRes, updatesRes, supportRes] = await Promise.allSettled([
        axios.get(`${API}/system/info`, { headers }),
        axios.get(`${API}/backups`, { headers }),
        axios.get(`${API}/updates/status`, { headers }),
        axios.get(`${API}/system/support-snapshot`, { headers }),
      ]);

      if (infoRes.status === 'fulfilled') {
        setSysInfo(infoRes.value.data);
      }
      if (backupsRes.status === 'fulfilled') {
        setBackups(backupsRes.value.data);
      }
      if (updatesRes.status === 'fulfilled') {
        setUpdates(updatesRes.value.data);
        setUpdateHistory(updatesRes.value.data.update_history || []);
      }
      if (supportRes.status === 'fulfilled') {
        setSupportSnapshot(supportRes.value.data);
        setLogs(supportRes.value.data?.logs?.tail_lines || []);
        setAgentStatus(supportRes.value.data?.agent_status || null);
      }
    } catch (err) {
      console.error('System fetch error', err);
    } finally {
      setLoading(false);
    }
  }, [headers]);

  useEffect(() => {
    fetchAll();
    const iv = setInterval(fetchAll, 30000);
    return () => clearInterval(iv);
  }, [fetchAll]);

  const fetchDownloads = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/updates/downloads`, { headers });
      setDownloadedAssets(res.data.assets || []);
    } catch { /* ignore */ }
  }, [headers]);

  const fetchAppBackups = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/updates/backups`, { headers });
      setAppBackups(res.data.backups || []);
    } catch { /* ignore */ }
  }, [headers]);

  const fetchUpdateResult = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/updates/result`, { headers });
      if (res.data.has_result) {
        setUpdateResult(res.data.result);
      }
    } catch { /* ignore */ }
  }, [headers]);

  useEffect(() => {
    fetchDownloads();
    fetchAppBackups();
    fetchUpdateResult();
  }, [fetchDownloads, fetchAppBackups, fetchUpdateResult]);

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
  }, [downloading, headers, fetchDownloads]);

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

  const beginUpdateResultPolling = useCallback(() => {
    setTimeout(() => {
      const pollInterval = setInterval(async () => {
        try {
          const r = await axios.get(`${API}/updates/result`, { headers });
          if (r.data.has_result) {
            setUpdateResult(r.data.result);
            clearInterval(pollInterval);
            setInstalling(false);
            setInstallingTarget('');
          }
        } catch {
          // Backend might be restarting — keep polling
        }
      }, 5000);
      setTimeout(() => {
        clearInterval(pollInterval);
        setInstalling(false);
        setInstallingTarget('');
      }, 180000);
    }, 10000);
  }, [headers]);

  const handleInstallUpdate = async (assetFilename, targetVersion) => {
    if (!window.confirm(
      `Update auf v${targetVersion} installieren?\n\n` +
      `Das System erstellt ein Backup, stoppt alle Dienste, ersetzt die Dateien und startet neu.\n` +
      `Laufzeitdaten (Datenbank, Chrome-Profil, .env) werden NICHT ueberschrieben.`
    )) return;
    setInstalling(true);
    setInstallingTarget(targetVersion);
    try {
      const res = await axios.post(
        `${API}/updates/install?asset_filename=${encodeURIComponent(assetFilename)}&target_version=${encodeURIComponent(targetVersion)}`,
        {},
        { headers }
      );
      toast.success(res.data.message || 'Update gestartet');
      beginUpdateResultPolling();
    } catch (err) {
      const detail = err.response?.data?.detail || 'Installation fehlgeschlagen';
      toast.error(detail);
      setInstalling(false);
      setInstallingTarget('');
    }
  };

  const handleDirectInstallRelease = async (release) => {
    const windowsAsset = getPreferredWindowsAsset(release);
    if (!windowsAsset) {
      toast.error('Kein installierbares Windows-Paket in diesem Release gefunden');
      return;
    }

    if (!window.confirm(
      `Update auf v${release.version} direkt installieren?\n\n` +
      `Ablauf: Backup -> Download -> Validierung -> Installation -> Neustart.\n` +
      `Datenbank, Chrome-Profile und .env bleiben erhalten.`
    )) return;

    setInstalling(true);
    setInstallingTarget(release.version);

    try {
      const prepRes = await axios.post(`${API}/updates/prepare?target_version=${encodeURIComponent(release.version)}`, {}, { headers });
      setUpdatePrep(prepRes.data);

      const dlRes = await axios.post(
        `${API}/updates/download?asset_url=${encodeURIComponent(windowsAsset.download_url || windowsAsset.api_url)}&asset_name=${encodeURIComponent(windowsAsset.name)}`,
        {},
        { headers }
      );

      const downloadId = dlRes.data.download_id;
      setDownloading(downloadId);
      setDownloadProgress({ status: 'downloading', percent: 0, asset_name: windowsAsset.name });

      let finalProgress = null;
      for (let attempt = 0; attempt < 240; attempt += 1) {
        const progressRes = await axios.get(`${API}/updates/download/${downloadId}`, { headers });
        finalProgress = progressRes.data;
        setDownloadProgress(finalProgress);
        if (finalProgress.status === 'completed') break;
        if (finalProgress.status === 'failed') {
          throw new Error(finalProgress.error || 'Download fehlgeschlagen');
        }
        await wait(1500);
      }

      if (!finalProgress || finalProgress.status !== 'completed') {
        throw new Error('Download-Timeout');
      }

      setDownloading(null);
      await fetchDownloads();

      const installRes = await axios.post(
        `${API}/updates/install?asset_filename=${encodeURIComponent(windowsAsset.name)}&target_version=${encodeURIComponent(release.version)}`,
        {},
        { headers }
      );

      toast.success(installRes.data.message || `Update v${release.version} gestartet`);
      beginUpdateResultPolling();
    } catch (err) {
      toast.error(err.response?.data?.detail || err.message || 'Direkt-Installation fehlgeschlagen');
      setInstalling(false);
      setInstallingTarget('');
      setDownloading(null);
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
      const detail = err.response?.data?.detail || 'Rollback fehlgeschlagen';
      toast.error(detail);
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
      a.download = `darts-support_${new Date().toISOString().slice(0,10)}.tar.gz`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast.success('Support-Bundle heruntergeladen');
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
    <AdminPage
      eyebrow="System & Updates"
      title={t('system')}
      description="Updates installieren, Backups verwalten und den Board-PC im Griff behalten — ohne Wartungsroman in der Oberfläche."
      actions={
        <div className="flex flex-wrap items-center gap-2">
          <AdminStatusPill tone="blue">
            <Cpu className="w-3 h-3" /> {sysInfo?.mode || 'MASTER'}
          </AdminStatusPill>
          <Button onClick={fetchAll} variant="outline" className="border-zinc-700 text-zinc-300 hover:text-white" data-testid="system-refresh-btn">
            <RefreshCw className="w-4 h-4 mr-2" /> Aktualisieren
          </Button>
        </div>
      }
    >
      <AdminStatsGrid>
        <AdminStatCard
          icon={Info}
          label="Installierte Version"
          value={`v${sysInfo?.version || '–'}`}
          hint={sysInfo?.image_tag ? `Image tag: ${sysInfo.image_tag}` : 'Lokaler Build-Stand'}
          tone="amber"
          className="[&_p.truncate]:text-left"
        />
        <AdminStatCard
          icon={Clock}
          label="Uptime"
          value={formatUptime(sysInfo?.uptime_seconds || 0)}
          hint={sysInfo?.start_time ? `Seit ${formatDate(sysInfo.start_time)}` : 'Seit letztem Start'}
          tone="blue"
        />
        <AdminStatCard
          icon={HardDrive}
          label="Festplattennutzung"
          value={`${diskPercent}%`}
          hint={`${sysInfo?.disk?.free_gb ?? 0} GB frei im Datenlaufwerk`}
          tone={diskPercent > 90 ? 'red' : diskPercent > 70 ? 'amber' : 'emerald'}
        />
        <AdminStatCard
          icon={Archive}
          label="Recovery-Artefakte"
          value={downloadedAssets.length + appBackups.length}
          hint={`${downloadedAssets.length} Downloads · ${appBackups.length} App-Backups`}
          tone={downloadedAssets.length + appBackups.length > 0 ? 'violet' : 'neutral'}
        />
      </AdminStatsGrid>

      <AdminSection
        title="Schnellzugriff"
        description="Die wichtigsten Wartungswege ohne Umwege."
        actions={
          <div className="flex flex-wrap gap-2 text-xs">
            <AdminStatusPill tone="blue">Diagnose</AdminStatusPill>
            <AdminStatusPill tone="amber">Updates</AdminStatusPill>
            <AdminStatusPill tone="violet">Backups</AdminStatusPill>
          </div>
        }
      >
        <div className="grid gap-3 lg:grid-cols-3 text-sm leading-6 text-zinc-400">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
            <p className="font-medium text-white">Direkt aktualisieren</p>
            Neue Versionen können hier geprüft, geladen und direkt installiert werden — mit Backup davor.
          </div>
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
            <p className="font-medium text-white">Backups & Support</p>
            App-Backups, Downloads und das Support-Bundle liegen gebündelt an einer Stelle.
          </div>
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
            <p className="font-medium text-white">Device Ops</p>
            Neustart, Autodarts, Shell und Host-Aktionen bleiben gesammelt unter Device Ops.
          </div>
        </div>
      </AdminSection>

      <Tabs defaultValue="updates" className="space-y-6">
        <TabsList className="bg-zinc-900 border border-zinc-800 p-1 h-auto flex-wrap">
          <TabsTrigger value="updates" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-updates">
            <ArrowUpCircle className="w-4 h-4 mr-2" /> Updates
          </TabsTrigger>
          <TabsTrigger value="backups" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-backups">
            <Database className="w-4 h-4 mr-2" /> Backups
          </TabsTrigger>
          <TabsTrigger value="logs" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-logs">
            <Terminal className="w-4 h-4 mr-2" /> Diagnostics
          </TabsTrigger>
          <TabsTrigger value="device" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-device">
            <ShieldCheck className="w-4 h-4 mr-2" /> Device Ops
          </TabsTrigger>
          <TabsTrigger value="details" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="tab-details">
            <Server className="w-4 h-4 mr-2" /> Host & Dienste
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
                          v{updates?.current_version || sysInfo?.version || '–'}
                        </span>
                        <p className="mt-1 text-xs font-mono text-emerald-500/80" data-testid="update-build-tag">
                          Release-Kanal: stable · Update-System aktiv
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
                  <div className="rounded-3xl border border-emerald-500/30 bg-emerald-500/10 p-5" data-testid="update-available-banner">
                    <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                      <div className="min-w-0 flex-1">
                        <p className="text-emerald-400 font-medium flex items-center gap-2 text-lg">
                          <ArrowUpCircle className="w-5 h-5" />
                          v{githubReleases.latest_version} verfuegbar
                        </p>
                        <p className="text-sm text-zinc-400 mt-1">{githubReleases.latest_name}</p>
                        <ChangelogBlock body={githubReleases.latest_body} />
                      </div>
                      <div className="flex flex-col gap-2 sm:flex-row xl:flex-col xl:items-stretch">
                        <Button
                          onClick={() => handleDirectInstallRelease({
                            version: githubReleases.latest_version,
                            assets: githubReleases.latest_assets || [],
                          })}
                          disabled={installing || rollbackInProgress || preparingUpdate || downloading}
                          className="bg-emerald-600 hover:bg-emerald-700 text-white"
                          data-testid="direct-install-latest-btn"
                        >
                          <ArrowUpCircle className="w-4 h-4 mr-2" />
                          {installing && installingTarget === githubReleases.latest_version ? 'Installiert...' : 'Jetzt installieren'}
                        </Button>
                        <Button
                          onClick={() => handlePrepareUpdate(githubReleases.latest_version)}
                          disabled={preparingUpdate || installing}
                          variant="outline"
                          className="border-zinc-700 text-zinc-300 hover:text-white"
                          data-testid="prepare-update-btn"
                        >
                          <ShieldCheck className="w-4 h-4 mr-2" />
                          {preparingUpdate ? 'Vorbereiten...' : 'Details / Pakete'}
                        </Button>
                      </div>
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
                            <div key={i} className="flex flex-col gap-3 rounded-2xl bg-zinc-800/50 p-3 lg:flex-row lg:items-center lg:justify-between">
                              <div className="flex min-w-0 items-center gap-2">
                                <FileDown className="w-4 h-4 text-zinc-500 flex-shrink-0" />
                                <span className="min-w-0 break-words text-sm text-zinc-300">{dl.label}</span>
                                <span className="text-xs text-zinc-600">{formatBytes(dl.size)}</span>
                              </div>
                              <div className="flex flex-wrap gap-2 flex-shrink-0">
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
                        const assetVersion = parseAssetVersion(a.name);
                        const installable = Boolean(assetVersion && /-windows\./i.test(a.name || ''));
                        return (
                          <div key={a.name} className="flex flex-col gap-3 rounded-2xl bg-zinc-800/50 p-3 lg:flex-row lg:items-center lg:justify-between" data-testid={`downloaded-${a.name}`}>
                            <div className="flex min-w-0 items-center gap-2">
                              <Package className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                              <span className="min-w-0 break-all text-sm text-white font-mono">{a.name}</span>
                              <span className="text-xs text-zinc-500">{formatBytes(a.size)}</span>
                            </div>
                            <div className="flex flex-wrap gap-2 items-center lg:justify-end">
                              <span className="text-xs text-zinc-600">{formatDate(a.downloaded_at)}</span>
                              {installable ? (
                                <Button
                                  size="sm"
                                  onClick={() => handleInstallUpdate(a.name, assetVersion)}
                                  disabled={installing || rollbackInProgress}
                                  className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
                                  data-testid={`install-btn-${a.name}`}
                                >
                                  <ArrowUpCircle className="w-3 h-3 mr-1" />
                                  {installing && installingTarget === assetVersion ? 'Installiert...' : `v${assetVersion} installieren`}
                                </Button>
                              ) : (
                                <AdminStatusPill tone="amber">Manuell / nicht direkt installierbar</AdminStatusPill>
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
                            className="flex flex-col gap-3 rounded-2xl bg-zinc-800/50 p-3 transition-colors hover:bg-zinc-800/70 lg:flex-row lg:items-center lg:justify-between"
                            onClick={() => setExpandedRelease(expandedRelease === r.tag ? null : r.tag)}
                          >
                            <div className="flex min-w-0 items-center gap-3 flex-1">
                              {r.is_current
                                ? <CheckCircle className="w-4 h-4 text-emerald-500 flex-shrink-0" />
                                : r.is_newer
                                  ? <ArrowUpCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                                  : <Clock className="w-4 h-4 text-zinc-600 flex-shrink-0" />
                              }
                              <span className="break-all text-white font-mono">{r.tag}</span>
                              <span className="min-w-0 break-words text-xs text-zinc-500">{r.name}</span>
                              {r.is_prerelease && <span className="text-xs px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">pre</span>}
                              {r.is_current && <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-400">aktiv</span>}
                              {r.published_at && <span className="text-xs text-zinc-600 ml-auto">{formatDate(r.published_at)}</span>}
                            </div>
                            <div className="flex flex-wrap items-center gap-2 lg:ml-2">
                              {r.is_newer && !r.is_prerelease && getPreferredWindowsAsset(r) && (
                                <Button
                                  size="sm"
                                  onClick={(e) => { e.stopPropagation(); handleDirectInstallRelease(r); }}
                                  disabled={installing || rollbackInProgress || preparingUpdate || downloading}
                                  className="bg-emerald-600 hover:bg-emerald-700 text-white text-xs"
                                >
                                  <ArrowUpCircle className="w-3 h-3 mr-1" />
                                  {installing && installingTarget === r.version ? 'Installiert...' : 'Jetzt installieren'}
                                </Button>
                              )}
                              {r.is_newer && !r.is_prerelease && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={(e) => { e.stopPropagation(); handlePrepareUpdate(r.version); }}
                                  disabled={preparingUpdate}
                                  className="border-zinc-700 text-zinc-400 hover:text-white text-xs"
                                >
                                  Pakete
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
          <div className="space-y-6">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div>
                    <CardTitle className="text-white flex items-center gap-2">
                      <Archive className="w-5 h-5 text-amber-500" /> Support snapshot & Bundle
                    </CardTitle>
                    <p className="text-sm text-zinc-400 mt-2">
                      Dieselbe Sicht, die auch im Support-Bundle landet: Runtime-Status, Setup/Readiness, Agent-Lage, Update-Artefakte und aktueller Log-Tail.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button onClick={fetchAll} variant="outline" size="sm" className="border-zinc-700 text-zinc-400 hover:text-white">
                      <RefreshCw className="w-3 h-3 mr-1" /> Refresh
                    </Button>
                    <Button onClick={downloadLogBundle} className="bg-amber-500 hover:bg-amber-400 text-black" size="sm" data-testid="logs-download-btn">
                      <Archive className="w-3 h-3 mr-1" /> Support-Bundle exportieren
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Readiness</p>
                    <p className="mt-2 text-lg font-semibold text-white">{supportSnapshot?.readiness?.summary?.status || '–'}</p>
                    <p className="mt-1 text-xs text-zinc-500">
                      {supportSnapshot?.readiness?.summary?.fail_count || 0} Blocker · {supportSnapshot?.readiness?.summary?.warn_count || 0} Hinweise
                    </p>
                  </div>
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Agent / Device Ops</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {supportSnapshot?.agent_status?.agent_online ? 'Agent online' : 'Fallback / lokal'}
                    </p>
                    <p className="mt-1 text-xs text-zinc-500">Quelle: {supportSnapshot?.agent_status?.source || '–'}</p>
                  </div>
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Update-Artefakte</p>
                    <p className="mt-2 text-lg font-semibold text-white">
                      {(supportSnapshot?.downloaded_assets?.count || 0) + (supportSnapshot?.app_backups?.count || 0)}
                    </p>
                    <p className="mt-1 text-xs text-zinc-500">
                      {supportSnapshot?.downloaded_assets?.count || 0} Downloads · {supportSnapshot?.app_backups?.count || 0} App-Backups
                    </p>
                  </div>
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Artefakte</p>
                    <p className="mt-2 text-lg font-semibold text-white">{supportSnapshot?.screenshots?.count || 0} Screenshots</p>
                    <p className="mt-1 text-xs text-zinc-500">{supportSnapshot?.logs?.files?.length || 0} Logdatei(en) im Bundle</p>
                  </div>
                </div>

                <div className="grid gap-4 xl:grid-cols-[0.95fr,1.05fr]">
                  <div className="rounded-3xl border border-zinc-800 bg-zinc-950/70 p-4">
                    <p className="text-sm font-semibold uppercase tracking-[0.22em] text-zinc-400">Bundle-Inhalt</p>
                    <div className="mt-3 space-y-2 text-sm text-zinc-300">
                      {(supportSnapshot?.support_bundle?.includes || []).map((entry) => (
                        <div key={entry} className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-3 py-2 font-mono text-xs text-zinc-400">
                          {entry}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="rounded-3xl border border-zinc-800 bg-zinc-950/70 p-4">
                    <p className="text-sm font-semibold uppercase tracking-[0.22em] text-zinc-400">Sofort sichtbar im Snapshot</p>
                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                        <p className="text-zinc-500 text-xs">System</p>
                        <p className="mt-1 text-white">v{supportSnapshot?.system_info?.version || '–'} · {supportSnapshot?.system_info?.mode || '–'}</p>
                        <p className="mt-1 text-xs text-zinc-500 break-all">DB: {supportSnapshot?.system_info?.database?.path || '–'}</p>
                      </div>
                      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                        <p className="text-zinc-500 text-xs">Setup</p>
                        <p className="mt-1 text-white">{supportSnapshot?.setup_status?.is_complete ? 'Abgeschlossen' : 'Offen'}</p>
                        <p className="mt-1 text-xs text-zinc-500">Secrets: {supportSnapshot?.secrets_status?.loaded_in_env ? 'geladen' : 'prüfen'}</p>
                      </div>
                      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                        <p className="text-zinc-500 text-xs">Health</p>
                        <p className="mt-1 text-white">{supportSnapshot?.health?.status || '–'}</p>
                        <p className="mt-1 text-xs text-zinc-500">Observer: {supportSnapshot?.health?.observer_metrics?.failed || 0} Fehler</p>
                      </div>
                      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                        <p className="text-zinc-500 text-xs">Letztes Update-Ergebnis</p>
                        <p className="mt-1 text-white">
                          {supportSnapshot?.update_result?.has_result
                            ? supportSnapshot?.update_result?.result?.success
                              ? 'Erfolgreich'
                              : 'Fehlgeschlagen'
                            : 'Keins vorhanden'}
                        </p>
                        <p className="mt-1 text-xs text-zinc-500">{supportSnapshot?.update_result?.result?.target_version ? `Ziel: v${supportSnapshot.update_result.result.target_version}` : '–'}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-white flex items-center gap-2">
                    <Terminal className="w-5 h-5 text-amber-500" /> Aktueller Log-Tail
                  </CardTitle>
                  <AdminStatusPill tone="blue">
                    {logs.length} Zeilen
                  </AdminStatusPill>
                </div>
                <p className="text-xs text-zinc-500 mt-2">
                  Schnelllesbare Live-Sicht. Für vollständige Artefakte, zusätzliche Dateien und Snapshots bitte das Support-Bundle ziehen.
                </p>
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
          </div>
        </TabsContent>

        {/* ===== Device Ops Tab ===== */}
        <TabsContent value="device">
          <div className="space-y-4">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-amber-500" /> Windows / Device Operations
                </CardTitle>
                <p className="text-sm text-zinc-400">
                  Nutzt bevorzugt den lokalen Windows-Agenten und faellt fuer sichere Recovery-Faelle auf bestehende Backend-Pfade zurueck.
                </p>
                <div className="mt-3 flex flex-wrap gap-2 text-xs">
                  <AdminStatusPill tone="blue">1. Erst Zustand lesen</AdminStatusPill>
                  <AdminStatusPill tone="amber">2. Dann gezielt eingreifen</AdminStatusPill>
                  <AdminStatusPill tone="red">Explorer zuerst, wenn der Shell-Lockdown Ärger macht</AdminStatusPill>
                </div>
              </CardHeader>
            </Card>
            <AgentTab
              agentStatus={agentStatus}
              setAgentStatus={setAgentStatus}
              headers={headers}
              t={t}
              fetchAll={fetchAll}
            />
          </div>
        </TabsContent>

        {/* ===== Details Tab ===== */}
        <TabsContent value="details">
          <div className="space-y-4">
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

          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Zap className="w-5 h-5 text-amber-500" /> Maintenance inventory
              </CardTitle>
              <p className="text-sm text-zinc-400">
                Nur Lesesicht: welche Recovery-/Support-Artefakte aktuell wirklich vorhanden sind. Eingriffe passieren bewusst in Device Ops, Updates oder Backups.
              </p>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                  <p className="text-xs text-zinc-500 uppercase tracking-[0.22em]">Readiness</p>
                  <p className="mt-2 text-lg font-semibold text-white">{supportSnapshot?.readiness?.summary?.status || '–'}</p>
                  <p className="mt-1 text-xs text-zinc-500">{supportSnapshot?.readiness?.summary?.check_count || 0} Checks</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                  <p className="text-xs text-zinc-500 uppercase tracking-[0.22em]">Support-Logs</p>
                  <p className="mt-2 text-lg font-semibold text-white">{supportSnapshot?.logs?.files?.length || 0}</p>
                  <p className="mt-1 text-xs text-zinc-500 break-all">{supportSnapshot?.logs?.dir || '–'}</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                  <p className="text-xs text-zinc-500 uppercase tracking-[0.22em]">Screenshots</p>
                  <p className="mt-2 text-lg font-semibold text-white">{supportSnapshot?.screenshots?.count || 0}</p>
                  <p className="mt-1 text-xs text-zinc-500 break-all">{supportSnapshot?.screenshots?.dir || '–'}</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                  <p className="text-xs text-zinc-500 uppercase tracking-[0.22em]">Secrets</p>
                  <p className="mt-2 text-lg font-semibold text-white">{supportSnapshot?.secrets_status?.loaded_in_env ? 'geladen' : 'prüfen'}</p>
                  <p className="mt-1 text-xs text-zinc-500 break-all">{supportSnapshot?.secrets_status?.file_path || '–'}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Monitor className="w-5 h-5 text-amber-500" /> Device snapshot
              </CardTitle>
              <p className="text-sm text-zinc-400">
                Was die Maintenance-Fläche aktuell über Agent, Shell und lokale Board-Zuordnung weiß – ohne doppelte Buttons und ohne falsche Versprechen.
              </p>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                  <p className="text-xs text-zinc-500 uppercase tracking-[0.22em]">Device Ops Quelle</p>
                  <p className="mt-2 text-white">{agentStatus?.source === 'agent' ? 'Windows-Agent' : 'Lokaler Fallback'}</p>
                  <p className="mt-1 text-xs text-zinc-500">{agentStatus?.agent_online ? 'Agent erreichbar' : 'Keine Agent-Verbindung – lokale Recovery bleibt nutzbar'}</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3">
                  <p className="text-xs text-zinc-500 uppercase tracking-[0.22em]">Lokales Board</p>
                  <p className="mt-2 text-white">{supportSnapshot?.readiness?.board?.board_id || supportSnapshot?.readiness?.local_board_id || '–'}</p>
                  <p className="mt-1 text-xs text-zinc-500">{supportSnapshot?.readiness?.board?.name || 'Kein Board gemappt'}</p>
                </div>
                <div className="rounded-2xl border border-zinc-800 bg-zinc-950/70 px-4 py-3 md:col-span-2">
                  <p className="text-xs text-zinc-500 uppercase tracking-[0.22em]">Empfohlene Reihenfolge bei Ärger</p>
                  <div className="mt-2 space-y-2 text-sm text-zinc-300">
                    <p>1. Diagnostics lesen und Bundle ziehen.</p>
                    <p>2. Wenn der Lockdown/Shell das Problem ist: zuerst in Device Ops auf Explorer umstellen.</p>
                    <p>3. Danach gezielt Backend/Autodarts/Task-Manager anfassen – nicht alles gleichzeitig drücken.</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
          </div>
        </TabsContent>
      </Tabs>
    </AdminPage>
  );
}
