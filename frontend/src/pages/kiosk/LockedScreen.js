import { useState, useEffect, useCallback } from 'react';
import { Crown, Lock, QrCode, Shield, ShieldCheck, Target, Trophy, Users, WalletCards } from 'lucide-react';
import { useI18n } from '../../context/I18nContext';
import { useSettings } from '../../context/SettingsContext';
import { QRCodeSVG } from 'qrcode.react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function TopPlayersRotation() {
  const [players, setPlayers] = useState([]);
  const [current, setCurrent] = useState(0);
  const { t } = useI18n();

  useEffect(() => {
    const fetchTop = async () => {
      try {
        const res = await fetch(`${API}/stats/top-today?limit=5`);
        if (res.ok) {
          const data = await res.json();
          setPlayers(data.players || []);
        }
      } catch {
        /* ignore */
      }
    };
    fetchTop();
    const iv = setInterval(fetchTop, 60000);
    return () => clearInterval(iv);
  }, []);

  useEffect(() => {
    if (players.length <= 1) return;
    const iv = setInterval(() => setCurrent((value) => (value + 1) % players.length), 5000);
    return () => clearInterval(iv);
  }, [players.length]);

  if (players.length === 0) return null;
  const player = players[current];

  return (
    <div className="rounded-3xl border border-zinc-800 bg-zinc-950/75 p-4 shadow-[0_16px_48px_rgba(0,0,0,0.24)]" data-testid="top-players-rotation">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-500/15 text-amber-400">
          <Crown className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">{t('top_players_today')}</p>
          <div className="mt-1 flex items-center gap-2">
            <span className="truncate text-lg font-semibold text-white" data-testid="top-player-name">{player.nickname}</span>
            <span className="text-xs text-zinc-500">{player.games_won}W / {player.games_played}G</span>
          </div>
        </div>
        {players.length > 1 && (
          <div className="flex gap-1">
            {players.map((_, index) => (
              <div key={index} className={`h-1.5 w-1.5 rounded-full ${index === current ? 'bg-amber-500' : 'bg-zinc-700'}`} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TopStammkundenRotation() {
  const [data, setData] = useState(null);
  const [config, setConfig] = useState(null);
  const [current, setCurrent] = useState(0);
  const [fade, setFade] = useState(true);
  const { t } = useI18n();

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
          if (cfg.period !== 'month' || cfg.max_entries !== 3) {
            const updated = await fetch(`${API}/stats/top-registered?period=${cfg.period}&limit=${cfg.max_entries || 3}`);
            if (updated.ok) setData(await updated.json());
          } else if (dataRes.ok) {
            setData(await dataRes.json());
          }
        } else if (dataRes.ok) {
          setData(await dataRes.json());
        }
      } catch {
        /* ignore */
      }
    };
    fetchData();
    const iv = setInterval(fetchData, 60000);
    return () => clearInterval(iv);
  }, []);

  const playerCount = data?.players?.length || 0;

  useEffect(() => {
    const players = data?.players || [];
    if (players.length <= 1) return;
    const interval = (config?.interval_seconds || 6) * 1000;
    const iv = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setCurrent((value) => (value + 1) % players.length);
        setFade(true);
      }, 280);
    }, interval);
    return () => clearInterval(iv);
  }, [playerCount, config?.interval_seconds, data?.players]);

  if (!config?.enabled) return null;
  const players = data?.players || [];
  if (players.length === 0) {
    return (
      <div className="rounded-3xl border border-zinc-800 bg-zinc-950/75 p-4 shadow-[0_16px_48px_rgba(0,0,0,0.24)]" data-testid="stammkunde-cta">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-400">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm text-zinc-200">{t('become_stammkunde')}</p>
            <p className="text-xs text-zinc-500">{t('become_stammkunde_desc')}</p>
          </div>
        </div>
      </div>
    );
  }

  const player = players[current];
  const maxLen = config?.nickname_max_length || 15;
  const displayName = player.nickname.length > maxLen ? `${player.nickname.slice(0, maxLen)}...` : player.nickname;

  return (
    <div className="rounded-3xl border border-amber-500/20 bg-[linear-gradient(135deg,rgba(245,158,11,0.10),rgba(24,24,27,0.95))] p-4 shadow-[0_20px_48px_rgba(0,0,0,0.28)]" data-testid="top-stammkunden-rotation">
      <div className="mb-3 flex items-center gap-2">
        <Trophy className="h-4 w-4 text-amber-400" />
        <p className="text-[11px] uppercase tracking-[0.28em] text-amber-300">{t('top_stammkunden')}</p>
        {players.length > 1 && (
          <div className="ml-auto flex gap-1">
            {players.map((_, index) => (
              <div key={index} className={`h-1.5 w-1.5 rounded-full ${index === current ? 'bg-amber-400' : 'bg-zinc-700'}`} />
            ))}
          </div>
        )}
      </div>

      <div className={`transition-opacity duration-300 ${fade ? 'opacity-100' : 'opacity-0'}`} data-testid="stammkunde-card">
        <div className="flex items-center gap-4">
          <div className={`flex h-12 w-12 items-center justify-center rounded-2xl ${current === 0 ? 'bg-amber-500/20 text-amber-300' : current === 1 ? 'bg-zinc-700 text-zinc-200' : 'bg-orange-500/15 text-orange-300'}`}>
            <span className="font-heading text-lg font-bold">#{current + 1}</span>
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-lg font-semibold text-white" data-testid="stammkunde-name">{displayName}</span>
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs text-zinc-400">
              <span>{player.games_won}S / {player.games_played}G</span>
              <span className="text-zinc-600">•</span>
              <span>{player.win_rate}% Quote</span>
            </div>
          </div>
          {player.highlight && (
            <div className="rounded-2xl border border-zinc-700 bg-zinc-950/80 px-3 py-2 text-xs font-semibold text-zinc-200" data-testid="stammkunde-highlight">
              {player.highlight.label}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PairingCode() {
  const [code, setCode] = useState('------');
  const [remaining, setRemaining] = useState(0);
  const { t } = useI18n();

  const fetchCode = useCallback(async () => {
    try {
      const res = await fetch(`${API}/agent/pair/code`);
      if (res.ok) {
        const data = await res.json();
        setCode(data.code);
        setRemaining(data.expires_in);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    fetchCode();
    const iv = setInterval(fetchCode, 5000);
    return () => clearInterval(iv);
  }, [fetchCode]);

  useEffect(() => {
    if (remaining <= 0) return;
    const iv = setInterval(() => setRemaining((value) => Math.max(0, value - 1)), 1000);
    return () => clearInterval(iv);
  }, [remaining]);

  const pct = Math.max(0, (remaining / 60) * 100);

  return (
    <div className="rounded-3xl border border-zinc-800 bg-zinc-950/75 p-4 shadow-[0_16px_48px_rgba(0,0,0,0.24)]" data-testid="pairing-code-display">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-amber-500/15 text-amber-400">
          <Shield className="h-5 w-5" />
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">{t('pairing_code')}</p>
          <p className="text-2xl font-mono font-bold tracking-[0.25em] text-white" data-testid="pairing-code-value">{code}</p>
        </div>
        <div className="ml-auto w-16 overflow-hidden rounded-full bg-zinc-800">
          <div className="h-1.5 bg-amber-500 transition-all duration-1000 ease-linear" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}

export default function LockedScreen({ branding, pricing, boardId }) {
  const { t } = useI18n();
  const { kioskTexts } = useSettings();
  const [qrConfig, setQrConfig] = useState(null);
  const [baseUrl, setBaseUrl] = useState('');

  const formatPrice = (amount, currency = 'EUR') => `${amount.toFixed(2)} ${currency}`;

  useEffect(() => {
    const fetchQrConfig = async () => {
      try {
        const [qrRes, urlRes] = await Promise.all([
          fetch(`${API}/settings/lockscreen-qr`),
          fetch(`${API}/system/base-url`),
        ]);
        if (qrRes.ok) setQrConfig(await qrRes.json());
        if (urlRes.ok) {
          const data = await urlRes.json();
          setBaseUrl(data.base_url || '');
        }
      } catch {
        /* ignore */
      }
    };
    fetchQrConfig();
  }, []);

  return (
    <div className="relative h-full w-full overflow-hidden bg-zinc-950" data-testid="locked-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(245,158,11,0.16),transparent_30%),linear-gradient(180deg,rgba(9,9,11,0.96),rgba(9,9,11,1))]" />
      <div className="absolute inset-0 opacity-[0.08] texture-overlay" />

      <div className="relative z-10 flex h-full flex-col px-6 py-6 lg:px-10 lg:py-8">
        <div className="mx-auto flex w-full max-w-7xl items-center justify-between rounded-3xl border border-zinc-800/80 bg-zinc-950/70 px-5 py-4 backdrop-blur">
          <div>
            <p className="text-[11px] uppercase tracking-[0.28em] text-zinc-500">Board {boardId}</p>
            <h1 className="mt-1 text-2xl font-heading uppercase tracking-[0.08em] text-white">{branding.cafe_name}</h1>
            {branding.subtitle && <p className="text-sm text-zinc-500">{branding.subtitle}</p>}
          </div>
          <div className="rounded-full border border-zinc-800 bg-zinc-900/80 px-4 py-2 text-sm text-zinc-300">
            Admin Panel: <span className="font-mono text-white">/admin</span>
          </div>
        </div>

        <div className="mx-auto grid w-full max-w-7xl flex-1 gap-6 py-8 lg:grid-cols-[1.2fr,0.8fr] lg:items-center">
          <div className="space-y-6">
            <div className="inline-flex h-20 w-20 items-center justify-center rounded-3xl border border-zinc-800 bg-zinc-900/80 text-zinc-400 shadow-[0_16px_48px_rgba(0,0,0,0.28)]">
              <Lock className="h-10 w-10" strokeWidth={2.2} />
            </div>
            <div>
              <h2 className="text-4xl font-heading uppercase tracking-[0.08em] text-white md:text-6xl" data-testid="locked-message">
                {kioskTexts.locked_title || t('locked')}
              </h2>
              <p className="mt-4 max-w-2xl text-lg leading-8 text-zinc-400">
                {kioskTexts.locked_subtitle || t('locked_message')}
              </p>
              {kioskTexts.pricing_hint && (
                <p className="mt-3 text-sm uppercase tracking-[0.22em] text-amber-300">{kioskTexts.pricing_hint}</p>
              )}
            </div>

            <div className="grid gap-4 md:grid-cols-3" data-testid="pricing-info">
              <div className="rounded-3xl border border-zinc-800 bg-zinc-950/80 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.2)]">
                <div className="flex items-center gap-2 text-sm text-zinc-500">
                  <WalletCards className="h-4 w-4 text-amber-400" />
                  Credits
                </div>
                <p className="mt-4 text-3xl font-semibold text-white">{formatPrice(pricing.per_game?.price_per_credit || 2.0)}</p>
                <p className="mt-2 text-sm text-zinc-500">Preis pro Credit am Board</p>
              </div>
              <div className="rounded-3xl border border-zinc-800 bg-zinc-950/80 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.2)]">
                <div className="flex items-center gap-2 text-sm text-zinc-500">
                  <Users className="h-4 w-4 text-amber-400" />
                  Matchstart
                </div>
                <p className="mt-4 text-3xl font-semibold text-white">1 Credit / Spieler</p>
                <p className="mt-2 text-sm text-zinc-500">Die echte Abbuchung passiert erst beim echten Match.</p>
              </div>
              <div className="rounded-3xl border border-zinc-800 bg-zinc-950/80 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.2)]">
                <div className="flex items-center gap-2 text-sm text-zinc-500">
                  <Target className="h-4 w-4 text-amber-400" />
                  Freischaltung
                </div>
                <p className="mt-4 text-3xl font-semibold text-white">{pricing.per_game?.default_credits || 3} Credits</p>
                <p className="mt-2 text-sm text-zinc-500">Typischer Startwert, Nachladen jederzeit an der Theke.</p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            <PairingCode />
            {qrConfig?.enabled && baseUrl ? (
              <div className="rounded-3xl border border-zinc-800 bg-zinc-950/75 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]" data-testid="lockscreen-qr">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">{qrConfig.label || 'Leaderboard'}</p>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">Stats & Ergebnisse direkt am Handy ansehen.</p>
                  </div>
                  <div className="rounded-2xl bg-white p-2">
                    <QRCodeSVG value={`${baseUrl}${qrConfig.path || '/public/leaderboard'}`} size={72} bgColor="#ffffff" fgColor="#09090b" level="L" />
                  </div>
                </div>
              </div>
            ) : null}
            <TopStammkundenRotation />
            <TopPlayersRotation />
          </div>
        </div>

        <div className="mx-auto w-full max-w-7xl rounded-3xl border border-zinc-800 bg-zinc-950/70 px-5 py-4 text-sm text-zinc-400 backdrop-blur">
          Unlocks laufen lokal über den Operator. Kein Lizenz-/Zentral-Noise auf dem Startscreen — nur das, was Gäste hier wirklich brauchen.
        </div>
      </div>
    </div>
  );
}
