import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  AlertTriangle,
  ArrowUpCircle,
  BellOff,
  FileText,
  Lock,
  Play,
  Plus,
  RefreshCw,
  Settings,
  Target,
  TrendingUp,
  Unlock,
  Wifi,
  WifiOff,
  X,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { Input } from '../../components/ui/input';
import { useSettings } from '../../context/SettingsContext';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import { useBoardWS } from '../../hooks/useBoardWS';
import {
  AdminLinkTile,
  AdminMiniAction,
  AdminPage,
  AdminSection,
  AdminStatusPill,
} from '../../components/admin/AdminShell';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_STYLES = {
  locked: { tone: 'neutral', icon: Lock, label: 'Gesperrt' },
  unlocked: { tone: 'amber', icon: Unlock, label: 'Freigeschaltet' },
  in_game: { tone: 'emerald', icon: Play, label: 'Im Spiel' },
  blocked_pending: { tone: 'red', icon: AlertTriangle, label: 'Wartet auf Credits' },
  offline: { tone: 'red', icon: WifiOff, label: 'Offline' },
};

function formatRemaining(session, boardStatus) {
  if (!session) return 'Keine aktive Session';
  if (session.pricing_mode === 'per_player') {
    const requiredPlayers = session.players_count || session.players?.length || 1;
    const shortage = Math.max(0, requiredPlayers - (session.credits_remaining || 0));
    if (boardStatus === 'blocked_pending') {
      return `${session.credits_remaining} Credits da, ${shortage} fehlen für ${requiredPlayers} Spieler`;
    }
    if (requiredPlayers > 0) {
      return `${session.credits_remaining} Credits verfügbar · letzter Match mit ${requiredPlayers} Spielern`;
    }
    return `${session.credits_remaining} Credits verfügbar · Abrechnung erst beim echten Matchstart`;
  }
  if (session.pricing_mode === 'per_time' && session.expires_at) {
    const diffMs = Math.max(0, new Date(session.expires_at).getTime() - Date.now());
    const minutes = Math.ceil(diffMs / 60000);
    return `${minutes} min Restzeit`;
  }
  if (session.pricing_mode === 'per_game') {
    return `${session.credits_remaining} / ${session.credits_total} Spiel-Credits übrig (Legacy)`;
  }
  return 'Aktive Session';
}

function formatSessionMode(session) {
  if (!session) return 'Keine aktive Session';
  if (session.pricing_mode === 'per_time') return 'Zeitbasiert (Legacy)';
  if (session.pricing_mode === 'per_game') return 'Spielbasiert (Legacy)';
  return 'Credits-basiert';
}

function calculateExtendPrice(session, pricing, credits, minutes) {
  if (!session) return 0;
  if (session.pricing_mode === 'per_time') {
    const halfHours = Math.max(0, Number(minutes || 0)) / 30;
    return halfHours * Number(pricing?.per_time?.price_per_30_min || 5);
  }
  return Math.max(0, Number(credits || 0)) * Number(pricing?.per_game?.price_per_credit || 2);
}

export default function AdminDashboard() {
  const { pricing } = useSettings();
  const { token } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [boards, setBoards] = useState([]);
  const [boardDetails, setBoardDetails] = useState({});
  const [loading, setLoading] = useState(true);
  const [observerStatuses, setObserverStatuses] = useState({});
  const [selectedBoard, setSelectedBoard] = useState(null);
  const [showUnlockDialog, setShowUnlockDialog] = useState(false);
  const [showExtendDialog, setShowExtendDialog] = useState(false);
  const [updateNotification, setUpdateNotification] = useState(null);
  const [showChangelog, setShowChangelog] = useState(false);

  const [unlockCredits, setUnlockCredits] = useState(3);
  const [unlockMinutes, setUnlockMinutes] = useState(30);

  const fetchBoards = useCallback(async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      const response = await axios.get(`${API}/boards`, { headers });
      setBoards(response.data || []);

      const [detailsEntries, observerResult] = await Promise.all([
        Promise.all(
          (response.data || []).map(async (board) => {
            try {
              const detailRes = await axios.get(`${API}/boards/${board.board_id}`, { headers });
              return [board.board_id, detailRes.data.active_session || null];
            } catch {
              return [board.board_id, null];
            }
          })
        ),
        axios.get(`${API}/kiosk/observers/all`).catch(() => null),
      ]);

      setBoardDetails(Object.fromEntries(detailsEntries));
      const observerMap = {};
      (observerResult?.data?.observers || []).forEach((item) => {
        observerMap[item.board_id] = item;
      });
      setObserverStatuses(observerMap);
    } catch (error) {
      console.error('Failed to fetch boards:', error);
      toast.error('Boards konnten nicht geladen werden');
    } finally {
      setLoading(false);
    }
  }, [token]);

  const onWsEvent = useCallback(
    (event) => {
      if (['board_status', 'session_extended', 'credit_update', 'session_state'].includes(event)) {
        fetchBoards();
      }
    },
    [fetchBoards]
  );
  const { connected: wsConnected } = useBoardWS(onWsEvent);

  useEffect(() => {
    fetchBoards();
    const interval = setInterval(() => {
      if (!wsConnected) fetchBoards();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchBoards, wsConnected]);

  useEffect(() => {
    const fetchNotification = async () => {
      try {
        const res = await axios.get(`${API}/updates/notification`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = res.data;
        if (!data.update_available) {
          setUpdateNotification(null);
          return;
        }
        if (data.dismissed_version === data.latest_version) {
          setUpdateNotification(null);
          return;
        }
        if (data.snoozed_version === data.latest_version && data.snooze_until) {
          if (new Date(data.snooze_until) > new Date()) {
            setUpdateNotification(null);
            return;
          }
        }
        setUpdateNotification(data);
      } catch {
        /* ignore */
      }
    };

    fetchNotification();
    const interval = setInterval(fetchNotification, 300000);
    return () => clearInterval(interval);
  }, [token]);

  const dismissNotification = async () => {
    if (!updateNotification) return;
    try {
      await axios.post(
        `${API}/updates/notification/dismiss?version=${updateNotification.latest_version}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } catch {
      /* ignore */
    }
    setUpdateNotification(null);
  };

  const snoozeNotification = async () => {
    if (!updateNotification) return;
    try {
      await axios.post(
        `${API}/updates/notification/snooze?version=${updateNotification.latest_version}&hours=48`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } catch {
      /* ignore */
    }
    setUpdateNotification(null);
  };

  const calculatePrice = () => {
    return unlockCredits * (pricing?.per_game?.price_per_credit || 2.0);
  };

  const handleUnlock = async () => {
    if (!selectedBoard) return;

    try {
      await axios.post(
        `${API}/boards/${selectedBoard.board_id}/unlock`,
        {
          pricing_mode: 'per_player',
          credits: unlockCredits,
          players_count: 0,
          price_total: calculatePrice(),
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      toast.success(`${selectedBoard.name} freigeschaltet`);
      setShowUnlockDialog(false);
      fetchBoards();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Freischalten');
    }
  };

  const handleQuickUnlock = async (board) => {
    try {
      const credits = pricing?.per_game?.default_credits || 3;
      const pricePerCredit = pricing?.per_game?.price_per_credit || 2.0;
      await axios.post(
        `${API}/boards/${board.board_id}/unlock`,
        {
          pricing_mode: 'per_player',
          credits,
          players_count: 0,
          price_total: credits * pricePerCredit,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      toast.success(`${board.name} direkt freigeschaltet`);
      fetchBoards();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Freischalten');
    }
  };

  const handleLock = async (board) => {
    try {
      await axios.post(`${API}/boards/${board.board_id}/lock`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(`${board.name} gesperrt`);
      fetchBoards();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Sperren');
    }
  };

  const handleExtend = async () => {
    if (!selectedBoard) return;

    try {
      const session = boardDetails[selectedBoard.board_id];
      const extendTime = session?.pricing_mode === 'per_time';
      await axios.post(
        `${API}/boards/${selectedBoard.board_id}/extend`,
        {
          credits: extendTime ? null : unlockCredits,
          minutes: extendTime ? unlockMinutes : null,
          price_total: calculateExtendPrice(session, pricing, unlockCredits, unlockMinutes),
        },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      toast.success(`Session für ${selectedBoard.name} verlängert`);
      setShowExtendDialog(false);
      fetchBoards();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Verlängern');
    }
  };

  const openUnlockDialog = (board) => {
    setSelectedBoard(board);
    setUnlockCredits(pricing?.per_game?.default_credits || 3);
    setShowUnlockDialog(true);
  };

  const openExtendDialog = (board) => {
    setSelectedBoard(board);
    setUnlockCredits(1);
    setUnlockMinutes(15);
    setShowExtendDialog(true);
  };

  const metrics = useMemo(() => {
    const total = boards.length;
    const live = boards.filter((board) => board.status !== 'locked' && board.status !== 'offline').length;
    const inGame = boards.filter((board) => board.status === 'in_game').length;
    const offline = boards.filter((board) => board.status === 'offline').length;
    const observerIssues = Object.values(observerStatuses).filter(
      (observer) => observer?.state === 'error' || observer?.last_error
    ).length;

    return { total, live, inGame, offline, observerIssues };
  }, [boards, observerStatuses]);

  const actionBoards = useMemo(() => {
    const priority = {
      blocked_pending: 0,
      in_game: 1,
      unlocked: 2,
      locked: 3,
      offline: 4,
    };
    return [...boards].sort((a, b) => {
      const pa = priority[a.status] ?? 99;
      const pb = priority[b.status] ?? 99;
      if (pa !== pb) return pa - pb;
      return a.name.localeCompare(b.name);
    });
  }, [boards]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <AdminPage
      eyebrow="Darts Control"
      title="Control"
      description="Boards steuern, Credits nachbuchen, Probleme direkt sehen."
      actions={
        <>
          <AdminMiniAction icon={wsConnected ? Wifi : WifiOff} onClick={fetchBoards}>
            {wsConnected ? 'Live verbunden' : 'Polling aktiv'}
          </AdminMiniAction>
          <Button onClick={fetchBoards} variant="outline" className="border-zinc-700 text-zinc-300 hover:text-white">
            <RefreshCw className="w-4 h-4 mr-2" />
            {t('refresh')}
          </Button>
        </>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[
          { label: 'Boards', value: metrics.total, tone: 'amber' },
          { label: 'Aktiv', value: metrics.live, tone: 'emerald' },
          { label: 'Im Spiel', value: metrics.inGame, tone: 'blue' },
          { label: 'Hinweise', value: metrics.offline + metrics.observerIssues, tone: metrics.offline + metrics.observerIssues > 0 ? 'red' : 'neutral' },
        ].map((item) => (
          <div key={item.label} className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.7)] px-4 py-3">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-[var(--color-text-secondary)]">{item.label}</span>
              <AdminStatusPill tone={item.tone}>{item.value}</AdminStatusPill>
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
        <AdminSection
          title="Dart Control"
          description="Alle Boards direkt im Zugriff — auch nach dem Freischalten, damit Nachbuchen sofort geht."
          actions={
            <AdminStatusPill tone={metrics.live ? 'amber' : 'emerald'}>
              {metrics.live ? `${metrics.live} aktiv / bereit` : 'Aktuell alles gesperrt'}
            </AdminStatusPill>
          }
        >
          {actionBoards.length === 0 ? (
            <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.75)] bg-[rgb(var(--color-bg-rgb)/0.34)] px-4 py-4 text-sm text-[var(--color-text-secondary)]">
              Noch keine Boards vorhanden.
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-3">
              {actionBoards.map((board) => {
                const session = boardDetails[board.board_id];
                const isLocked = board.status === 'locked';
                const isTimeMode = session?.pricing_mode === 'per_time';
                const primaryCta = isLocked ? 'Direkt freischalten' : (isTimeMode ? 'Zeit verlängern' : 'Credits nachbuchen');
                const PrimaryIcon = isLocked ? Unlock : Plus;

                return (
                <div key={`quick-${board.board_id}`} className="theme-panel min-w-0 rounded-3xl border p-4 theme-primary-glow">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-base font-semibold text-[var(--color-text)]">{board.name}</p>
                      <p className="mt-1 text-xs font-mono text-[var(--color-text-secondary)]">{board.board_id}</p>
                    </div>
                    <AdminStatusPill tone={(STATUS_STYLES[board.status] || STATUS_STYLES.locked).tone}>
                      {(STATUS_STYLES[board.status] || STATUS_STYLES.locked).label}
                    </AdminStatusPill>
                  </div>
                  <div className="mt-4 space-y-2 text-sm">
                    <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.72)] bg-[rgb(var(--color-bg-rgb)/0.4)] px-3 py-3">
                      <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--color-text-muted)]">Status</p>
                      <p className="mt-1 font-semibold text-[var(--color-text)]">
                        {isLocked
                          ? `${pricing?.per_game?.default_credits || 3} Credits Standard · ${((pricing?.per_game?.default_credits || 3) * (pricing?.per_game?.price_per_credit || 2)).toFixed(2)} €`
                          : formatRemaining(session, board.status)}
                      </p>
                    </div>
                    {session && (
                      <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.72)] bg-[rgb(var(--color-bg-rgb)/0.4)] px-3 py-3">
                        <p className="text-[10px] uppercase tracking-[0.2em] text-[var(--color-text-muted)]">Abrechnung</p>
                        <p className="mt-1 font-semibold text-[var(--color-text)]">{formatSessionMode(session)}</p>
                      </div>
                    )}
                  </div>
                  <div className="mt-4 grid gap-2 lg:grid-cols-2">
                    <Button
                      onClick={() => (isLocked ? handleQuickUnlock(board) : openExtendDialog(board))}
                      className="h-11 rounded-2xl bg-[var(--color-primary)] text-[hsl(var(--primary-foreground))] hover:opacity-90"
                    >
                      <PrimaryIcon className="w-4 h-4 mr-2" />
                      {primaryCta}
                    </Button>
                    {isLocked ? (
                      <Button
                        variant="outline"
                        onClick={() => openUnlockDialog(board)}
                        className="h-11 rounded-2xl border-[rgb(var(--color-border-rgb)/0.8)] text-[var(--color-text-secondary)] hover:border-[rgb(var(--color-primary-rgb)/0.3)] hover:text-[var(--color-text)]"
                      >
                        Anpassen
                      </Button>
                    ) : (
                      <Button
                        variant="outline"
                        onClick={() => handleLock(board)}
                        className="h-11 rounded-2xl border-[rgb(var(--color-accent-rgb)/0.28)] text-[var(--color-accent)] hover:bg-[rgb(var(--color-accent-rgb)/0.12)]"
                      >
                        <Lock className="w-4 h-4 mr-2" /> Sperren
                      </Button>
                    )}
                  </div>
                </div>
              )})}
            </div>
          )}
        </AdminSection>

        <AdminSection title="Heute" description="Knapp, direkt, hilfreich.">
          <div className="grid gap-3 text-sm sm:grid-cols-3 xl:grid-cols-1">
            <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.62)] px-4 py-3 flex items-center justify-between">
              <span className="text-[var(--color-text-secondary)]">Realtime</span>
              <AdminStatusPill tone={wsConnected ? 'emerald' : 'amber'}>{wsConnected ? 'WebSocket live' : 'Polling fallback'}</AdminStatusPill>
            </div>
            <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.62)] px-4 py-3 flex items-center justify-between">
              <span className="text-[var(--color-text-secondary)]">Offline Boards</span>
              <span className="font-semibold text-[var(--color-text)]">{metrics.offline}</span>
            </div>
            <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.62)] px-4 py-3 flex items-center justify-between">
              <span className="text-[var(--color-text-secondary)]">Observer Issues</span>
              <span className="font-semibold text-[var(--color-text)]">{metrics.observerIssues}</span>
            </div>
          </div>
        </AdminSection>
      </div>

      {updateNotification && (
        <AdminSection>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between" data-testid="update-notification-banner">
            <div className="flex items-start gap-3 min-w-0">
              <div className="mt-0.5 flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-400">
                <ArrowUpCircle className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium text-emerald-300">Neue Version verfügbar: v{updateNotification.latest_version}</p>
                  <AdminStatusPill tone="emerald">Update</AdminStatusPill>
                </div>
                <p className="mt-1 text-sm text-zinc-400">{updateNotification.latest_name || 'Neue Release Notes vorhanden.'}</p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {updateNotification.latest_body && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowChangelog((value) => !value)}
                  className="border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10"
                  data-testid="update-show-changelog-btn"
                >
                  <FileText className="w-3 h-3 mr-1" /> Release Notes
                </Button>
              )}
              <Button size="sm" onClick={() => navigate('/admin/system')} className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="update-go-to-updates-btn">
                <Settings className="w-3 h-3 mr-1" /> Update starten
              </Button>
              <Button variant="outline" size="sm" onClick={snoozeNotification} className="border-zinc-700 text-zinc-300 hover:text-white" data-testid="update-snooze-btn">
                <BellOff className="w-3 h-3 mr-1" /> Später
              </Button>
              <Button variant="ghost" size="icon" onClick={dismissNotification} className="text-zinc-500 hover:text-zinc-300 h-8 w-8" data-testid="update-dismiss-btn">
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>
          {showChangelog && updateNotification.latest_body && (
            <div className="mt-5 rounded-2xl border border-zinc-800 bg-zinc-950/80 p-4" data-testid="update-changelog-preview">
              <p className="text-xs uppercase tracking-[0.24em] text-zinc-500 mb-2">Release Notes</p>
              <pre className="max-h-56 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-zinc-400 font-sans">{updateNotification.latest_body}</pre>
            </div>
          )}
        </AdminSection>
      )}

      <AdminSection title="Mehr" description="Selten gebraucht, schnell erreichbar.">
        <div className="grid gap-3 md:grid-cols-3">
          <AdminLinkTile icon={TrendingUp} title="Umsatz" description="Tagesumsatz prüfen." onClick={() => navigate('/admin/revenue')} tone="emerald" cta="Öffnen" />
          <AdminLinkTile icon={FileText} title="Reports" description="Sessions & CSV." onClick={() => navigate('/admin/reports')} tone="blue" cta="Öffnen" />
          <AdminLinkTile icon={Settings} title="Einstellungen" description="Branding, Pricing, Kiosk." onClick={() => navigate('/admin/settings')} tone="amber" cta="Öffnen" />
        </div>
      </AdminSection>

      <Dialog open={showUnlockDialog} onOpenChange={setShowUnlockDialog}>
        <DialogContent className="border-[rgb(var(--color-border-rgb)/0.88)] bg-[rgb(var(--color-bg-rgb)/0.98)] p-0 text-[var(--color-text)] sm:max-w-xl overflow-hidden">
          <DialogHeader>
            <div className="border-b border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.6)] px-6 py-5">
              <DialogTitle className="font-heading uppercase tracking-[0.12em] text-[var(--color-text)]">
                {selectedBoard?.name} freischalten
              </DialogTitle>
              <p className="mt-2 text-sm text-[var(--color-text-secondary)]">Credits drauf, Board offen. Abbuchung kommt später beim echten Matchstart.</p>
            </div>
          </DialogHeader>

          <div className="space-y-5 px-6 py-5">
            <div className="grid grid-cols-4 gap-2">
              {[1, 2, 3, 4].map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setUnlockCredits(value)}
                  className={`h-12 rounded-2xl border text-sm font-semibold transition ${unlockCredits === value ? 'border-[rgb(var(--color-primary-rgb)/0.3)] bg-[rgb(var(--color-primary-rgb)/0.14)] text-[var(--color-primary)]' : 'border-[rgb(var(--color-border-rgb)/0.8)] bg-[rgb(var(--color-surface-rgb)/0.54)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'}`}
                >
                  {value}C
                </button>
              ))}
            </div>

            <div className="grid gap-3 sm:grid-cols-[1fr,1fr]">
              <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-4">
                <label className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">Credits</label>
                <Input type="number" min="1" value={unlockCredits} onChange={(e) => setUnlockCredits(parseInt(e.target.value || '1', 10))} data-testid="credits-input" className="mt-3 h-12 rounded-2xl border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.54)] text-center text-xl text-[var(--color-text)]" />
              </div>
              <div className="rounded-3xl border border-[rgb(var(--color-primary-rgb)/0.24)] bg-[rgb(var(--color-primary-rgb)/0.12)] p-4">
                <label className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-primary)]">Gesamt</label>
                <p className="mt-3 text-3xl font-semibold text-[var(--color-text)]" data-testid="total-price">{calculatePrice().toFixed(2)} €</p>
                <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{(pricing?.per_game?.price_per_credit || 2).toFixed(2)} € pro Credit</p>
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2 border-t border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.42)] px-6 py-4">
            <Button variant="outline" onClick={() => setShowUnlockDialog(false)} className="rounded-2xl border-[rgb(var(--color-border-rgb)/0.82)] text-[var(--color-text-secondary)]">Abbrechen</Button>
            <Button onClick={handleUnlock} data-testid="confirm-unlock-btn" className="rounded-2xl bg-[var(--color-primary)] text-[hsl(var(--primary-foreground))] hover:opacity-90">Freischalten</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showExtendDialog} onOpenChange={setShowExtendDialog}>
        <DialogContent className="border-[rgb(var(--color-border-rgb)/0.88)] bg-[rgb(var(--color-bg-rgb)/0.98)] text-[var(--color-text)] sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-heading uppercase tracking-[0.12em] text-white">
              {boardDetails[selectedBoard?.board_id]?.pricing_mode === 'per_time' ? 'Zeit verlängern' : 'Credits nachladen'} · {selectedBoard?.name}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6 py-4">
            <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-4 text-sm text-[var(--color-text-secondary)]">
              {selectedBoard ? formatRemaining(boardDetails[selectedBoard.board_id], selectedBoard.status) : 'Keine Session ausgewählt'}
            </div>
            {boardDetails[selectedBoard?.board_id]?.pricing_mode === 'per_time' ? (
              <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-4">
                <label className="text-xs uppercase tracking-[0.24em] text-[var(--color-text-muted)]">Zusätzliche Minuten</label>
                <Input type="number" min="0" step="15" value={unlockMinutes} onChange={(e) => setUnlockMinutes(parseInt(e.target.value || '0', 10))} className="mt-3 h-12 rounded-2xl border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.54)] text-center text-xl text-[var(--color-text)]" />
              </div>
            ) : (
              <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-4">
                <label className="text-xs uppercase tracking-[0.24em] text-[var(--color-text-muted)]">Zusätzliche Credits</label>
                <Input type="number" min="0" value={unlockCredits} onChange={(e) => setUnlockCredits(parseInt(e.target.value || '0', 10))} className="mt-3 h-12 rounded-2xl border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.54)] text-center text-xl text-[var(--color-text)]" />
              </div>
            )}
            <div className="rounded-2xl border border-[rgb(var(--color-primary-rgb)/0.24)] bg-[rgb(var(--color-primary-rgb)/0.12)] p-4">
              <label className="text-xs uppercase tracking-[0.24em] text-[var(--color-primary)]">Buchung</label>
              <p className="mt-2 text-3xl font-semibold text-[var(--color-text)]">
                {calculateExtendPrice(boardDetails[selectedBoard?.board_id], pricing, unlockCredits, unlockMinutes).toFixed(2)} €
              </p>
              <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
                Top-up wird jetzt auch im Umsatz mitgebucht.
              </p>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowExtendDialog(false)} className="rounded-2xl border-[rgb(var(--color-border-rgb)/0.82)] text-[var(--color-text-secondary)]">Abbrechen</Button>
            <Button onClick={handleExtend} data-testid="confirm-extend-btn" className="rounded-2xl bg-[var(--color-primary)] text-[hsl(var(--primary-foreground))] hover:opacity-90">
              {boardDetails[selectedBoard?.board_id]?.pricing_mode === 'per_time' ? 'Verlängern' : 'Credits nachladen'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AdminPage>
  );
}
