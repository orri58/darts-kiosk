import { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import {
  Trophy,
  Medal,
  Target,
  TrendingUp,
  Users,
  RefreshCw,
  Crown,
  Flame,
  Award,
  Zap,
  Trash2,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import { toast } from 'sonner';
import {
  AdminEmptyState,
  AdminPage,
  AdminSection,
  AdminStatCard,
  AdminStatsGrid,
  AdminStatusPill,
} from '../../components/admin/AdminShell';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function StatBadge({ icon: Icon, label, value, tone = 'neutral' }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <AdminStatusPill tone={tone} className="normal-case tracking-[0.08em]">
      <Icon className="h-3 w-3" /> {label}: {value}
    </AdminStatusPill>
  );
}

function RankBadge({ rank }) {
  if (rank === 1) return <Crown className="h-6 w-6 text-amber-400" />;
  if (rank === 2) return <Medal className="h-6 w-6 text-zinc-300" />;
  if (rank === 3) return <Medal className="h-6 w-6 text-amber-700" />;
  return <span className="w-6 text-center text-sm font-mono text-zinc-500">{rank}</span>;
}

export default function Leaderboard() {
  const { token } = useAuth();
  const { t } = useI18n();
  const [period, setPeriod] = useState('all');
  const [sortBy, setSortBy] = useState('games_won');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchLeaderboard = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/stats/leaderboard`, {
        params: { period, sort_by: sortBy, limit: 50 },
      });
      setData(res.data);
    } catch (err) {
      console.error('Leaderboard fetch error', err);
    } finally {
      setLoading(false);
    }
  }, [period, sortBy]);

  useEffect(() => {
    setLoading(true);
    fetchLeaderboard();
  }, [fetchLeaderboard]);

  const board = useMemo(() => data?.leaderboard || [], [data]);
  const topThree = board.slice(0, 3);

  const leaderboardStats = useMemo(() => {
    const topPlayer = board[0] || null;
    const totalGames = board.reduce((sum, player) => sum + Number(player.games_played || 0), 0);
    const highestCheckout = board.reduce((max, player) => Math.max(max, Number(player.best_checkout || 0)), 0);
    return {
      totalPlayers: data?.total_players || 0,
      totalGames,
      topPlayer,
      highestCheckout,
    };
  }, [board, data]);

  const periodLabel = period === 'today' ? 'Heute' : period === 'week' ? 'Woche' : period === 'month' ? 'Monat' : 'Gesamt';
  const sortLabel = sortBy === 'games_played' ? 'Spiele' : sortBy === 'win_rate' ? 'Quote' : 'Siege';

  if (loading && !data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-amber-500" />
      </div>
    );
  }

  return (
    <AdminPage
      eyebrow="Player performance"
      title={t('leaderboard')}
      description="Lokales Ranking mit etwas mehr Hierarchie statt Tabellenfriedhof: Podium, Rankingliste und gezielte Wartungsaktionen für Gastdaten und Matchhistorie."
      actions={
        <Button onClick={fetchLeaderboard} variant="outline" className="border-zinc-700 text-zinc-300 hover:text-white" data-testid="leaderboard-refresh-btn">
          <RefreshCw className="mr-2 h-4 w-4" /> Aktualisieren
        </Button>
      }
    >
      <AdminStatsGrid>
        <AdminStatCard icon={Users} label="Spieler im Scope" value={leaderboardStats.totalPlayers} hint={`Zeitraum: ${periodLabel}`} tone="blue" />
        <AdminStatCard icon={Trophy} label="Sortierung" value={sortLabel} hint={leaderboardStats.topPlayer ? `Spitze: ${leaderboardStats.topPlayer.nickname}` : 'Noch kein Spitzenreiter'} tone="amber" />
        <AdminStatCard icon={Target} label="Erfasste Spiele" value={leaderboardStats.totalGames} hint="aufsummiert aus dem aktuellen Ranking" tone="violet" />
        <AdminStatCard icon={Flame} label="Bester Checkout" value={leaderboardStats.highestCheckout || '–'} hint="höchster sichtbarer Wert im Ranking" tone={leaderboardStats.highestCheckout ? 'emerald' : 'neutral'} />
      </AdminStatsGrid>

      <Tabs value={period} onValueChange={setPeriod} className="space-y-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <TabsList className="sticky top-3 z-20 flex h-auto flex-nowrap gap-1 overflow-x-auto rounded-[1.4rem] border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.82)] p-1.5 shadow-[0_16px_36px_rgba(0,0,0,0.22)] backdrop-blur">
            <TabsTrigger value="today" className="rounded-[1rem] px-4 py-2.5 data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="period-today">Heute</TabsTrigger>
            <TabsTrigger value="week" className="rounded-[1rem] px-4 py-2.5 data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="period-week">Woche</TabsTrigger>
            <TabsTrigger value="month" className="rounded-[1rem] px-4 py-2.5 data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="period-month">Monat</TabsTrigger>
            <TabsTrigger value="all" className="rounded-[1rem] px-4 py-2.5 data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="period-all">Gesamt</TabsTrigger>
          </TabsList>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs uppercase tracking-[0.22em] text-zinc-500">Sortieren nach</span>
            {[
              { key: 'games_won', label: 'Siege', icon: Trophy },
              { key: 'games_played', label: 'Spiele', icon: Target },
              { key: 'win_rate', label: 'Quote', icon: TrendingUp },
            ].map(({ key, label, icon: Icon }) => (
              <Button
                key={key}
                size="sm"
                variant={sortBy === key ? 'default' : 'outline'}
                onClick={() => setSortBy(key)}
                className={sortBy === key ? 'bg-amber-500 text-black hover:bg-amber-400' : 'border-zinc-700 text-zinc-300 hover:text-white'}
                data-testid={`sort-${key}`}
              >
                <Icon className="mr-1 h-3 w-3" /> {label}
              </Button>
            ))}
          </div>
        </div>

        {['today', 'week', 'month', 'all'].map((p) => (
          <TabsContent key={p} value={p}>
            {board.length === 0 ? (
              <AdminSection title="Leaderboard" description="Sobald lokale Matchresultate vorhanden sind, baut sich das Ranking hier automatisch auf.">
                <AdminEmptyState
                  icon={Users}
                  title="Keine Spieler für diesen Zeitraum"
                  description="Im aktuellen Zeitfenster liegen noch keine erfassten Matches vor oder es wurden alle relevanten Daten bereits zurückgesetzt."
                />
              </AdminSection>
            ) : (
              <div className="space-y-6">
                {topThree.length > 0 && (
                  <AdminSection title="Podium" description="Die drei sichtbar stärksten Spieler im aktuellen Scope.">
                    <div className="grid gap-4 md:grid-cols-3">
                      {topThree.map((player, i) => (
                        <div
                          key={player.nickname}
                          className={`rounded-3xl border p-5 text-center shadow-[0_12px_34px_rgba(0,0,0,0.22)] ${i === 0 ? 'border-[rgb(var(--color-primary-rgb)/0.28)] bg-[rgb(var(--color-primary-rgb)/0.1)]' : 'border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.52)]'}`}
                        >
                          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-[rgb(var(--color-bg-rgb)/0.54)]">
                            <RankBadge rank={i + 1} />
                          </div>
                          <p className="mt-4 break-words text-xl font-heading font-bold text-[var(--color-text)]" data-testid={`top-${i + 1}-name`}>
                            {player.nickname}
                          </p>
                          <div className="mt-4 flex items-center justify-center gap-4 text-sm">
                            <div>
                              <p className="font-mono text-[var(--color-primary)]">{player.games_won}</p>
                              <p className="text-xs text-[var(--color-text-muted)]">Siege</p>
                            </div>
                            <div>
                              <p className="font-mono text-[var(--color-text-secondary)]">{player.games_played}</p>
                              <p className="text-xs text-[var(--color-text-muted)]">Spiele</p>
                            </div>
                          </div>
                          <p className="mt-3 text-sm text-[var(--color-text-secondary)]">{player.win_rate}% Siegquote</p>
                        </div>
                      ))}
                    </div>
                  </AdminSection>
                )}

                <AdminSection
                  title="Rankingliste"
                  description="Komplette Reihenfolge mit schnellen Leistungsdetails pro Spieler."
                  actions={<AdminStatusPill tone="blue">{board.length} Einträge</AdminStatusPill>}
                >
                  <div className="space-y-3">
                    {board.map((player, i) => (
                      <div
                        key={player.nickname}
                        className={`grid gap-4 rounded-2xl border p-4 md:grid-cols-[auto,1.4fr,repeat(3,minmax(0,0.7fr)),1.2fr] md:items-center ${i < 3 ? 'border-[rgb(var(--color-primary-rgb)/0.18)] bg-[rgb(var(--color-primary-rgb)/0.06)]' : 'border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.5)]'}`}
                        data-testid={`player-row-${player.nickname}`}
                      >
                        <div className="flex items-center justify-center rounded-2xl bg-[rgb(var(--color-bg-rgb)/0.5)] px-3 py-3">
                          <RankBadge rank={i + 1} />
                        </div>
                        <div>
                          <p className="font-medium text-[var(--color-text)]">{player.nickname}</p>
                          <div className="mt-2 flex flex-wrap gap-2">
                            <StatBadge icon={Zap} label="High throw" value={player.highest_throw} tone="blue" />
                            <StatBadge icon={Flame} label="Checkout" value={player.best_checkout} tone="amber" />
                          </div>
                        </div>
                        <MetricCell label="Spiele" value={player.games_played} />
                        <MetricCell label="Siege" value={player.games_won} accent />
                        <MetricCell label="Quote" value={`${player.win_rate}%`} />
                        <div className="flex flex-wrap gap-2 md:justify-end">
                          {i === 0 ? <AdminStatusPill tone="emerald">führt</AdminStatusPill> : null}
                          {player.games_played >= 10 ? <AdminStatusPill tone="neutral">aktiv</AdminStatusPill> : null}
                        </div>
                      </div>
                    ))}
                  </div>
                </AdminSection>
              </div>
            )}
          </TabsContent>
        ))}
      </Tabs>

      <AdminSection
        title="Datenverwaltung"
        description="Bewusst sichtbar, aber klar als Wartungsbereich markiert. Sessions/Umsatz bleiben davon unberührt, solange es der jeweilige Text sagt."
        actions={<AdminStatusPill tone="red"><AlertTriangle className="h-3 w-3" /> destruktiv</AdminStatusPill>}
      >
        <div className="space-y-4">
          <div className="rounded-2xl border border-[rgb(var(--color-accent-rgb)/0.18)] bg-[rgb(var(--color-accent-rgb)/0.08)] p-4 text-sm leading-6 text-[var(--color-text-secondary)]">
            Diese Aktionen sind nicht für den Alltagsbetrieb gedacht. Sie helfen bei Demo-Resets, Testgeräten oder wenn Gastdaten bewusst bereinigt werden sollen.
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              data-testid="reset-guest-stats-btn"
              size="sm"
              variant="outline"
              className="border-red-800 text-red-400 hover:bg-red-900/30"
              onClick={async () => {
                if (!window.confirm('Alle Gast-Spieler loeschen? (Registrierte bleiben erhalten)')) return;
                try {
                  const res = await axios.delete(`${API}/admin/players/guests`, { headers: { Authorization: `Bearer ${token}` } });
                  toast.success(res.data.message);
                  fetchLeaderboard();
                } catch {
                  toast.error('Fehler');
                }
              }}
            >
              <Trash2 className="mr-1 h-3 w-3" /> Gast-Spieler löschen
            </Button>
            <Button
              data-testid="reset-all-stats-btn"
              size="sm"
              variant="outline"
              className="border-red-800 text-red-400 hover:bg-red-900/30"
              onClick={async () => {
                if (!window.confirm('Alle Spieler-Statistiken zuruecksetzen? (Spieler bleiben, nur Zaehler auf 0)')) return;
                try {
                  const res = await axios.delete(`${API}/admin/players/all-stats`, { headers: { Authorization: `Bearer ${token}` } });
                  toast.success(res.data.message);
                  fetchLeaderboard();
                } catch {
                  toast.error('Fehler');
                }
              }}
            >
              <RefreshCw className="mr-1 h-3 w-3" /> Alle Stats zurücksetzen
            </Button>
            <Button
              data-testid="delete-matches-btn"
              size="sm"
              variant="outline"
              className="border-red-800 text-red-400 hover:bg-red-900/30"
              onClick={async () => {
                if (!window.confirm('Alle Match-Ergebnisse loeschen? (Sessions/Umsatz bleiben erhalten)')) return;
                try {
                  const res = await axios.delete(`${API}/admin/matches`, { headers: { Authorization: `Bearer ${token}` } });
                  toast.success(res.data.message);
                } catch {
                  toast.error('Fehler');
                }
              }}
            >
              <Trash2 className="mr-1 h-3 w-3" /> Match-Historie löschen
            </Button>
          </div>
          <p className="text-xs text-zinc-500">Sessions und Umsatzdaten werden von diesen Resets nicht berührt.</p>
        </div>
      </AdminSection>
    </AdminPage>
  );
}

function MetricCell({ label, value, accent = false }) {
  return (
    <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.72)] bg-[rgb(var(--color-bg-rgb)/0.42)] px-3 py-2 text-right">
      <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">{label}</p>
      <p className={`mt-1 font-mono text-sm ${accent ? 'text-[var(--color-primary)]' : 'text-[var(--color-text)]'}`}>{value}</p>
    </div>
  );
}
