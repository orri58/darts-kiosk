import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  CheckCircle,
  XCircle,
  RefreshCw,
  Cpu,
  Monitor,
  Power,
  PlayCircle,
  RotateCcw,
  Clock,
  Wifi,
  WifiOff,
  Terminal,
  Lock,
  Unlock,
  AlertTriangle,
  Info,
  Zap,
  Shield
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function ConfirmDialog({ open, title, message, onConfirm, onCancel, danger }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" data-testid="agent-confirm-dialog">
      <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 max-w-md w-full mx-4 shadow-xl">
        <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
        <p className="text-sm text-zinc-400 mb-6">{message}</p>
        <div className="flex gap-3 justify-end">
          <Button variant="outline" onClick={onCancel} className="border-zinc-600 text-zinc-300" data-testid="agent-confirm-cancel">
            Abbrechen
          </Button>
          <Button
            onClick={onConfirm}
            className={danger ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-amber-500 hover:bg-amber-600 text-black'}
            data-testid="agent-confirm-ok"
          >
            Ausfuehren
          </Button>
        </div>
      </div>
    </div>
  );
}

function StatusRow({ icon: Icon, label, value, valueClass, testId }) {
  return (
    <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm" data-testid={testId}>
      <div className="flex items-center gap-2">
        <Icon className="w-4 h-4 text-zinc-500" />
        <span className="text-sm text-zinc-400">{label}</span>
      </div>
      <span className={`text-sm font-mono ${valueClass || 'text-zinc-300'}`}>{value}</span>
    </div>
  );
}

function ViaBadge({ source, t }) {
  if (!source) return null;
  const isAgent = source === 'agent';
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded ${isAgent ? 'bg-emerald-500/20 text-emerald-400' : 'bg-amber-500/20 text-amber-400'}`}>
      {t('agent_via_badge')}: {isAgent ? t('agent_source_agent') : t('agent_source_fallback')}
    </span>
  );
}

function formatUptime(s) {
  if (!s) return '-';
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h ${m}m`;
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function AgentTab({ agentStatus, setAgentStatus, headers, t, fetchAll }) {
  const [confirm, setConfirm] = useState(null);
  const [actionInProgress, setActionInProgress] = useState(null);

  const agentOnline = agentStatus?.agent_online === true;
  const source = agentStatus?.source;

  const doAction = async (endpoint, successMsg, body = {}) => {
    setActionInProgress(endpoint);
    setConfirm(null);
    try {
      const res = await axios.post(`${API}${endpoint}`, body, { headers, timeout: 8000 });
      const via = res.data?.via === 'agent' ? ' (Agent)' : ' (Fallback)';
      toast.success(`${successMsg}${via}`);
      // Refresh agent status
      setTimeout(async () => {
        try {
          const r = await axios.get(`${API}/admin/agent/status`, { headers });
          setAgentStatus(r.data);
        } catch { /* ignore */ }
      }, 2000);
    } catch (err) {
      toast.error(`Fehler: ${err.response?.data?.detail || err.message}`);
    } finally {
      setActionInProgress(null);
    }
  };

  const refreshStatus = async () => {
    try {
      const r = await axios.get(`${API}/admin/agent/status`, { headers });
      setAgentStatus(r.data);
      toast.success('Agent-Status aktualisiert');
    } catch {
      toast.error('Agent-Status konnte nicht geladen werden');
    }
  };

  const ad = agentStatus?.autodarts || {};
  const kioskWin = agentStatus?.kiosk_window || {};
  const shell = agentStatus?.shell || {};
  const taskMgr = agentStatus?.task_manager || {};

  return (
    <div className="space-y-4">
      {/* Agent Status Header */}
      <Card className="bg-zinc-900 border-zinc-800" data-testid="agent-status-card">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-white flex items-center gap-2">
              <Cpu className="w-5 h-5 text-amber-500" /> {t('agent_status')}
            </CardTitle>
            <div className="flex items-center gap-2">
              <ViaBadge source={source} t={t} />
              <Button variant="ghost" size="sm" onClick={refreshStatus} className="text-zinc-400 hover:text-white" data-testid="agent-refresh-btn">
                <RefreshCw className="w-4 h-4" />
              </Button>
            </div>
          </div>
          <p className="text-sm text-zinc-400">{t('agent_status_desc')}</p>
        </CardHeader>
        <CardContent className="space-y-2">
          {/* Online/Offline */}
          <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm" data-testid="agent-online-status">
            <div className="flex items-center gap-2">
              {agentOnline ? <Wifi className="w-4 h-4 text-emerald-400" /> : <WifiOff className="w-4 h-4 text-red-400" />}
              <span className="text-sm text-zinc-400">Status</span>
            </div>
            <span className={`text-sm font-semibold ${agentOnline ? 'text-emerald-400' : 'text-red-400'}`}>
              {agentOnline ? t('agent_online') : t('agent_offline')}
            </span>
          </div>

          {agentOnline && (
            <>
              <StatusRow icon={Info} label={t('agent_version')} value={agentStatus.agent_version || '-'} testId="agent-version" />
              <StatusRow icon={Cpu} label={t('agent_platform')}
                value={`${agentStatus.platform || '-'} ${agentStatus.platform_release || ''}`}
                testId="agent-platform" />
              <StatusRow icon={Clock} label={t('agent_uptime')} value={formatUptime(agentStatus.uptime_s)} testId="agent-uptime" />
              <StatusRow icon={Clock} label={t('agent_heartbeat')}
                value={agentStatus.heartbeat ? new Date(agentStatus.heartbeat).toLocaleString('de-DE') : '-'}
                testId="agent-heartbeat" />
              {agentStatus.pid && (
                <StatusRow icon={Info} label="PID" value={agentStatus.pid} testId="agent-pid" />
              )}
              {/* Autostart Status */}
              {agentStatus.autostart && (
                <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm" data-testid="agent-autostart-status">
                  <div className="flex items-center gap-2">
                    <PlayCircle className="w-4 h-4 text-zinc-500" />
                    <span className="text-sm text-zinc-400">{t('agent_autostart')}</span>
                  </div>
                  {agentStatus.autostart.supported === false ? (
                    <span className="text-xs text-zinc-500">{t('windows_only')}</span>
                  ) : agentStatus.autostart.registered ? (
                    <span className="text-sm text-emerald-400 flex items-center gap-1">
                      <CheckCircle className="w-3.5 h-3.5" /> {t('agent_autostart_registered')}
                    </span>
                  ) : (
                    <span className="text-sm text-amber-400 flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" /> {t('agent_autostart_not_registered')}
                    </span>
                  )}
                </div>
              )}
              {agentStatus.autostart?.task_status && (
                <div className="pl-9 text-xs text-zinc-500 -mt-1" data-testid="agent-autostart-detail">
                  Task: {agentStatus.autostart.task_status}
                  {agentStatus.autostart.last_run && ` | ${t('agent_autostart_last_run')}: ${agentStatus.autostart.last_run}`}
                </div>
              )}
            </>
          )}

          {!agentOnline && (
            <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-sm flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0" />
              <span className="text-xs text-amber-400">{t('agent_fallback_hint')}</span>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Autodarts Desktop Section */}
      <Card className="bg-zinc-900 border-zinc-800" data-testid="agent-autodarts-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-white flex items-center gap-2 text-base">
            <Monitor className="w-5 h-5 text-amber-500" /> {t('agent_autodarts_section')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Running status */}
          <div className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm" data-testid="agent-autodarts-status">
            <div className="flex items-center gap-2">
              <span className="text-sm text-zinc-400">Status</span>
            </div>
            <div className="flex items-center gap-2">
              {ad.running ? (
                <span className="text-sm text-emerald-400 flex items-center gap-1">
                  <CheckCircle className="w-3.5 h-3.5" /> {t('agent_autodarts_running')}
                </span>
              ) : (
                <span className="text-sm text-red-400 flex items-center gap-1">
                  <XCircle className="w-3.5 h-3.5" /> {t('agent_autodarts_stopped')}
                </span>
              )}
              {ad.pid && <span className="text-xs text-zinc-500 font-mono">PID: {ad.pid}</span>}
            </div>
          </div>

          {ad.last_error && (
            <div className="p-2 bg-red-500/10 border border-red-500/20 rounded-sm text-xs text-red-400 font-mono">
              {ad.last_error}
            </div>
          )}

          {ad.cooldown_active && (
            <div className="p-2 bg-amber-500/10 border border-amber-500/20 rounded-sm text-xs text-amber-400 flex items-center gap-1">
              <Clock className="w-3 h-3" /> {t('agent_cooldown')}
            </div>
          )}

          {/* Buttons */}
          <div className="flex gap-2">
            <Button
              onClick={() => doAction('/admin/agent/autodarts/ensure', t('agent_autodarts_ensure'))}
              disabled={actionInProgress === '/admin/agent/autodarts/ensure'}
              variant="outline"
              className="flex-1 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
              data-testid="agent-autodarts-ensure-btn"
            >
              <PlayCircle className={`w-4 h-4 mr-2 ${actionInProgress === '/admin/agent/autodarts/ensure' ? 'animate-spin' : ''}`} />
              {t('agent_autodarts_ensure')}
            </Button>
            <Button
              onClick={() => setConfirm({
                title: t('agent_autodarts_restart'),
                message: t('agent_autodarts_restart_confirm'),
                action: () => doAction('/admin/agent/autodarts/restart', t('agent_autodarts_restart')),
              })}
              disabled={!!actionInProgress}
              variant="outline"
              className="flex-1 border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
              data-testid="agent-autodarts-restart-btn"
            >
              <RotateCcw className="w-4 h-4 mr-2" />
              {t('agent_autodarts_restart')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Kiosk Window */}
      {agentOnline && (
        <Card className="bg-zinc-900 border-zinc-800" data-testid="agent-kiosk-window-card">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Monitor className="w-4 h-4 text-zinc-500" />
                <span className="text-sm text-zinc-400">{t('agent_kiosk_window')}</span>
              </div>
              <span className={`text-sm ${kioskWin.detected ? 'text-emerald-400' : 'text-zinc-500'}`}>
                {kioskWin.detected ? (
                  <span className="flex items-center gap-1"><CheckCircle className="w-3.5 h-3.5" /> {t('agent_kiosk_window_detected')}</span>
                ) : (
                  <span className="flex items-center gap-1"><XCircle className="w-3.5 h-3.5" /> {t('agent_kiosk_window_not_detected')}</span>
                )}
              </span>
            </div>
            {kioskWin.title && <p className="text-xs text-zinc-600 mt-1 font-mono ml-6">{kioskWin.title}</p>}
          </CardContent>
        </Card>
      )}

      {/* System Commands */}
      <Card className="bg-zinc-900 border-zinc-800" data-testid="agent-system-card">
        <CardHeader className="pb-3">
          <CardTitle className="text-white flex items-center gap-2 text-base">
            <Zap className="w-5 h-5 text-amber-500" /> {t('agent_system_section')}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            <Button
              onClick={() => setConfirm({
                title: t('agent_restart_backend'),
                message: t('agent_restart_backend_confirm'),
                action: () => doAction('/admin/agent/system/restart-backend', t('agent_restart_backend')),
              })}
              disabled={!!actionInProgress}
              variant="outline"
              className="border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
              data-testid="agent-restart-backend-btn"
            >
              <RotateCcw className={`w-4 h-4 mr-2 ${actionInProgress === '/admin/agent/system/restart-backend' ? 'animate-spin' : ''}`} />
              {t('agent_restart_backend')}
            </Button>
            <Button
              onClick={() => setConfirm({
                title: t('agent_reboot'),
                message: t('agent_reboot_confirm'),
                action: () => doAction('/admin/agent/system/reboot', t('agent_reboot')),
                danger: true,
              })}
              disabled={!!actionInProgress}
              variant="outline"
              className="border-red-500/30 text-red-400 hover:bg-red-500/10"
              data-testid="agent-reboot-btn"
            >
              <Power className="w-4 h-4 mr-2" />
              {t('agent_reboot')}
            </Button>
            <Button
              onClick={() => setConfirm({
                title: t('agent_shutdown'),
                message: t('agent_shutdown_confirm'),
                action: () => doAction('/admin/agent/system/shutdown', t('agent_shutdown')),
                danger: true,
              })}
              disabled={!!actionInProgress}
              variant="outline"
              className="border-red-500/30 text-red-400 hover:bg-red-500/10"
              data-testid="agent-shutdown-btn"
            >
              <Power className="w-4 h-4 mr-2" />
              {t('agent_shutdown')}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Kiosk Controls via Agent */}
      {agentOnline && (
        <Card className="bg-zinc-900 border-zinc-800" data-testid="agent-kiosk-controls-card">
          <CardHeader className="pb-3">
            <CardTitle className="text-white flex items-center gap-2 text-base">
              <Shield className="w-5 h-5 text-amber-500" /> {t('agent_kiosk_section')}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Shell Status */}
            <StatusRow
              icon={Terminal}
              label={t('agent_shell_current')}
              value={shell.shell_mode || '-'}
              valueClass={shell.shell_mode === 'kiosk' ? 'text-amber-400' : shell.shell_mode === 'explorer' ? 'text-emerald-400' : 'text-zinc-500'}
              testId="agent-shell-status"
            />

            <div className="flex gap-2">
              <Button
                onClick={() => setConfirm({
                  title: t('agent_shell_switch_explorer'),
                  message: t('agent_shell_reboot_hint'),
                  action: () => doAction('/admin/agent/kiosk/shell/switch', t('agent_shell_switch_explorer'), { target: 'explorer' }),
                })}
                disabled={!!actionInProgress || shell.shell_mode === 'explorer'}
                variant="outline"
                className="flex-1 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                data-testid="agent-shell-explorer-btn"
              >
                <Monitor className="w-4 h-4 mr-2" />
                {t('agent_shell_switch_explorer')}
              </Button>
              <Button
                onClick={() => setConfirm({
                  title: t('agent_shell_switch_kiosk'),
                  message: t('agent_shell_reboot_hint'),
                  action: () => doAction('/admin/agent/kiosk/shell/switch', t('agent_shell_switch_kiosk'), { target: 'kiosk' }),
                })}
                disabled={!!actionInProgress || shell.shell_mode === 'kiosk'}
                variant="outline"
                className="flex-1 border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
                data-testid="agent-shell-kiosk-btn"
              >
                <Shield className="w-4 h-4 mr-2" />
                {t('agent_shell_switch_kiosk')}
              </Button>
            </div>

            {/* Task Manager */}
            <StatusRow
              icon={taskMgr.disabled ? Lock : Unlock}
              label={t('agent_taskmgr_status')}
              value={taskMgr.disabled ? t('task_manager_disabled') : t('task_manager_enabled')}
              valueClass={taskMgr.disabled ? 'text-red-400' : 'text-emerald-400'}
              testId="agent-taskmgr-status"
            />

            <div className="flex gap-2">
              <Button
                onClick={() => doAction('/admin/agent/kiosk/taskmanager/set', t('agent_taskmgr_enable'), { enabled: true })}
                disabled={!!actionInProgress || !taskMgr.disabled}
                variant="outline"
                className="flex-1 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                data-testid="agent-taskmgr-enable-btn"
              >
                <Unlock className="w-4 h-4 mr-2" />
                {t('agent_taskmgr_enable')}
              </Button>
              <Button
                onClick={() => setConfirm({
                  title: t('agent_taskmgr_disable'),
                  message: t('disable_task_manager_confirm'),
                  action: () => doAction('/admin/agent/kiosk/taskmanager/set', t('agent_taskmgr_disable'), { enabled: false }),
                  danger: true,
                })}
                disabled={!!actionInProgress || taskMgr.disabled}
                variant="outline"
                className="flex-1 border-red-500/30 text-red-400 hover:bg-red-500/10"
                data-testid="agent-taskmgr-disable-btn"
              >
                <Lock className="w-4 h-4 mr-2" />
                {t('agent_taskmgr_disable')}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Confirmation Dialog */}
      <ConfirmDialog
        open={!!confirm}
        title={confirm?.title || ''}
        message={confirm?.message || ''}
        danger={confirm?.danger}
        onConfirm={() => confirm?.action?.()}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}
