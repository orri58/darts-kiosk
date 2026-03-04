import { useState, useEffect, useCallback } from 'react';
import { Lock, QrCode, Euro, Shield, Trophy, Crown } from 'lucide-react';

function TopPlayersRotation() {
  const [players, setPlayers] = useState([]);
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const fetchTop = async () => {
      try {
        const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/stats/top-today?limit=5`);
        if (res.ok) {
          const data = await res.json();
          setPlayers(data.players || []);
        }
      } catch { /* ignore */ }
    };
    fetchTop();
    const iv = setInterval(fetchTop, 60000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (players.length <= 1) return;
    const iv = setInterval(() => setCurrent((c) => (c + 1) % players.length), 5000);
    return () => clearInterval(iv);
  }, [players.length]);

  if (players.length === 0) return null;
  const p = players[current];

  return (
    <div className="flex items-center gap-3 px-5 py-3 bg-zinc-800/50 border border-zinc-700 rounded-sm" data-testid="top-players-rotation">
      <Crown className="w-5 h-5 text-amber-500 flex-shrink-0" />
      <div className="min-w-0">
        <p className="text-[11px] text-zinc-500 uppercase tracking-wider">Top Spieler heute</p>
        <div className="flex items-center gap-2">
          <span className="text-lg font-mono font-bold text-amber-400 truncate" data-testid="top-player-name">{p.nickname}</span>
          <span className="text-xs text-zinc-500">{p.games_won}W / {p.games_played}G</span>
        </div>
      </div>
      {players.length > 1 && (
        <div className="flex gap-1 ml-auto">
          {players.map((_, i) => (
            <div key={i} className={`w-1.5 h-1.5 rounded-full ${i === current ? 'bg-amber-500' : 'bg-zinc-700'}`} />
          ))}
        </div>
      )}
    </div>
  );
}

function PairingCode({ boardId }) {
  const [code, setCode] = useState('------');
  const [remaining, setRemaining] = useState(0);

  const fetchCode = useCallback(async () => {
    try {
      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/agent/pair/code`);
      if (res.ok) {
        const data = await res.json();
        setCode(data.code);
        setRemaining(data.expires_in);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => {
    fetchCode();
    const iv = setInterval(fetchCode, 5000);
    return () => clearInterval(iv);
  }, [fetchCode]);

  useEffect(() => {
    if (remaining <= 0) return;
    const iv = setInterval(() => setRemaining((r) => Math.max(0, r - 1)), 1000);
    return () => clearInterval(iv);
  }, [remaining]);

  const pct = Math.max(0, (remaining / 60) * 100);

  return (
    <div className="flex items-center gap-4 px-5 py-3 bg-zinc-800/50 border border-zinc-700 rounded-sm" data-testid="pairing-code-display">
      <Shield className="w-5 h-5 text-amber-500 flex-shrink-0" />
      <div>
        <p className="text-[11px] text-zinc-500 uppercase tracking-wider">Pairing-Code</p>
        <p className="text-2xl font-mono font-bold tracking-[0.3em] text-amber-400" data-testid="pairing-code-value">{code}</p>
      </div>
      <div className="w-12 h-1 bg-zinc-700 rounded-full overflow-hidden ml-auto">
        <div className="h-full bg-amber-500 transition-all duration-1000 ease-linear" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function LockedScreen({ branding, pricing, boardId }) {
  // Format price for display
  const formatPrice = (amount, currency = 'EUR') => {
    return `${amount.toFixed(2)} ${currency}`;
  };

  return (
    <div className="h-full w-full flex flex-col texture-overlay" data-testid="locked-screen">
      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center justify-center relative z-10 px-8">
        {/* Logo / Cafe Name */}
        <div className="text-center mb-12">
          {branding.logo_url ? (
            <img 
              src={branding.logo_url} 
              alt={branding.cafe_name}
              className="h-24 w-auto mx-auto mb-6"
            />
          ) : (
            <div className="mb-4">
              <h1 className="text-6xl font-heading font-bold uppercase tracking-wider text-white">
                {branding.cafe_name}
              </h1>
              {branding.subtitle && (
                <p className="text-xl text-zinc-400 mt-2">{branding.subtitle}</p>
              )}
            </div>
          )}
        </div>

        {/* Lock Icon with Glow */}
        <div className="relative mb-12">
          <div className="w-32 h-32 rounded-full bg-zinc-900 border-4 border-zinc-700 flex items-center justify-center">
            <Lock className="w-16 h-16 text-zinc-500" strokeWidth={2.5} />
          </div>
          <div className="absolute inset-0 rounded-full bg-zinc-700/20 blur-xl -z-10"></div>
        </div>

        {/* Lock Message */}
        <div className="text-center mb-16">
          <h2 className="text-4xl font-heading font-bold uppercase tracking-wider text-zinc-300 mb-4" data-testid="locked-message">
            GESPERRT
          </h2>
          <p className="text-2xl text-zinc-500">
            Bitte an der Theke freischalten lassen
          </p>
        </div>

        {/* Pricing Info */}
        <div className="w-full max-w-2xl" data-testid="pricing-info">
          <div className="bg-zinc-900/80 border-2 border-zinc-800 rounded-sm p-8">
            <div className="flex items-center gap-3 mb-6">
              <Euro className="w-6 h-6 text-amber-500" />
              <h3 className="text-xl font-heading uppercase tracking-wider text-zinc-300">
                Preise
              </h3>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Per Game */}
              <div className="text-center p-4 bg-zinc-800/50 rounded-sm border border-zinc-700">
                <p className="text-zinc-500 uppercase text-sm mb-2">Pro Spiel</p>
                <p className="text-3xl font-mono font-bold text-white">
                  {formatPrice(pricing.per_game?.price_per_credit || 2.0)}
                </p>
              </div>

              {/* Per 30 Min */}
              <div className="text-center p-4 bg-zinc-800/50 rounded-sm border border-zinc-700">
                <p className="text-zinc-500 uppercase text-sm mb-2">30 Minuten</p>
                <p className="text-3xl font-mono font-bold text-white">
                  {formatPrice(pricing.per_time?.price_per_30_min || 5.0)}
                </p>
              </div>

              {/* Per 60 Min */}
              <div className="text-center p-4 bg-zinc-800/50 rounded-sm border border-zinc-700">
                <p className="text-zinc-500 uppercase text-sm mb-2">60 Minuten</p>
                <p className="text-3xl font-mono font-bold text-white">
                  {formatPrice(pricing.per_time?.price_per_60_min || 8.0)}
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Top Players of the Day */}
      <div className="relative z-10 px-6 pb-4">
        <div className="max-w-4xl mx-auto">
          <TopPlayersRotation />
        </div>
      </div>

      {/* Footer */}
      <div className="relative z-10 p-6 border-t border-zinc-800 bg-zinc-950/80">
        <div className="flex items-center justify-between max-w-4xl mx-auto">
          <div className="flex items-center gap-3 text-zinc-600">
            <QrCode className="w-5 h-5" />
            <span className="text-sm uppercase tracking-wider">Board: {boardId}</span>
          </div>
          <PairingCode boardId={boardId} />
          <div className="text-zinc-600 text-sm">
            Staff Panel: <span className="font-mono">/admin</span>
          </div>
        </div>
      </div>
    </div>
  );
}
