import { useState, useEffect, useCallback } from 'react';
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
  Zap
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useAuth } from '../../context/AuthContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function StatBadge({ icon: Icon, label, value, color = 'text-zinc-400' }) {
  if (value === null || value === undefined) return null;
  return (
    <div className="flex items-center gap-1.5 text-xs">
      <Icon className={`w-3 h-3 ${color}`} />
      <span className="text-zinc-500">{label}:</span>
      <span className={`font-mono ${color}`}>{value}</span>
    </div>
  );
}

function RankBadge({ rank }) {
  if (rank === 1) return <Crown className="w-6 h-6 text-amber-400" />;
  if (rank === 2) return <Medal className="w-6 h-6 text-zinc-300" />;
  if (rank === 3) return <Medal className="w-6 h-6 text-amber-700" />;
  return <span className="w-6 text-center text-sm font-mono text-zinc-600">{rank}</span>;
}

export default function Leaderboard() {
  const { token } = useAuth();
  const [period, setPeriod] = useState('all');
  const [sortBy, setSortBy] = useState('games_won');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const headers = { Authorization: `Bearer ${token}` };

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

  if (loading && !data) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  const board = data?.leaderboard || [];
  const topThree = board.slice(0, 3);
  const rest = board.slice(3);

  return (
    <div data-testid="admin-leaderboard">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-heading uppercase tracking-wider text-white">Leaderboard</h1>
          <p className="text-zinc-500">{data?.total_players || 0} Spieler | Zeitraum: {period}</p>
        </div>
        <Button onClick={fetchLeaderboard} variant="outline" className="border-zinc-700 text-zinc-400 hover:text-white" data-testid="leaderboard-refresh-btn">
          <RefreshCw className="w-4 h-4 mr-2" /> Aktualisieren
        </Button>
      </div>

      {/* Period Tabs */}
      <Tabs value={period} onValueChange={setPeriod} className="space-y-6">
        <div className="flex items-center justify-between">
          <TabsList className="bg-zinc-900 border border-zinc-800 p-1">
            <TabsTrigger value="today" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="period-today">Heute</TabsTrigger>
            <TabsTrigger value="week" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="period-week">Woche</TabsTrigger>
            <TabsTrigger value="month" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="period-month">Monat</TabsTrigger>
            <TabsTrigger value="all" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="period-all">Gesamt</TabsTrigger>
          </TabsList>

          {/* Sort selector */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-500">Sortieren:</span>
            {[
              { key: 'games_won', label: 'Siege', icon: Trophy },
              { key: 'games_played', label: 'Spiele', icon: Target },
              { key: 'win_rate', label: 'Quote', icon: TrendingUp },
            ].map(({ key, label, icon: Icon }) => (
              <Button
                key={key}
                size="sm"
                variant={sortBy === key ? 'default' : 'ghost'}
                onClick={() => setSortBy(key)}
                className={sortBy === key ? 'bg-amber-500 text-black hover:bg-amber-400' : 'text-zinc-500 hover:text-white'}
                data-testid={`sort-${key}`}
              >
                <Icon className="w-3 h-3 mr-1" /> {label}
              </Button>
            ))}
          </div>
        </div>

        {/* Content (same for all period tabs) */}
        {['today', 'week', 'month', 'all'].map((p) => (
          <TabsContent key={p} value={p}>
            {board.length === 0 ? (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="py-16 text-center">
                  <Users className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
                  <p className="text-zinc-500">Keine Spieler fuer diesen Zeitraum</p>
                  <p className="text-xs text-zinc-600 mt-1">Spiele werden automatisch erfasst</p>
                </CardContent>
              </Card>
            ) : (
              <div className="space-y-6">
                {/* Podium: Top 3 */}
                {topThree.length > 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {topThree.map((player, i) => (
                      <Card key={player.nickname} className={`bg-zinc-900 border-zinc-800 ${i === 0 ? 'ring-1 ring-amber-500/30' : ''}`}>
                        <CardContent className="p-5 text-center">
                          <RankBadge rank={i + 1} />
                          <p className="text-xl font-heading font-bold text-white mt-2 uppercase" data-testid={`top-${i + 1}-name`}>
                            {player.nickname}
                          </p>
                          <div className="flex justify-center gap-4 mt-3 text-sm">
                            <span className="text-amber-400 font-mono">{player.games_won} <span className="text-xs text-zinc-500">Siege</span></span>
                            <span className="text-zinc-400 font-mono">{player.games_played} <span className="text-xs text-zinc-500">Spiele</span></span>
                          </div>
                          <p className="text-xs text-zinc-500 mt-2">{player.win_rate}% Siegquote</p>
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                )}

                {/* Full List */}
                <Card className="bg-zinc-900 border-zinc-800">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center gap-2 text-base">
                      <Award className="w-5 h-5 text-amber-500" /> Alle Spieler
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-1">
                      {/* Header row */}
                      <div className="grid grid-cols-12 gap-2 px-3 py-2 text-xs text-zinc-500 uppercase tracking-wider border-b border-zinc-800">
                        <div className="col-span-1">#</div>
                        <div className="col-span-3">Spieler</div>
                        <div className="col-span-2 text-right">Spiele</div>
                        <div className="col-span-2 text-right">Siege</div>
                        <div className="col-span-2 text-right">Quote</div>
                        <div className="col-span-2 text-right">Details</div>
                      </div>

                      {board.map((player, i) => (
                        <div
                          key={player.nickname}
                          className={`grid grid-cols-12 gap-2 px-3 py-3 items-center rounded-sm ${i < 3 ? 'bg-zinc-800/30' : 'hover:bg-zinc-800/20'}`}
                          data-testid={`player-row-${player.nickname}`}
                        >
                          <div className="col-span-1 flex items-center">
                            <RankBadge rank={i + 1} />
                          </div>
                          <div className="col-span-3">
                            <span className="text-white font-mono">{player.nickname}</span>
                          </div>
                          <div className="col-span-2 text-right font-mono text-zinc-400">
                            {player.games_played}
                          </div>
                          <div className="col-span-2 text-right font-mono text-amber-400">
                            {player.games_won}
                          </div>
                          <div className="col-span-2 text-right font-mono text-zinc-400">
                            {player.win_rate}%
                          </div>
                          <div className="col-span-2 text-right flex justify-end gap-2">
                            <StatBadge icon={Zap} value={player.highest_throw} color="text-blue-400" />
                            <StatBadge icon={Flame} value={player.best_checkout} color="text-orange-400" />
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
