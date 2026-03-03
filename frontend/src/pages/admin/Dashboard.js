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
  Minus
} from 'lucide-react';
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
  const [boards, setBoards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedBoard, setSelectedBoard] = useState(null);
  const [showUnlockDialog, setShowUnlockDialog] = useState(false);
  const [showExtendDialog, setShowExtendDialog] = useState(false);
  
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
    } catch (error) {
      console.error('Failed to fetch boards:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchBoards();
    const interval = setInterval(fetchBoards, 5000);
    return () => clearInterval(interval);
  }, [fetchBoards]);

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
          <h1 className="text-2xl font-heading uppercase tracking-wider text-white">Dashboard</h1>
          <p className="text-zinc-500">Board-Übersicht und Steuerung</p>
        </div>
        <Button
          onClick={fetchBoards}
          variant="outline"
          className="border-zinc-700 text-zinc-400 hover:text-white"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Aktualisieren
        </Button>
      </div>

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
                      {board.status === 'in_game' ? 'Im Spiel' : 
                       board.status === 'unlocked' ? 'Offen' :
                       board.status === 'offline' ? 'Offline' : 'Gesperrt'}
                    </span>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Location */}
                {board.location && (
                  <p className="text-sm text-zinc-500">
                    <span className="text-zinc-600">Standort:</span> {board.location}
                  </p>
                )}

                {/* Action Buttons */}
                <div className="flex gap-2">
                  {board.status === 'locked' ? (
                    <Button
                      onClick={() => openUnlockDialog(board)}
                      data-testid={`unlock-btn-${board.board_id}`}
                      className="flex-1 bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading tracking-wider"
                    >
                      <Unlock className="w-4 h-4 mr-2" />
                      Freischalten
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
                        Verlängern
                      </Button>
                      <Button
                        onClick={() => handleLock(board)}
                        data-testid={`lock-btn-${board.board_id}`}
                        variant="outline"
                        className="flex-1 border-red-500/50 text-red-500 hover:bg-red-500/20"
                      >
                        <Lock className="w-4 h-4 mr-2" />
                        Sperren
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
