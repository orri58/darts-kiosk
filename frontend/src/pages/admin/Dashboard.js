import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { 
  Target, 
  Lock, 
  Unlock, 
  Play, 
  Wifi, 
  WifiOff, 
  Clock, 
  Coins,
  RefreshCw,
  Plus,
  Minus,
  ArrowUpCircle,
  X,
  FileText,
  Settings
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/dialog';
import { Input } from '../../components/ui/input';
import { useSettings } from '../../context/SettingsContext';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import { useBoardWS } from '../../hooks/useBoardWS';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_STYLES = {
  locked: { bg: 'bg-zinc-700/30', text: 'text-zinc-400', border: 'border-zinc-700', icon: Lock },
  unlocked: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500/50', icon: Unlock },
  in_game: { bg: 'bg-emerald-500/20', text: 'text-emerald-400', border: 'border-emerald-500/50', icon: Play },
  offline: { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/50', icon: WifiOff },
};

export default function AdminDashboard() {
  const { pricing } = useSettings();
  const { token } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [boards, setBoards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [observerStatuses, setObserverStatuses] = useState({});
  const [selectedBoard, setSelectedBoard] = useState(null);
  const [showUnlockDialog, setShowUnlockDialog] = useState(false);
  const [showExtendDialog, setShowExtendDialog] = useState(false);
  const [updateNotification, setUpdateNotification] = useState(null);
  const [showChangelog, setShowChangelog] = useState(false);
  
  // Unlock form state
  const [unlockMode, setUnlockMode] = useState('per_game');
  const [unlockCredits, setUnlockCredits] = useState(3);
  const [unlockMinutes, setUnlockMinutes] = useState(30);
  const [unlockPlayers, setUnlockPlayers] = useState(1);

  // Fetch boards
  const fetchBoards = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/boards`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBoards(response.data);
      // Fetch observer statuses for all boards
      try {
        const obsRes = await axios.get(`${API}/kiosk/observers/all`);
        const map = {};
        (obsRes.data.observers || []).forEach(o => { map[o.board_id] = o; });
        setObserverStatuses(map);
      } catch { /* observer endpoint may not exist yet */ }
    } catch (error) {
      console.error('Failed to fetch boards:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  // ---- WebSocket for real-time updates ----
  const onWsEvent = useCallback((event, data) => {
    if (event === 'board_status' || event === 'session_extended' || event === 'credit_update') {
      fetchBoards();
    }
  }, [fetchBoards]);
  const { connected: wsConnected } = useBoardWS(onWsEvent);

  useEffect(() => {
    fetchBoards();
    // Fallback poll every 30s only if WS is disconnected
    const interval = setInterval(() => {
      if (!wsConnected) fetchBoards();
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchBoards, wsConnected]);

  // Fetch update notification
  useEffect(() => {
    const fetchNotification = async () => {
      try {
        const res = await axios.get(`${API}/updates/notification`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        const data = res.data;
        if (data.update_available && data.dismissed_version !== data.latest_version) {
          setUpdateNotification(data);
        } else {
          setUpdateNotification(null);
        }
      } catch { /* silent */ }
    };
    fetchNotification();
    const iv = setInterval(fetchNotification, 300000); // re-check every 5 min
    return () => clearInterval(iv);
  }, [token]);

  const dismissNotification = async () => {
    if (!updateNotification) return;
    try {
      await axios.post(
        `${API}/updates/notification/dismiss?version=${updateNotification.latest_version}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } catch { /* silent */ }
    setUpdateNotification(null);
  };

  // Calculate price
  const calculatePrice = () => {
    if (unlockMode === 'per_game') {
      return unlockCredits * (pricing?.per_game?.price_per_credit || 2.0);
    }
    if (unlockMode === 'per_time') {
      if (unlockMinutes === 30) return pricing?.per_time?.price_per_30_min || 5.0;
      if (unlockMinutes === 60) return pricing?.per_time?.price_per_60_min || 8.0;
      return (unlockMinutes / 30) * (pricing?.per_time?.price_per_30_min || 5.0);
    }
    if (unlockMode === 'per_player') {
      return unlockPlayers * (pricing?.per_player?.price_per_player || 1.5);
    }
    return 0;
  };

  // Unlock board
  const handleUnlock = async () => {
    if (!selectedBoard) return;
    
    try {
      await axios.post(`${API}/boards/${selectedBoard.board_id}/unlock`, {
        pricing_mode: unlockMode,
        credits: unlockMode === 'per_game' ? unlockCredits : null,
        minutes: unlockMode === 'per_time' ? unlockMinutes : null,
        players_count: unlockPlayers,
        price_total: calculatePrice()
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success(`${selectedBoard.name} freigeschaltet!`);
      setShowUnlockDialog(false);
      fetchBoards();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Freischalten');
    }
  };

  // Lock board
  const handleLock = async (board) => {
    try {
      await axios.post(`${API}/boards/${board.board_id}/lock`, {}, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(`${board.name} gesperrt`);
      fetchBoards();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Sperren');
    }
  };

  // Extend session
  const handleExtend = async () => {
    if (!selectedBoard) return;
    
    try {
      await axios.post(`${API}/boards/${selectedBoard.board_id}/extend`, {
        credits: unlockMode === 'per_game' ? unlockCredits : null,
        minutes: unlockMode === 'per_time' ? unlockMinutes : null,
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      toast.success(`Session für ${selectedBoard.name} verlängert`);
      setShowExtendDialog(false);
      fetchBoards();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Verlängern');
    }
  };

  const openUnlockDialog = (board) => {
    setSelectedBoard(board);
    setUnlockMode(pricing?.mode || 'per_game');
    setUnlockCredits(pricing?.per_game?.default_credits || 3);
    setUnlockMinutes(30);
    setUnlockPlayers(1);
    setShowUnlockDialog(true);
  };

  const openExtendDialog = (board) => {
    setSelectedBoard(board);
    setUnlockMode('per_game');
    setUnlockCredits(1);
    setUnlockMinutes(15);
    setShowExtendDialog(true);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <div data-testid="admin-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-heading uppercase tracking-wider text-white">{t('dashboard')}</h1>
          <p className="text-zinc-500 flex items-center gap-2">
            {t('board_overview')}
            {wsConnected
              ? <span className="inline-flex items-center gap-1 text-xs text-emerald-500" data-testid="ws-status-connected"><Wifi className="w-3 h-3" /> Live</span>
              : <span className="inline-flex items-center gap-1 text-xs text-zinc-600" data-testid="ws-status-polling"><WifiOff className="w-3 h-3" /> Polling</span>
            }
          </p>
        </div>
        <Button
          onClick={fetchBoards}
          variant="outline"
          className="border-zinc-700 text-zinc-400 hover:text-white"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          {t('refresh')}
        </Button>
      </div>

      {/* Update Notification Banner */}
      {updateNotification && (
        <div
          className="mb-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-sm flex items-center justify-between gap-4"
          data-testid="update-notification-banner"
        >
          <div className="flex items-center gap-3 min-w-0">
            <ArrowUpCircle className="w-6 h-6 text-emerald-400 flex-shrink-0" />
            <div className="min-w-0">
              <p className="text-emerald-400 font-medium">
                Neue Version verfuegbar: v{updateNotification.latest_version}
              </p>
              {updateNotification.latest_name && (
                <p className="text-sm text-zinc-400 truncate">{updateNotification.latest_name}</p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {updateNotification.latest_body && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowChangelog(!showChangelog)}
                className="border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
                data-testid="update-show-changelog-btn"
              >
                <FileText className="w-3 h-3 mr-1" /> Release Notes
              </Button>
            )}
            <Button
              size="sm"
              onClick={() => navigate('/admin/system')}
              className="bg-emerald-600 hover:bg-emerald-700 text-white"
              data-testid="update-go-to-updates-btn"
            >
              <Settings className="w-3 h-3 mr-1" /> Update starten
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={dismissNotification}
              className="text-zinc-500 hover:text-zinc-300 h-8 w-8"
              data-testid="update-dismiss-btn"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Changelog Preview */}
      {showChangelog && updateNotification?.latest_body && (
        <div className="mb-6 p-4 bg-zinc-900 border border-zinc-800 rounded-sm" data-testid="update-changelog-preview">
          <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Release Notes - v{updateNotification.latest_version}</p>
          <pre className="text-sm text-zinc-400 whitespace-pre-wrap font-sans leading-relaxed max-h-48 overflow-y-auto">
            {updateNotification.latest_body}
          </pre>
        </div>
      )}

      {/* Board Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {boards.map((board) => {
          const statusStyle = STATUS_STYLES[board.status] || STATUS_STYLES.locked;
          const StatusIcon = statusStyle.icon;
          
          return (
            <Card key={board.id} className={`bg-zinc-900 border-2 ${statusStyle.border} transition-all`} data-testid={`board-card-${board.board_id}`}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-sm ${statusStyle.bg} flex items-center justify-center`}>
                      <Target className={`w-5 h-5 ${statusStyle.text}`} />
                    </div>
                    <div>
                      <CardTitle className="text-lg text-white">{board.name}</CardTitle>
                      <p className="text-xs text-zinc-500">{board.board_id}</p>
                    </div>
                  </div>
                  <div className={`flex items-center gap-2 px-3 py-1 rounded-sm ${statusStyle.bg}`}>
                    <StatusIcon className={`w-4 h-4 ${statusStyle.text}`} />
                    <span className={`text-xs uppercase font-medium ${statusStyle.text}`}>
                      {board.status === 'in_game' ? t('in_game_status') : 
                       board.status === 'unlocked' ? t('unlocked_status') :
                       board.status === 'offline' ? t('offline_status') : t('locked_status')}
                    </span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Location */}
                {board.location && (
                  <p className="text-sm text-zinc-500">
                    <span className="text-zinc-600">{t('location')}:</span> {board.location}
                  </p>
                )}

                {/* Observer Status */}
                {(() => {
                  const obs = observerStatuses[board.board_id];
                  if (!obs || obs.state === 'closed') return null;
                  const stateColors = {
                    idle: 'text-amber-400',
                    in_game: 'text-emerald-400',
                    finished: 'text-blue-400',
                    unknown: 'text-zinc-400',
                    error: 'text-red-400',
                  };
                  return (
                    <div className="bg-zinc-800/50 rounded-sm p-2 text-xs space-y-1" data-testid={`observer-status-${board.board_id}`}>
                      <div className="flex items-center justify-between">
                        <span className="text-zinc-500">Observer</span>
                        <span className={`uppercase font-medium ${stateColors[obs.state] || 'text-zinc-400'}`}>
                          {obs.state}
                        </span>
                      </div>
                      {obs.games_observed > 0 && (
                        <div className="flex items-center justify-between">
                          <span className="text-zinc-500">Spiele beobachtet</span>
                          <span className="text-zinc-300">{obs.games_observed}</span>
                        </div>
                      )}
                      {obs.last_error && (
                        <p className="text-red-400 truncate" title={obs.last_error}>
                          {obs.last_error}
                        </p>
                      )}
                    </div>
                  );
                })()}

                {/* Action Buttons */}
                <div className="flex gap-2">
                  {board.status === 'locked' ? (
                    <Button
                      onClick={() => openUnlockDialog(board)}
                      data-testid={`unlock-btn-${board.board_id}`}
                      className="flex-1 bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading tracking-wider"
                    >
                      <Unlock className="w-4 h-4 mr-2" />
                      {t('unlock_btn')}
                    </Button>
                  ) : (
                    <>
                      <Button
                        onClick={() => openExtendDialog(board)}
                        data-testid={`extend-btn-${board.board_id}`}
                        variant="outline"
                        className="flex-1 border-amber-500/50 text-amber-500 hover:bg-amber-500/20"
                      >
                        <Plus className="w-4 h-4 mr-2" />
                        {t('extend_btn')}
                      </Button>
                      <Button
                        onClick={() => handleLock(board)}
                        data-testid={`lock-btn-${board.board_id}`}
                        variant="outline"
                        className="flex-1 border-red-500/50 text-red-500 hover:bg-red-500/20"
                      >
                        <Lock className="w-4 h-4 mr-2" />
                        {t('lock_btn')}
                      </Button>
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Unlock Dialog */}
      <Dialog open={showUnlockDialog} onOpenChange={setShowUnlockDialog}>
        <DialogContent className="bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="font-heading uppercase tracking-wider text-white">
              {selectedBoard?.name} freischalten
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6 py-4">
            {/* Mode Selection */}
            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider">Abrechnungsart</label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  onClick={() => setUnlockMode('per_game')}
                  data-testid="mode-per-game"
                  className={`p-3 rounded-sm border-2 transition-all ${
                    unlockMode === 'per_game'
                      ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                      : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                  }`}
                >
                  <Coins className="w-5 h-5 mx-auto mb-1" />
                  <span className="text-xs uppercase">Pro Spiel</span>
                </button>
                <button
                  onClick={() => setUnlockMode('per_time')}
                  data-testid="mode-per-time"
                  className={`p-3 rounded-sm border-2 transition-all ${
                    unlockMode === 'per_time'
                      ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                      : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                  }`}
                >
                  <Clock className="w-5 h-5 mx-auto mb-1" />
                  <span className="text-xs uppercase">Pro Zeit</span>
                </button>
                <button
                  onClick={() => setUnlockMode('per_player')}
                  data-testid="mode-per-player"
                  className={`p-3 rounded-sm border-2 transition-all ${
                    unlockMode === 'per_player'
                      ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                      : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                  }`}
                >
                  <Target className="w-5 h-5 mx-auto mb-1" />
                  <span className="text-xs uppercase">Pro Spieler</span>
                </button>
              </div>
            </div>

            {/* Credits/Time/Players Input */}
            {unlockMode === 'per_game' && (
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Anzahl Spiele</label>
                <div className="flex items-center gap-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setUnlockCredits(Math.max(1, unlockCredits - 1))}
                    className="h-12 w-12 border-zinc-700"
                  >
                    <Minus className="w-5 h-5" />
                  </Button>
                  <Input
                    type="number"
                    value={unlockCredits}
                    onChange={(e) => setUnlockCredits(parseInt(e.target.value) || 1)}
                    min="1"
                    data-testid="credits-input"
                    className="input-industrial text-center text-2xl h-12"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setUnlockCredits(unlockCredits + 1)}
                    className="h-12 w-12 border-zinc-700"
                  >
                    <Plus className="w-5 h-5" />
                  </Button>
                </div>
              </div>
            )}

            {unlockMode === 'per_time' && (
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Zeit (Minuten)</label>
                <div className="grid grid-cols-3 gap-2">
                  {[30, 60, 90].map((mins) => (
                    <button
                      key={mins}
                      onClick={() => setUnlockMinutes(mins)}
                      className={`p-4 rounded-sm border-2 text-xl font-mono transition-all ${
                        unlockMinutes === mins
                          ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                          : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                      }`}
                    >
                      {mins} min
                    </button>
                  ))}
                </div>
              </div>
            )}

            {unlockMode === 'per_player' && (
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Anzahl Spieler</label>
                <div className="flex items-center gap-4">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setUnlockPlayers(Math.max(1, unlockPlayers - 1))}
                    className="h-12 w-12 border-zinc-700"
                  >
                    <Minus className="w-5 h-5" />
                  </Button>
                  <Input
                    type="number"
                    value={unlockPlayers}
                    onChange={(e) => setUnlockPlayers(parseInt(e.target.value) || 1)}
                    min="1"
                    max={pricing?.max_players || 4}
                    data-testid="players-input"
                    className="input-industrial text-center text-2xl h-12"
                  />
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setUnlockPlayers(Math.min(pricing?.max_players || 4, unlockPlayers + 1))}
                    className="h-12 w-12 border-zinc-700"
                  >
                    <Plus className="w-5 h-5" />
                  </Button>
                </div>
              </div>
            )}

            {/* Price Display */}
            <div className="bg-zinc-800 rounded-sm p-4 text-center">
              <p className="text-sm text-zinc-500 uppercase mb-2">Gesamtpreis</p>
              <p className="text-4xl font-mono font-bold text-amber-500" data-testid="total-price">
                {calculatePrice().toFixed(2)} €
              </p>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setShowUnlockDialog(false)}
              className="border-zinc-700"
            >
              Abbrechen
            </Button>
            <Button
              onClick={handleUnlock}
              data-testid="confirm-unlock-btn"
              className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading"
            >
              Freischalten
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Extend Dialog */}
      <Dialog open={showExtendDialog} onOpenChange={setShowExtendDialog}>
        <DialogContent className="bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="font-heading uppercase tracking-wider text-white">
              Session verlängern: {selectedBoard?.name}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">+ Spiele</label>
                <Input
                  type="number"
                  value={unlockCredits}
                  onChange={(e) => setUnlockCredits(parseInt(e.target.value) || 0)}
                  min="0"
                  className="input-industrial text-center text-xl"
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">+ Minuten</label>
                <Input
                  type="number"
                  value={unlockMinutes}
                  onChange={(e) => setUnlockMinutes(parseInt(e.target.value) || 0)}
                  min="0"
                  className="input-industrial text-center text-xl"
                />
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setShowExtendDialog(false)}
              className="border-zinc-700"
            >
              Abbrechen
            </Button>
            <Button
              onClick={handleExtend}
              data-testid="confirm-extend-btn"
              className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading"
            >
              Verlängern
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
