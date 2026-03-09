import { useState, useEffect } from 'react';
import { Target, Clock, Coins, Phone, StopCircle, Users } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { useSettings } from '../../context/SettingsContext';

export default function InGameScreen({ branding, session, onEndGame, onCallStaff }) {
  const [timeLeft, setTimeLeft] = useState(null);
  const [showConfirmEnd, setShowConfirmEnd] = useState(false);
  const { kioskTexts } = useSettings();

  // Calculate time remaining for per_time mode
  useEffect(() => {
    if (session?.pricing_mode === 'per_time' && session?.expires_at) {
      const updateTime = () => {
        const expiresAt = new Date(session.expires_at);
        const now = new Date();
        const diff = Math.max(0, expiresAt - now);
        
        if (diff <= 0) {
          setTimeLeft({ minutes: 0, seconds: 0 });
          // Auto-end when time expires
          onEndGame();
          return;
        }
        
        setTimeLeft({
          minutes: Math.floor(diff / 60000),
          seconds: Math.floor((diff % 60000) / 1000)
        });
      };

      updateTime();
      const interval = setInterval(updateTime, 1000);
      return () => clearInterval(interval);
    }
  }, [session, onEndGame]);

  const formatTime = (time) => {
    if (!time) return '--:--';
    return `${String(time.minutes).padStart(2, '0')}:${String(time.seconds).padStart(2, '0')}`;
  };

  return (
    <div className="h-full w-full flex flex-col bg-zinc-950" data-testid="in-game-screen">
      {/* Header */}
      <div className="p-6 border-b border-zinc-800">
        <div className="flex items-center justify-between max-w-6xl mx-auto">
          <div>
            <h1 className="text-2xl font-heading font-bold uppercase tracking-wider text-white">
              {branding.cafe_name}
            </h1>
          </div>
          
          {/* Status Indicator */}
          <div className="flex items-center gap-2 bg-emerald-500/20 text-emerald-400 border border-emerald-500/50 rounded-sm px-4 py-2">
            <div className="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></div>
            <span className="font-heading uppercase tracking-wider">{kioskTexts.game_running || 'SPIEL LÄUFT'}</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center justify-center p-8">
        {/* Game Type */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-4 mb-4">
            <Target className="w-12 h-12 text-amber-500" />
            <h2 className="text-6xl font-heading font-bold uppercase text-white">
              {session?.game_type || 'DART'}
            </h2>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl mb-12">
          {/* Players */}
          <div className="bg-zinc-900 border-2 border-zinc-800 rounded-sm p-6 text-center">
            <div className="flex items-center justify-center gap-2 mb-3">
              <Users className="w-6 h-6 text-zinc-500" />
              <span className="text-sm text-zinc-500 uppercase tracking-wider">Spieler</span>
            </div>
            <div className="space-y-2">
              {session?.players?.map((player, index) => (
                <p key={index} className="text-xl font-mono text-white">
                  {player}
                </p>
              )) || <p className="text-zinc-600">-</p>}
            </div>
          </div>

          {/* Credits or Time Remaining */}
          {session?.pricing_mode === 'per_game' ? (
            <div className="bg-zinc-900 border-2 border-amber-500/30 rounded-sm p-6 text-center">
              <div className="flex items-center justify-center gap-2 mb-3">
                <Coins className="w-6 h-6 text-amber-500" />
                <span className="text-sm text-zinc-500 uppercase tracking-wider">{kioskTexts.credits_label || 'Spiele übrig'}</span>
              </div>
              <p className="text-5xl font-mono font-bold text-amber-500" data-testid="credits-remaining">
                {session?.credits_remaining || 0}
              </p>
            </div>
          ) : (
            <div className={`bg-zinc-900 border-2 rounded-sm p-6 text-center ${timeLeft?.minutes < 5 ? 'border-red-500/50' : 'border-amber-500/30'}`}>
              <div className="flex items-center justify-center gap-2 mb-3">
                <Clock className={`w-6 h-6 ${timeLeft?.minutes < 5 ? 'text-red-500' : 'text-amber-500'}`} />
                <span className="text-sm text-zinc-500 uppercase tracking-wider">{kioskTexts.time_label || 'Zeit übrig'}</span>
              </div>
              <p className={`text-5xl font-mono font-bold ${timeLeft?.minutes < 5 ? 'text-red-500 animate-pulse' : 'text-amber-500'}`} data-testid="time-remaining">
                {formatTime(timeLeft)}
              </p>
            </div>
          )}

          {/* Total Games / Price */}
          <div className="bg-zinc-900 border-2 border-zinc-800 rounded-sm p-6 text-center">
            <div className="flex items-center justify-center gap-2 mb-3">
              <span className="text-sm text-zinc-500 uppercase tracking-wider">
                {session?.pricing_mode === 'per_game' ? 'Gekaufte Spiele' : 'Bezahlte Zeit'}
              </span>
            </div>
            <p className="text-3xl font-mono font-bold text-white">
              {session?.pricing_mode === 'per_game' 
                ? session?.credits_total 
                : `${session?.minutes_total || 0} min`
              }
            </p>
            <p className="text-lg text-zinc-500 mt-1 font-mono">
              {session?.price_total?.toFixed(2)} EUR
            </p>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 w-full max-w-2xl">
          {/* Call Staff */}
          <Button
            onClick={onCallStaff}
            data-testid="call-staff-btn"
            variant="outline"
            className="flex-1 h-20 text-xl bg-transparent border-2 border-zinc-700 text-zinc-300 hover:border-amber-500 hover:text-amber-500 uppercase font-heading tracking-wider"
          >
            <Phone className="w-6 h-6 mr-3" />
            {kioskTexts.call_staff || 'Personal rufen'}
          </Button>

          {/* End Game (Manual) */}
          {!showConfirmEnd ? (
            <Button
              onClick={() => setShowConfirmEnd(true)}
              data-testid="end-game-btn"
              className="flex-1 h-20 text-xl bg-red-500/20 border-2 border-red-500/50 text-red-400 hover:bg-red-500 hover:text-white uppercase font-heading tracking-wider"
            >
              <StopCircle className="w-6 h-6 mr-3" />
              Spiel beenden
            </Button>
          ) : (
            <div className="flex-1 flex gap-2">
              <Button
                onClick={() => setShowConfirmEnd(false)}
                variant="outline"
                className="flex-1 h-20 text-lg border-2 border-zinc-700 text-zinc-400 hover:text-white uppercase font-heading"
              >
                Abbrechen
              </Button>
              <Button
                onClick={onEndGame}
                data-testid="confirm-end-game-btn"
                className="flex-1 h-20 text-lg bg-red-500 text-white hover:bg-red-400 uppercase font-heading"
              >
                Bestätigen
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-zinc-800 bg-zinc-950/80">
        <p className="text-center text-zinc-600 text-sm">
          Spiel wird automatisch beendet wenn Zeit/Credits aufgebraucht sind
        </p>
      </div>
    </div>
  );
}
