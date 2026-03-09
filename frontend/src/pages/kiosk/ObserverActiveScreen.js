import { useState, useEffect, useCallback } from 'react';
import { Target, Clock, Coins, Phone, StopCircle, Wifi, WifiOff, Activity } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { useSettings } from '../../context/SettingsContext';
import { useI18n } from '../../context/I18nContext';
import axios from 'axios';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ObserverActiveScreen({ branding, session, boardId, onEndGame, onCallStaff }) {
  const { kioskTexts } = useSettings();
  const { t } = useI18n();
  const [observerState, setObserverState] = useState('unknown');
  const [timeLeft, setTimeLeft] = useState(null);
  const [showConfirmEnd, setShowConfirmEnd] = useState(false);

  // Poll observer status
  const fetchObserver = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/kiosk/${boardId}/observer-status`);
      setObserverState(res.data.state || 'unknown');
    } catch { /* silent */ }
  }, [boardId]);

  useEffect(() => {
    fetchObserver();
    const iv = setInterval(fetchObserver, 5000);
    return () => clearInterval(iv);
  }, [fetchObserver]);

  // Timer for per_time mode
  useEffect(() => {
    if (session?.pricing_mode === 'per_time' && session?.expires_at) {
      const tick = () => {
        const diff = Math.max(0, new Date(session.expires_at) - new Date());
        if (diff <= 0) {
          setTimeLeft({ minutes: 0, seconds: 0 });
          return;
        }
        setTimeLeft({
          minutes: Math.floor(diff / 60000),
          seconds: Math.floor((diff % 60000) / 1000),
        });
      };
      tick();
      const iv = setInterval(tick, 1000);
      return () => clearInterval(iv);
    }
  }, [session]);

  const formatTime = (t) => t ? `${String(t.minutes).padStart(2, '0')}:${String(t.seconds).padStart(2, '0')}` : '--:--';

  const stateLabel = {
    idle: 'Bereit',
    in_game: 'Spiel laeuft',
    finished: 'Spiel beendet',
    closed: 'Nicht verbunden',
    error: 'Fehler',
    unknown: 'Unbekannt',
  };

  const stateColor = {
    idle: 'text-emerald-400',
    in_game: 'text-amber-400',
    finished: 'text-blue-400',
    closed: 'text-zinc-500',
    error: 'text-red-400',
    unknown: 'text-zinc-500',
  };

  const isConnected = observerState !== 'closed' && observerState !== 'error';

  return (
    <div className="h-full w-full flex flex-col bg-zinc-950" data-testid="observer-active-screen">
      {/* Header */}
      <div className="p-6 border-b border-zinc-800">
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <div>
            <h1 className="text-2xl font-heading font-bold uppercase tracking-wider text-white">
              {branding.cafe_name}
            </h1>
            <p className="text-sm text-zinc-500">{kioskTexts.welcome || 'Willkommen'}</p>
          </div>

          {/* Observer Status */}
          <div className={`flex items-center gap-2 border rounded-sm px-4 py-2 ${
            isConnected ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-red-500/10 border-red-500/30'
          }`}>
            {isConnected ? <Wifi className="w-4 h-4 text-emerald-400" /> : <WifiOff className="w-4 h-4 text-red-400" />}
            <span className={`text-sm font-heading uppercase tracking-wider ${stateColor[observerState] || 'text-zinc-500'}`}>
              {stateLabel[observerState] || observerState}
            </span>
          </div>
        </div>
      </div>

      {/* Main */}
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        {/* Central Message */}
        <div className="text-center mb-12">
          <Target className="w-20 h-20 text-amber-500 mx-auto mb-6" />
          <h2 className="text-4xl sm:text-5xl font-heading font-bold uppercase tracking-wider text-white mb-4">
            {observerState === 'in_game'
              ? (kioskTexts.game_running || 'Spiel laeuft')
              : 'Spiel starten'}
          </h2>
          <p className="text-lg text-zinc-400 max-w-xl mx-auto">
            {observerState === 'in_game'
              ? 'Viel Spass beim Spielen!'
              : 'Starte dein Spiel direkt in Autodarts. Credits werden automatisch verwaltet.'}
          </p>
        </div>

        {/* Session Info Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 w-full max-w-2xl mb-12">
          {session?.pricing_mode === 'per_game' ? (
            <div className="bg-zinc-900 border-2 border-amber-500/30 rounded-sm p-6 text-center">
              <Coins className="w-8 h-8 text-amber-500 mx-auto mb-2" />
              <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">{kioskTexts.credits_label || 'Spiele uebrig'}</p>
              <p className="text-5xl font-mono font-bold text-amber-500" data-testid="observer-credits">
                {session?.credits_remaining || 0}
              </p>
            </div>
          ) : (
            <div className={`bg-zinc-900 border-2 rounded-sm p-6 text-center ${
              timeLeft && timeLeft.minutes < 5 ? 'border-red-500/50' : 'border-amber-500/30'
            }`}>
              <Clock className={`w-8 h-8 mx-auto mb-2 ${timeLeft && timeLeft.minutes < 5 ? 'text-red-500' : 'text-amber-500'}`} />
              <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">{kioskTexts.time_label || 'Zeit uebrig'}</p>
              <p className={`text-5xl font-mono font-bold ${timeLeft && timeLeft.minutes < 5 ? 'text-red-500 animate-pulse' : 'text-amber-500'}`} data-testid="observer-time">
                {formatTime(timeLeft)}
              </p>
            </div>
          )}

          {/* Observer Activity */}
          <div className="bg-zinc-900 border-2 border-zinc-700 rounded-sm p-6 text-center">
            <Activity className={`w-8 h-8 mx-auto mb-2 ${observerState === 'in_game' ? 'text-amber-500 animate-pulse' : 'text-zinc-600'}`} />
            <p className="text-xs text-zinc-500 uppercase tracking-wider mb-1">Autodarts</p>
            <p className={`text-2xl font-heading font-bold uppercase ${stateColor[observerState] || 'text-zinc-500'}`} data-testid="observer-state-label">
              {stateLabel[observerState] || observerState}
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 w-full max-w-2xl">
          <Button
            onClick={onCallStaff}
            variant="outline"
            className="flex-1 h-16 text-xl bg-transparent border-2 border-zinc-700 text-zinc-300 hover:border-amber-500 hover:text-amber-500 uppercase font-heading tracking-wider"
            data-testid="observer-call-staff-btn"
          >
            <Phone className="w-6 h-6 mr-3" />
            {kioskTexts.call_staff || 'Personal rufen'}
          </Button>

          {!showConfirmEnd ? (
            <Button
              onClick={() => setShowConfirmEnd(true)}
              className="flex-1 h-16 text-xl bg-red-500/20 border-2 border-red-500/50 text-red-400 hover:bg-red-500 hover:text-white uppercase font-heading tracking-wider"
              data-testid="observer-end-session-btn"
            >
              <StopCircle className="w-6 h-6 mr-3" />
              Session beenden
            </Button>
          ) : (
            <div className="flex-1 flex gap-2">
              <Button
                onClick={() => setShowConfirmEnd(false)}
                variant="outline"
                className="flex-1 h-16 text-lg border-2 border-zinc-700 text-zinc-400 hover:text-white uppercase font-heading"
              >
                Abbrechen
              </Button>
              <Button
                onClick={onEndGame}
                className="flex-1 h-16 text-lg bg-red-500 text-white hover:bg-red-400 uppercase font-heading"
                data-testid="observer-confirm-end-btn"
              >
                Bestaetigen
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-zinc-800 bg-zinc-950/80">
        <p className="text-center text-zinc-600 text-sm">
          Credits werden automatisch abgezogen wenn ein Spiel erkannt wird
        </p>
      </div>
    </div>
  );
}
