import { useState, useEffect } from 'react';
import { Trophy, Target, Award, TrendingUp } from 'lucide-react';
import { useSettings } from '../context/SettingsContext';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export default function PublicLeaderboard() {
  const { branding } = useSettings();
  const [leaderboard, setLeaderboard] = useState([]);
  const [period, setPeriod] = useState('all');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      try {
        const res = await axios.get(`${API}/stats/leaderboard`, {
          params: { period, sort_by: 'games_won', limit: 20 },
        });
        setLeaderboard(res.data.leaderboard || []);
      } catch { setLeaderboard([]); }
      finally { setLoading(false); }
    };
    load();
  }, [period]);

  const medals = ['text-amber-400', 'text-zinc-300', 'text-orange-600'];

  return (
    <div className="min-h-screen bg-zinc-950 text-white" data-testid="public-leaderboard">
      <div className="max-w-lg mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-wider uppercase" data-testid="pub-lb-title">
            {branding.cafe_name}
          </h1>
          <p className="text-zinc-400 text-sm mt-1">{branding.subtitle}</p>
          <div className="flex items-center justify-center gap-2 mt-4 text-amber-500">
            <Trophy className="w-5 h-5" />
            <span className="font-semibold tracking-wide">Leaderboard</span>
          </div>
        </div>

        {/* Period Filter */}
        <div className="flex gap-2 mb-6 justify-center" data-testid="pub-lb-filters">
          {[
            { key: 'today', label: 'Heute' },
            { key: 'week', label: 'Woche' },
            { key: 'month', label: 'Monat' },
            { key: 'all', label: 'Alle' },
          ].map((p) => (
            <button
              key={p.key}
              onClick={() => setPeriod(p.key)}
              className={`px-3 py-1.5 text-xs rounded-sm transition-all ${
                period === p.key
                  ? 'bg-amber-500 text-black font-medium'
                  : 'bg-zinc-800 text-zinc-400 hover:text-white'
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        {/* Leaderboard */}
        {loading ? (
          <div className="text-center text-zinc-500 py-12">Laden...</div>
        ) : leaderboard.length === 0 ? (
          <div className="text-center text-zinc-500 py-12">
            <Target className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>Noch keine Spiele in diesem Zeitraum</p>
          </div>
        ) : (
          <div className="space-y-2" data-testid="pub-lb-list">
            {leaderboard.map((player, idx) => (
              <div
                key={player.nickname}
                className={`flex items-center gap-3 p-3 rounded-sm transition-all ${
                  idx < 3 ? 'bg-zinc-900 border border-zinc-800' : 'bg-zinc-900/50'
                }`}
              >
                <div className={`w-8 text-center font-bold text-lg ${idx < 3 ? medals[idx] : 'text-zinc-600'}`}>
                  {idx < 3 ? <Award className="w-5 h-5 mx-auto" /> : idx + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{player.nickname}</p>
                  <p className="text-xs text-zinc-500">
                    {player.games_played} Spiele
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-amber-500 font-bold">{player.games_won}</p>
                  <p className="text-xs text-zinc-500">
                    <TrendingUp className="w-3 h-3 inline mr-1" />
                    {player.win_rate || 0}%
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 text-center text-xs text-zinc-600">
          {branding.cafe_name} &middot; Dart Kiosk System
        </div>
      </div>
    </div>
  );
}
