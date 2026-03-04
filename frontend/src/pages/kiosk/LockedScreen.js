import { useState, useEffect, useCallback } from 'react';
import { Lock, QrCode, Euro, Shield, Trophy, Crown, ShieldCheck, Target } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function TopPlayersRotation() {
  const [players, setPlayers] = useState([]);
  const [current, setCurrent] = useState(0);

  useEffect(() => {
    const fetchTop = async () => {
      try {
        const res = await fetch(`${API}/stats/top-today?limit=5`);
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

function TopStammkundenRotation() {
  const [data, setData] = useState(null);
  const [config, setConfig] = useState(null);
  const [current, setCurrent] = useState(0);
  const [fade, setFade] = useState(true);

  // Fetch config + top registered players
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [configRes, dataRes] = await Promise.all([
          fetch(`${API}/settings/stammkunde-display`),
          fetch(`${API}/stats/top-registered?period=month&limit=3`),
        ]);
        if (configRes.ok) {
          const cfg = await configRes.json();
          setConfig(cfg);
          // Re-fetch with correct period if needed
          if (cfg.period !== 'month' || cfg.max_entries !== 3) {
            const updated = await fetch(`${API}/stats/top-registered?period=${cfg.period}&limit=${cfg.max_entries || 3}`);
            if (updated.ok) setData(await updated.json());
          } else if (dataRes.ok) {
            setData(await dataRes.json());
          }
        } else if (dataRes.ok) {
          setData(await dataRes.json());
        }
      } catch { /* silent */ }
    };
    fetchData();
    const iv = setInterval(fetchData, 60000); // Re-fetch every 60s
    return () => clearInterval(iv);
  }, []);

  // Rotation timer with fade
  useEffect(() => {
    const players = data?.players || [];
    if (players.length <= 1) return;
    const interval = (config?.interval_seconds || 6) * 1000;
    const iv = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setCurrent((c) => (c + 1) % players.length);
        setFade(true);
      }, 300);
    }, interval);
    return () => clearInterval(iv);
  }, [data?.players?.length, config?.interval_seconds]);

  // Don't render if disabled or no players
  if (!config?.enabled) return null;
  const players = data?.players || [];
  if (players.length === 0) {
    // Fallback CTA when no registered players
    return (
      <div className="px-5 py-4 bg-zinc-800/50 border border-zinc-700 rounded-sm" data-testid="stammkunde-cta">
        <div className="flex items-center gap-3">
          <ShieldCheck className="w-5 h-5 text-amber-500 flex-shrink-0" />
          <div>
            <p className="text-sm text-zinc-300">Werde Stammkunde!</p>
            <p className="text-xs text-zinc-500">Registriere dich beim Spielstart und tracke deine Stats</p>
          </div>
        </div>
      </div>
    );
  }

  const p = players[current];
  const maxLen = config?.nickname_max_length || 15;
  const displayName = p.nickname.length > maxLen ? p.nickname.slice(0, maxLen) + '...' : p.nickname;

  return (
    <div className="px-5 py-4 bg-zinc-800/50 border border-amber-500/20 rounded-sm" data-testid="top-stammkunden-rotation">
      <div className="flex items-center gap-2 mb-3">
        <Trophy className="w-4 h-4 text-amber-500" />
        <p className="text-[11px] text-amber-500/80 uppercase tracking-widest font-heading">
          Top Stammkunden
        </p>
        {players.length > 1 && (
          <div className="flex gap-1 ml-auto">
            {players.map((_, i) => (
              <div key={i} className={`w-1.5 h-1.5 rounded-full transition-colors duration-300 ${i === current ? 'bg-amber-500' : 'bg-zinc-700'}`} />
            ))}
          </div>
        )}
      </div>

      <div className={`transition-opacity duration-300 ${fade ? 'opacity-100' : 'opacity-0'}`} data-testid="stammkunde-card">
        <div className="flex items-center gap-4">
          {/* Rank badge */}
          <div className={`w-10 h-10 rounded-sm flex items-center justify-center flex-shrink-0 ${
            current === 0 ? 'bg-amber-500/20 text-amber-400' :
            current === 1 ? 'bg-zinc-600/30 text-zinc-300' :
            'bg-orange-900/20 text-orange-400'
          }`}>
            <span className="text-lg font-heading font-bold">#{current + 1}</span>
          </div>

          {/* Player info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-lg font-mono font-bold text-white truncate" data-testid="stammkunde-name">
                {displayName}
              </span>
              <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0" />
            </div>
            <div className="flex items-center gap-3 mt-0.5">
              <span className="text-xs text-zinc-500">
                {p.games_won}S / {p.games_played}G
              </span>
              <span className="text-xs text-zinc-600">|</span>
              <span className="text-xs text-zinc-400">
                {p.win_rate}% Quote
              </span>
            </div>
          </div>

          {/* Highlight stat */}
          {p.highlight && (
            <div className={`px-3 py-1.5 rounded-sm text-xs font-mono font-bold flex-shrink-0 ${
              p.highlight.type === '180+' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
              p.highlight.type === 'checkout' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' :
              p.highlight.type === 'throw' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' :
              'bg-zinc-700/50 text-zinc-400 border border-zinc-600'
            }`} data-testid="stammkunde-highlight">
              {p.highlight.type === '180+' && <Target className="w-3 h-3 inline mr-1" />}
              {p.highlight.label}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PairingCode({ boardId }) {
  const [code, setCode] = useState('------');
  const [remaining, setRemaining] = useState(0);

  const fetchCode = useCallback(async () => {
    try {
      const res = await fetch(`${API}/agent/pair/code`);
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
              <div className="text-center p-4 bg-zinc-800/50 rounded-sm border border-zinc-700">
                <p className="text-zinc-500 uppercase text-sm mb-2">Pro Spiel</p>
                <p className="text-3xl font-mono font-bold text-white">
                  {formatPrice(pricing.per_game?.price_per_credit || 2.0)}
                </p>
              </div>
              <div className="text-center p-4 bg-zinc-800/50 rounded-sm border border-zinc-700">
                <p className="text-zinc-500 uppercase text-sm mb-2">30 Minuten</p>
                <p className="text-3xl font-mono font-bold text-white">
                  {formatPrice(pricing.per_time?.price_per_30_min || 5.0)}
                </p>
              </div>
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

      {/* Bottom Section: Top Players + Stammkunden */}
      <div className="relative z-10 px-6 pb-4 space-y-2">
        <div className="max-w-4xl mx-auto space-y-2">
          <TopStammkundenRotation />
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
