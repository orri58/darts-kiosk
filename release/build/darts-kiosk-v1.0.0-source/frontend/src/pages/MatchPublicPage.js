import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { Trophy, Target, Users, Clock, MapPin, Calendar, Timer, AlertTriangle } from 'lucide-react';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function formatDuration(seconds) {
  if (!seconds) return null;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m > 0) return `${m}m ${s}s`;
  return `${s}s`;
}

export default function MatchPublicPage() {
  const { token } = useParams();
  const [match, setMatch] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMatch = async () => {
      try {
        const res = await axios.get(`${API}/match/${token}`);
        setMatch(res.data);
      } catch (err) {
        const status = err.response?.status;
        if (status === 410) setError('expired');
        else if (status === 404) setError('not_found');
        else if (status === 429) setError('rate_limit');
        else setError('unknown');
      } finally {
        setLoading(false);
      }
    };
    fetchMatch();
  }, [token]);

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
        <div className="text-center max-w-md" data-testid="match-error">
          <AlertTriangle className="w-16 h-16 text-amber-500 mx-auto mb-4" />
          {error === 'expired' && (
            <>
              <h1 className="text-2xl font-heading text-white uppercase mb-2">Link abgelaufen</h1>
              <p className="text-zinc-500">Dieser Match-Link ist nach 24 Stunden abgelaufen.</p>
            </>
          )}
          {error === 'not_found' && (
            <>
              <h1 className="text-2xl font-heading text-white uppercase mb-2">Nicht gefunden</h1>
              <p className="text-zinc-500">Dieser Match-Link existiert nicht.</p>
            </>
          )}
          {error === 'rate_limit' && (
            <>
              <h1 className="text-2xl font-heading text-white uppercase mb-2">Zu viele Anfragen</h1>
              <p className="text-zinc-500">Bitte warten Sie einen Moment und versuchen Sie es erneut.</p>
            </>
          )}
          {error === 'unknown' && (
            <>
              <h1 className="text-2xl font-heading text-white uppercase mb-2">Fehler</h1>
              <p className="text-zinc-500">Etwas ist schiefgelaufen.</p>
            </>
          )}
        </div>
      </div>
    );
  }

  const playedDate = match?.played_at ? new Date(match.played_at) : null;

  return (
    <div className="min-h-screen bg-zinc-950 text-white" data-testid="match-public-page">
      {/* Header */}
      <div className="border-b border-zinc-800 p-6">
        <div className="max-w-2xl mx-auto text-center">
          <div className="flex items-center justify-center gap-3 mb-1">
            <Target className="w-6 h-6 text-amber-500" />
            <span className="text-sm text-zinc-500 uppercase tracking-widest">Match Ergebnis</span>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-2xl mx-auto p-6 space-y-8">
        {/* Game Type */}
        <div className="text-center py-6">
          <h1 className="text-6xl font-heading font-bold uppercase text-white mb-3" data-testid="public-game-type">
            {match?.game_type}
          </h1>
          {match?.board_name && (
            <p className="flex items-center justify-center gap-2 text-zinc-500">
              <MapPin className="w-4 h-4" /> {match.board_name}
            </p>
          )}
        </div>

        {/* Players */}
        <div className="space-y-3">
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-5 h-5 text-zinc-500" />
            <span className="text-sm text-zinc-500 uppercase tracking-wider">Spieler</span>
          </div>
          {match?.players?.map((player, i) => (
            <div
              key={i}
              className={`flex items-center gap-4 p-4 rounded-sm ${i === 0 && match.winner === player ? 'bg-amber-500/10 border border-amber-500/30' : 'bg-zinc-900 border border-zinc-800'}`}
              data-testid={`public-player-${i}`}
            >
              {i === 0 && match.winner === player && (
                <Trophy className="w-6 h-6 text-amber-500 flex-shrink-0" />
              )}
              <span className={`font-mono text-lg ${i === 0 && match.winner === player ? 'text-amber-400 font-bold' : 'text-white'}`}>
                {player}
              </span>
              {match?.scores && match.scores[player] !== undefined && (
                <span className="ml-auto font-mono text-xl text-zinc-400">
                  {match.scores[player]}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* Meta Info */}
        <div className="grid grid-cols-2 gap-4">
          {playedDate && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-sm p-4">
              <div className="flex items-center gap-2 mb-1">
                <Calendar className="w-4 h-4 text-zinc-500" />
                <span className="text-xs text-zinc-500 uppercase">Gespielt am</span>
              </div>
              <p className="text-white font-mono" data-testid="public-played-at">
                {playedDate.toLocaleDateString('de-DE')}
              </p>
              <p className="text-sm text-zinc-500 font-mono">
                {playedDate.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>
          )}

          {match?.duration_seconds && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-sm p-4">
              <div className="flex items-center gap-2 mb-1">
                <Timer className="w-4 h-4 text-zinc-500" />
                <span className="text-xs text-zinc-500 uppercase">Dauer</span>
              </div>
              <p className="text-white font-mono" data-testid="public-duration">
                {formatDuration(match.duration_seconds)}
              </p>
            </div>
          )}
        </div>

        {/* Expiry notice */}
        <div className="text-center pt-4 border-t border-zinc-800">
          <p className="text-xs text-zinc-600 flex items-center justify-center gap-1">
            <Clock className="w-3 h-3" />
            Dieser Link ist 24 Stunden gueltig
          </p>
        </div>
      </div>
    </div>
  );
}
