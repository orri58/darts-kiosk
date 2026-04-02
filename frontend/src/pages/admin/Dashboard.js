import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  AlertTriangle,
  ArrowUpCircle,
  BellOff,
  Clock3,
  ExternalLink,
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
  AdminEmptyState,
  AdminLinkTile,
  AdminMiniAction,
  AdminPage,
  AdminSection,
  AdminStatCard,
  AdminStatsGrid,
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
  if (session.pricing_mode === 'per_game') {
    return `${session.credits_remaining} / ${session.credits_total} Spiele übrig`;
  }
  if (session.pricing_mode === 'per_player') {
    const requiredPlayers = session.players_count || session.players?.length || 1;
    const shortage = Math.max(0, requiredPlayers - (session.credits_remaining || 0));
    if (boardStatus === 'blocked_pending') {
      return `${session.credits_remaining} Credits da, ${shortage} fehlen für ${requiredPlayers} Spieler`;
    }
    return `${session.credits_remaining} Credits Rest · ${requiredPlayers} Spieler im Match`;
  }
  if (session.pricing_mode === 'per_time' && session.expires_at) {
    const diffMs = Math.max(0, new Date(session.expires_at).getTime() - Date.now());
    const minutes = Math.ceil(diffMs / 60000);
    return `${minutes} min Restzeit`;
  }
  return 'Aktive Session';
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

  const [unlockMode, setUnlockMode] = useState('per_game');
  const [unlockCredits, setUnlockCredits] = useState(3);
  const [unlockMinutes, setUnlockMinutes] = useState(30);
  const [unlockPlayers, setUnlockPlayers] = useState(2);

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
    if (unlockMode === 'per_game') {
      return unlockCredits * (pricing?.per_game?.price_per_credit || 2.0);
    }
    if (unlockMode === 'per_time') {
      if (unlockMinutes === 30) return pricing?.per_time?.price_per_30_min || 5.0;
      if (unlockMinutes === 60) return pricing?.per_time?.price_per_60_min || 8.0;
      return (unlockMinutes / 30) * (pricing?.per_time?.price_per_30_min || 5.0);
    }
    return 0;
  };

  const handleUnlock = async () => {
    if (!selectedBoard) return;

    try {
      await axios.post(
        `${API}/boards/${selectedBoard.board_id}/unlock`,
        {
          pricing_mode: unlockMode,
          credits: unlockMode === 'per_game' ? unlockCredits : null,
          minutes: unlockMode === 'per_time' ? unlockMinutes : null,
          players_count: unlockPlayers,
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
      await axios.post(
        `${API}/boards/${selectedBoard.board_id}/extend`,
        {
          credits: unlockMode === 'per_game' ? unlockCredits : null,
          minutes: unlockMode === 'per_time' ? unlockMinutes : null,
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
    setUnlockMode(pricing?.mode === 'per_time' ? 'per_time' : 'per_game');
    setUnlockCredits(pricing?.per_game?.default_credits || 3);
    setUnlockMinutes(30);
    setUnlockPlayers(2);
    setShowUnlockDialog(true);
  };

  const openExtendDialog = (board) => {
    const session = boardDetails[board.board_id];
    setSelectedBoard(board);
    setUnlockMode(session?.pricing_mode === 'per_time' ? 'per_time' : 'per_game');
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <AdminPage
      eyebrow="Local operations"
      title={t('dashboard')}
      description="Live-Überblick für Venue-Betrieb: Board-Status, Session-Kontext, Observer-Auffälligkeiten und die direkten Eingriffe, die man am Tresen wirklich braucht."
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
      <AdminStatsGrid>
        <AdminStatCard icon={Target} label="Boards gesamt" value={metrics.total} hint="Alle lokal bekannten Spielplätze" tone="amber" />
        <AdminStatCard icon={Unlock} label="Bereit / aktiv" value={metrics.live} hint="Freigeschaltet oder gerade im Spiel" tone="emerald" />
        <AdminStatCard icon={Play} label="Aktive Matches" value={metrics.inGame} hint="Boards mit laufendem Spiel" tone="blue" />
        <AdminStatCard icon={AlertTriangle} label="Auffälligkeiten" value={metrics.offline + metrics.observerIssues} hint={`${metrics.offline} offline · ${metrics.observerIssues} Observer`} tone={metrics.offline + metrics.observerIssues > 0 ? 'red' : 'neutral'} />
      </AdminStatsGrid>

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

      <div className="grid gap-6 xl:grid-cols-[1.4fr,0.8fr]">
        <AdminSection title="Board-Übersicht" description="Jedes Board mit Status, Session-Kontext und Direktaktionen für den Operator.">
          {boards.length === 0 ? (
            <AdminEmptyState
              icon={Target}
              title="Noch keine Boards vorhanden"
              description="Lege zuerst mindestens ein Board an, damit Unlocks, Kiosk und lokale Umsatzlogik sinnvoll greifen."
              action={
                <Button onClick={() => navigate('/admin/boards')} className="bg-amber-500 text-black hover:bg-amber-400">
                  <Plus className="w-4 h-4 mr-2" /> Boards öffnen
                </Button>
              }
            />
          ) : (
            <div className="space-y-4">
              {boards.map((board) => {
                const status = STATUS_STYLES[board.status] || STATUS_STYLES.locked;
                const StatusIcon = status.icon;
                const session = boardDetails[board.board_id];
                const observer = observerStatuses[board.board_id];
                const kioskHref = `/kiosk/${board.board_id}`;

                return (
                  <div key={board.id} className="rounded-3xl border border-zinc-800 bg-zinc-900/60 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]" data-testid={`board-card-${board.board_id}`}>
                    <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-xl font-semibold text-white">{board.name}</p>
                          <AdminStatusPill tone={status.tone}>
                            <StatusIcon className="w-3 h-3" /> {status.label}
                          </AdminStatusPill>
                          {board.is_master && <AdminStatusPill tone="amber">Master</AdminStatusPill>}
                          {observer?.state && observer.state !== 'closed' && (
                            <AdminStatusPill tone={observer.state === 'error' ? 'red' : observer.state === 'in_game' ? 'emerald' : 'blue'}>
                              Observer {observer.state}
                            </AdminStatusPill>
                          )}
                        </div>
                        <p className="mt-1 text-sm text-zinc-500 font-mono">{board.board_id}</p>
                        <div className="mt-3 grid gap-2 text-sm text-zinc-400 md:grid-cols-2">
                          <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-3 py-2">
                            <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Standort</p>
                            <p className="mt-1 text-zinc-200">{board.location || 'Nicht hinterlegt'}</p>
                          </div>
                          <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-3 py-2">
                            <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Session-Kontext</p>
                            <p className="mt-1 text-zinc-200">{session ? (session.pricing_mode === 'per_time' ? 'Zeitbasiert' : session.pricing_mode === 'per_player' ? 'Spielerbasiert' : 'Spielbasiert') : 'Keine aktive Session'}</p>
                            <p className="text-xs text-zinc-500 mt-1">{formatRemaining(session, board.status)}</p>
                          </div>
                        </div>
                        {observer?.last_error && (
                          <div className="mt-3 rounded-2xl border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-100">
                            <span className="font-medium">Observer-Hinweis:</span> {observer.last_error}
                          </div>
                        )}
                      </div>

                      <div className="flex flex-col gap-2 lg:min-w-[220px]">
                        <Button asChild variant="outline" className="justify-between border-zinc-700 text-zinc-200 hover:text-white">
                          <a href={kioskHref} target="_blank" rel="noreferrer">
                            Kiosk öffnen <ExternalLink className="w-4 h-4" />
                          </a>
                        </Button>
                        {board.status === 'locked' ? (
                          <Button onClick={() => openUnlockDialog(board)} data-testid={`unlock-btn-${board.board_id}`} className="bg-amber-500 hover:bg-amber-400 text-black">
                            <Unlock className="w-4 h-4 mr-2" /> Freischalten
                          </Button>
                        ) : (
                          <>
                            <Button onClick={() => openExtendDialog(board)} data-testid={`extend-btn-${board.board_id}`} variant="outline" className="border-amber-500/40 text-amber-300 hover:bg-amber-500/10">
                              <Plus className="w-4 h-4 mr-2" /> Verlängern
                            </Button>
                            <Button onClick={() => handleLock(board)} data-testid={`lock-btn-${board.board_id}`} variant="outline" className="border-red-500/40 text-red-300 hover:bg-red-500/10">
                              <Lock className="w-4 h-4 mr-2" /> Sperren
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </AdminSection>

        <div className="space-y-6">
          <AdminSection title="Schnellzugriffe" description="Weniger Suchen, mehr Operator-Flow.">
            <div className="space-y-3">
              <AdminLinkTile icon={TrendingUp} title="Revenue" description="Tagesumsatz, Board-Verteilung und Verlauf im Venue-Modus prüfen." onClick={() => navigate('/admin/revenue')} tone="emerald" cta="Zur Umsatzansicht" />
              <AdminLinkTile icon={FileText} title="Reports" description="Sessionlisten, Abrechnungsfenster und CSV-Export für die Nacharbeit." onClick={() => navigate('/admin/reports')} tone="blue" cta="Zu Reports" />
              <AdminLinkTile icon={Settings} title="Settings" description="Branding, Pricing, Trigger-Policy und Kiosk-Verhalten konsolidiert pflegen." onClick={() => navigate('/admin/settings')} tone="amber" cta="Zu Settings" />
            </div>
          </AdminSection>

          <AdminSection title="Betriebsstatus" description="Lokal-first Signals für die Lageeinschätzung.">
            <div className="space-y-3 text-sm">
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3 flex items-center justify-between">
                <span className="text-zinc-400">Realtime-Transport</span>
                <AdminStatusPill tone={wsConnected ? 'emerald' : 'amber'}>{wsConnected ? 'WebSocket live' : 'Polling fallback'}</AdminStatusPill>
              </div>
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3 flex items-center justify-between">
                <span className="text-zinc-400">Offline Boards</span>
                <span className="font-semibold text-white">{metrics.offline}</span>
              </div>
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3 flex items-center justify-between">
                <span className="text-zinc-400">Observer Issues</span>
                <span className="font-semibold text-white">{metrics.observerIssues}</span>
              </div>
            </div>
          </AdminSection>
        </div>
      </div>

      <Dialog open={showUnlockDialog} onOpenChange={setShowUnlockDialog}>
        <DialogContent className="bg-zinc-950 border-zinc-800 text-white sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle className="font-heading uppercase tracking-[0.12em] text-white">
              {selectedBoard?.name} freischalten
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6 py-4">
            <div className="grid gap-3 md:grid-cols-2">
              <button
                type="button"
                onClick={() => setUnlockMode('per_game')}
                data-testid="mode-per-game"
                className={`rounded-2xl border p-4 text-left transition ${unlockMode === 'per_game' ? 'border-amber-500/40 bg-amber-500/10 text-amber-200' : 'border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:border-zinc-700'}`}
              >
                <p className="font-medium">Pro Spiel</p>
                <p className="mt-1 text-sm text-zinc-500">Direkt für Credits / Spiele verkaufen.</p>
              </button>
              <button
                type="button"
                onClick={() => setUnlockMode('per_time')}
                data-testid="mode-per-time"
                className={`rounded-2xl border p-4 text-left transition ${unlockMode === 'per_time' ? 'border-amber-500/40 bg-amber-500/10 text-amber-200' : 'border-zinc-800 bg-zinc-900/60 text-zinc-400 hover:border-zinc-700'}`}
              >
                <p className="font-medium">Pro Zeit</p>
                <p className="mt-1 text-sm text-zinc-500">Sinnvoll für offene Spielphasen mit Timer.</p>
              </button>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              {unlockMode === 'per_game' ? (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
                  <label className="text-xs uppercase tracking-[0.24em] text-zinc-500">Spiele</label>
                  <Input type="number" min="1" value={unlockCredits} onChange={(e) => setUnlockCredits(parseInt(e.target.value || '1', 10))} data-testid="credits-input" className="mt-3 bg-zinc-950 border-zinc-700 text-white text-center text-2xl h-14" />
                </div>
              ) : (
                <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
                  <label className="text-xs uppercase tracking-[0.24em] text-zinc-500">Minuten</label>
                  <Input type="number" min="15" step="15" value={unlockMinutes} onChange={(e) => setUnlockMinutes(parseInt(e.target.value || '15', 10))} className="mt-3 bg-zinc-950 border-zinc-700 text-white text-center text-2xl h-14" />
                </div>
              )}
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
                <label className="text-xs uppercase tracking-[0.24em] text-zinc-500">Spielerzahl</label>
                <Input type="number" min="1" max="8" value={unlockPlayers} onChange={(e) => setUnlockPlayers(parseInt(e.target.value || '1', 10))} data-testid="players-input" className="mt-3 bg-zinc-950 border-zinc-700 text-white text-center text-2xl h-14" />
              </div>
              <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 p-4">
                <label className="text-xs uppercase tracking-[0.24em] text-amber-300">Gesamtpreis</label>
                <p className="mt-3 text-3xl font-semibold text-white" data-testid="total-price">{calculatePrice().toFixed(2)} €</p>
                <p className="mt-1 text-sm text-amber-100/70">Direkt aus lokalem Pricing abgeleitet.</p>
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowUnlockDialog(false)} className="border-zinc-700 text-zinc-300">Abbrechen</Button>
            <Button onClick={handleUnlock} data-testid="confirm-unlock-btn" className="bg-amber-500 hover:bg-amber-400 text-black">Freischalten</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={showExtendDialog} onOpenChange={setShowExtendDialog}>
        <DialogContent className="bg-zinc-950 border-zinc-800 text-white sm:max-w-xl">
          <DialogHeader>
            <DialogTitle className="font-heading uppercase tracking-[0.12em] text-white">
              Session verlängern · {selectedBoard?.name}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6 py-4">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4 text-sm text-zinc-400">
              {selectedBoard ? formatRemaining(boardDetails[selectedBoard.board_id]) : 'Keine Session ausgewählt'}
            </div>
            {unlockMode === 'per_game' ? (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
                <label className="text-xs uppercase tracking-[0.24em] text-zinc-500">Zusätzliche Spiele</label>
                <Input type="number" min="0" value={unlockCredits} onChange={(e) => setUnlockCredits(parseInt(e.target.value || '0', 10))} className="mt-3 bg-zinc-950 border-zinc-700 text-white text-center text-2xl h-14" />
              </div>
            ) : (
              <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4">
                <label className="text-xs uppercase tracking-[0.24em] text-zinc-500">Zusätzliche Minuten</label>
                <Input type="number" min="0" step="15" value={unlockMinutes} onChange={(e) => setUnlockMinutes(parseInt(e.target.value || '0', 10))} className="mt-3 bg-zinc-950 border-zinc-700 text-white text-center text-2xl h-14" />
              </div>
            )}
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowExtendDialog(false)} className="border-zinc-700 text-zinc-300">Abbrechen</Button>
            <Button onClick={handleExtend} data-testid="confirm-extend-btn" className="bg-amber-500 hover:bg-amber-400 text-black">Verlängern</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AdminPage>
  );
}
