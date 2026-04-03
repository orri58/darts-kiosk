import { useState, useEffect, useCallback } from 'react';
import { Crown, Lock, Shield, ShieldCheck, Target, Trophy, Users, WalletCards } from 'lucide-react';
import { useI18n } from '../../context/I18nContext';
import { useSettings } from '../../context/SettingsContext';
import { QRCodeSVG } from 'qrcode.react';
import KioskHeader from '../../components/kiosk/KioskHeader';

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
    <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.58)] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.24)]" data-testid="top-players-rotation">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[rgb(var(--color-primary-rgb)/0.16)] text-[var(--color-primary)]">
          <Crown className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">{t('top_players_today')}</p>
          <div className="mt-1 flex items-center gap-2">
            <span className="truncate text-lg font-semibold text-[var(--color-text)]" data-testid="top-player-name">{player.nickname}</span>
            <span className="text-xs text-[var(--color-text-secondary)]">{player.games_won}W / {player.games_played}G</span>
          </div>
        </div>
        {players.length > 1 && (
          <div className="flex gap-1">
            {players.map((_, index) => (
              <div key={index} className={`h-1.5 w-1.5 rounded-full ${index === current ? 'bg-[var(--color-primary)]' : 'bg-[rgb(var(--color-border-rgb)/0.9)]'}`} />
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
            <p className="text-sm text-[var(--color-text)]">{t('become_stammkunde')}</p>
            <p className="text-xs text-[var(--color-text-secondary)]">{t('become_stammkunde_desc')}</p>
          </div>
        </div>
      </div>
    );
  }

  const player = players[current];
  const maxLen = config?.nickname_max_length || 15;
  const displayName = player.nickname.length > maxLen ? `${player.nickname.slice(0, maxLen)}...` : player.nickname;

  return (
    <div className="rounded-3xl border border-[rgb(var(--color-primary-rgb)/0.24)] bg-[linear-gradient(135deg,rgb(var(--color-primary-rgb)/0.14),rgb(var(--color-surface-rgb)/0.96))] p-4 shadow-[0_20px_48px_rgba(0,0,0,0.28)]" data-testid="top-stammkunden-rotation">
      <div className="mb-3 flex items-center gap-2">
        <Trophy className="h-4 w-4 text-[var(--color-primary)]" />
        <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-primary)]">{t('top_stammkunden')}</p>
        {players.length > 1 && (
          <div className="ml-auto flex gap-1">
            {players.map((_, index) => (
              <div key={index} className={`h-1.5 w-1.5 rounded-full ${index === current ? 'bg-[var(--color-primary)]' : 'bg-[rgb(var(--color-border-rgb)/0.9)]'}`} />
            ))}
          </div>
        )}
      </div>

      <div className={`transition-opacity duration-300 ${fade ? 'opacity-100' : 'opacity-0'}`} data-testid="stammkunde-card">
        <div className="flex items-center gap-4">
          <div className={`flex h-12 w-12 items-center justify-center rounded-2xl ${current === 0 ? 'bg-[rgb(var(--color-primary-rgb)/0.18)] text-[var(--color-primary)]' : current === 1 ? 'bg-[rgb(var(--color-border-rgb)/0.65)] text-[var(--color-text)]' : 'bg-[rgb(var(--color-accent-rgb)/0.14)] text-[var(--color-text)]'}`}>
            <span className="font-heading text-lg font-bold">#{current + 1}</span>
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-lg font-semibold text-[var(--color-text)]" data-testid="stammkunde-name">{displayName}</span>
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs text-[var(--color-text-secondary)]">
              <span>{player.games_won}S / {player.games_played}G</span>
              <span className="text-[var(--color-text-muted)]">•</span>
              <span>{player.win_rate}% Quote</span>
            </div>
          </div>
          {player.highlight && (
            <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.62)] px-3 py-2 text-xs font-semibold text-[var(--color-text)]" data-testid="stammkunde-highlight">
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
  const [visible, setVisible] = useState(false);
  const { t } = useI18n();

  const fetchCode = useCallback(async () => {
    try {
      const statusRes = await fetch(`${API}/agent/pair/status`);
      if (statusRes.ok) {
        const statusData = await statusRes.json();
        const shouldShow = Boolean(statusData.show_pairing_code);
        setVisible(shouldShow);
        if (!shouldShow) {
          setRemaining(0);
          return;
        }
      } else {
        setVisible(true);
      }

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

  if (!visible) return null;

  const pct = Math.max(0, (remaining / 60) * 100);

  return (
    <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.58)] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.24)]" data-testid="pairing-code-display">
      <div className="flex items-center gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[rgb(var(--color-primary-rgb)/0.16)] text-[var(--color-primary)]">
          <Shield className="h-5 w-5" />
        </div>
        <div>
          <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">{t('pairing_code')}</p>
          <p className="text-2xl font-mono font-bold tracking-[0.25em] text-[var(--color-text)]" data-testid="pairing-code-value">{code}</p>
          <p className="mt-1 text-xs text-[var(--color-text-secondary)]">Nur nötig, wenn das Gerät neu gekoppelt werden muss.</p>
        </div>
        <div className="ml-auto w-16 overflow-hidden rounded-full bg-[rgb(var(--color-bg-rgb)/0.65)]">
          <div className="h-1.5 bg-[var(--color-primary)] transition-all duration-1000 ease-linear" style={{ width: `${pct}%` }} />
        </div>
      </div>
    </div>
  );
}

export default function LockedScreen({ branding, pricing, boardId }) {
  const { t } = useI18n();
  const { kioskTexts, kioskLayout } = useSettings();
  const [qrConfig, setQrConfig] = useState(null);
  const [baseUrl, setBaseUrl] = useState('');
  const showCommunityWidgets = Boolean(kioskLayout?.locked_screen?.show_community_widgets);
  const pairingPosition = kioskLayout?.locked_screen?.pairing_position || 'bottom';

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
    <div className="relative h-full w-full overflow-hidden bg-[var(--color-bg)]" data-testid="locked-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgb(var(--color-primary-rgb)/0.18),transparent_30%),linear-gradient(180deg,rgb(var(--color-bg-rgb)/0.96),var(--color-bg))]" />
      <div className="absolute inset-0 opacity-[0.08] texture-overlay" />

      <div className="relative z-10 flex h-full flex-col px-4 py-4 lg:px-8 lg:py-6">
        <KioskHeader branding={branding} eyebrow={`Board ${boardId}`} compact />

        <div className="mx-auto grid w-full max-w-7xl flex-1 gap-5 py-5 lg:grid-cols-[1.25fr,0.75fr] lg:items-center lg:py-7">
          <div className="space-y-5">
            <div className="inline-flex h-16 w-16 items-center justify-center rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.8)] text-[var(--color-text-secondary)] shadow-[0_16px_48px_rgba(0,0,0,0.28)] lg:h-20 lg:w-20">
              <Lock className="h-10 w-10" strokeWidth={2.2} />
            </div>
            <div>
              <h2 className="text-3xl font-heading uppercase tracking-[0.08em] text-[var(--color-text)] md:text-5xl lg:text-6xl" data-testid="locked-message">
                {kioskTexts.locked_title || t('locked')}
              </h2>
              <p className="mt-3 max-w-2xl text-base leading-7 text-[var(--color-text-secondary)] lg:text-lg lg:leading-8">
                {kioskTexts.locked_subtitle || t('locked_message')}
              </p>
              {kioskTexts.pricing_hint && (
                <p className="mt-3 text-sm uppercase tracking-[0.22em] text-[var(--color-primary)]">{kioskTexts.pricing_hint}</p>
              )}
            </div>

            <div className="grid gap-3 md:grid-cols-3" data-testid="pricing-info">
              <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.2)]">
                <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                  <WalletCards className="h-4 w-4 text-[var(--color-primary)]" />
                  Credits
                </div>
                <p className="mt-3 text-2xl font-semibold text-[var(--color-text)] lg:text-3xl">{formatPrice(pricing.per_game?.price_per_credit || 2.0)}</p>
                <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Preis pro Credit</p>
              </div>
              <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.2)]">
                <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                  <Users className="h-4 w-4 text-[var(--color-primary)]" />
                  Matchstart
                </div>
                <p className="mt-3 text-2xl font-semibold text-[var(--color-text)] lg:text-3xl">1 Credit / Spieler</p>
                <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Abbuchung erst beim echten Match.</p>
              </div>
              <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-4 shadow-[0_16px_48px_rgba(0,0,0,0.2)]">
                <div className="flex items-center gap-2 text-sm text-[var(--color-text-secondary)]">
                  <Target className="h-4 w-4 text-[var(--color-primary)]" />
                  Freischaltung
                </div>
                <p className="mt-3 text-2xl font-semibold text-[var(--color-text)] lg:text-3xl">{pricing.per_game?.default_credits || 3} Credits</p>
                <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Typischer Startwert am Tresen.</p>
              </div>
            </div>
          </div>

          <div className="space-y-4">
            {pairingPosition === 'side' ? <PairingCode /> : null}
            {qrConfig?.enabled && baseUrl ? (
              <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.58)] p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]" data-testid="lockscreen-qr">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">{qrConfig.label || 'Leaderboard'}</p>
                    <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">Stats & Ergebnisse direkt am Handy ansehen.</p>
                  </div>
                  <div className="rounded-2xl bg-white p-2">
                    <QRCodeSVG value={`${baseUrl}${qrConfig.path || '/public/leaderboard'}`} size={72} bgColor="#ffffff" fgColor="#09090b" level="L" />
                  </div>
                </div>
              </div>
            ) : null}
            {showCommunityWidgets ? <TopStammkundenRotation /> : null}
            {showCommunityWidgets ? <TopPlayersRotation /> : null}
          </div>
        </div>

        <div className="mx-auto mt-auto w-full max-w-7xl">
          {pairingPosition !== 'side' ? <PairingCode /> : null}
        </div>
      </div>
    </div>
  );
}
