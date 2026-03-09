import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { useAuth } from '../../hooks/useAuth';
import { useI18n } from '../../hooks/useI18n';
import { FileDown, Calendar, Filter, TrendingUp, DollarSign, BarChart3, Hash } from 'lucide-react';
import { toast } from 'sonner';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Reports() {
  const { token } = useAuth();
  const { t } = useI18n();

  const [sessions, setSessions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [boards, setBoards] = useState([]);

  // Filters
  const [preset, setPreset] = useState('month');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [filterBoard, setFilterBoard] = useState('');
  const [filterMode, setFilterMode] = useState('');

  useEffect(() => {
    const fetchBoards = async () => {
      try {
        const res = await axios.get(`${API}/boards`, { headers: { Authorization: `Bearer ${token}` } });
        setBoards(res.data);
      } catch { /* ignore */ }
    };
    fetchBoards();
  }, [token]);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (preset && !dateFrom && !dateTo) params.append('preset', preset);
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);
      if (filterBoard) params.append('board_id', filterBoard);
      if (filterMode) params.append('pricing_mode', filterMode);

      const res = await axios.get(`${API}/reports/sessions?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSessions(res.data.sessions);
      setSummary(res.data.summary);
    } catch {
      toast.error('Fehler beim Laden');
    } finally {
      setLoading(false);
    }
  }, [token, preset, dateFrom, dateTo, filterBoard, filterMode]);

  useEffect(() => { fetchReport(); }, [fetchReport]);

  const exportCSV = () => {
    const params = new URLSearchParams();
    if (preset && !dateFrom && !dateTo) params.append('preset', preset);
    if (dateFrom) params.append('date_from', dateFrom);
    if (dateTo) params.append('date_to', dateTo);
    if (filterBoard) params.append('board_id', filterBoard);
    if (filterMode) params.append('pricing_mode', filterMode);
    window.open(`${API}/reports/sessions/csv?${params}&token=${token}`, '_blank');
  };

  const presets = [
    { id: 'today', label: 'Heute' },
    { id: 'week', label: 'Woche' },
    { id: 'month', label: 'Monat' },
    { id: '', label: 'Alle' },
  ];

  const formatDate = (iso) => {
    if (!iso) return '-';
    return new Date(iso).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold text-zinc-100" data-testid="reports-heading">
          <BarChart3 className="w-6 h-6 inline mr-2 text-amber-500" />
          Berichte / Abrechnung
        </h2>
        <Button
          data-testid="export-csv-btn"
          onClick={exportCSV}
          className="bg-emerald-600 hover:bg-emerald-700 text-white"
        >
          <FileDown className="w-4 h-4 mr-2" />
          CSV Export
        </Button>
      </div>

      {/* Filters */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardContent className="pt-4">
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <p className="text-xs text-zinc-500 mb-1">Zeitraum</p>
              <div className="flex gap-1">
                {presets.map(p => (
                  <Button
                    key={p.id}
                    size="sm"
                    variant={preset === p.id ? 'default' : 'outline'}
                    className={preset === p.id ? 'bg-amber-500 text-black hover:bg-amber-600' : 'border-zinc-700 text-zinc-400'}
                    onClick={() => { setPreset(p.id); setDateFrom(''); setDateTo(''); }}
                    data-testid={`preset-${p.id || 'all'}`}
                  >
                    {p.label}
                  </Button>
                ))}
              </div>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-1">Von</p>
              <Input type="date" value={dateFrom} onChange={e => { setDateFrom(e.target.value); setPreset(''); }}
                className="bg-zinc-800 border-zinc-700 text-zinc-200 w-40" data-testid="date-from" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-1">Bis</p>
              <Input type="date" value={dateTo} onChange={e => { setDateTo(e.target.value); setPreset(''); }}
                className="bg-zinc-800 border-zinc-700 text-zinc-200 w-40" data-testid="date-to" />
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-1">Board</p>
              <select value={filterBoard} onChange={e => setFilterBoard(e.target.value)}
                className="bg-zinc-800 border border-zinc-700 text-zinc-200 rounded px-2 py-1.5 text-sm" data-testid="filter-board">
                <option value="">Alle</option>
                {boards.map(b => <option key={b.board_id} value={b.board_id}>{b.name}</option>)}
              </select>
            </div>
            <div>
              <p className="text-xs text-zinc-500 mb-1">Modus</p>
              <select value={filterMode} onChange={e => setFilterMode(e.target.value)}
                className="bg-zinc-800 border border-zinc-700 text-zinc-200 rounded px-2 py-1.5 text-sm" data-testid="filter-mode">
                <option value="">Alle</option>
                <option value="per_game">Pro Spiel</option>
                <option value="per_time">Pro Zeit</option>
                <option value="per_player">Pro Spieler</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="pt-4 text-center">
              <DollarSign className="w-5 h-5 mx-auto text-emerald-400 mb-1" />
              <p className="text-2xl font-bold text-zinc-100" data-testid="total-revenue">{summary.total_revenue.toFixed(2)} EUR</p>
              <p className="text-xs text-zinc-500">Umsatz gesamt</p>
            </CardContent>
          </Card>
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="pt-4 text-center">
              <Hash className="w-5 h-5 mx-auto text-blue-400 mb-1" />
              <p className="text-2xl font-bold text-zinc-100" data-testid="session-count">{summary.session_count}</p>
              <p className="text-xs text-zinc-500">Sessions</p>
            </CardContent>
          </Card>
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="pt-4 text-center">
              <TrendingUp className="w-5 h-5 mx-auto text-amber-400 mb-1" />
              <p className="text-2xl font-bold text-zinc-100" data-testid="avg-per-session">{summary.average_per_session.toFixed(2)} EUR</p>
              <p className="text-xs text-zinc-500">Durchschnitt/Session</p>
            </CardContent>
          </Card>
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="pt-4 text-center">
              <BarChart3 className="w-5 h-5 mx-auto text-purple-400 mb-1" />
              <div className="text-xs text-zinc-400 space-y-0.5" data-testid="revenue-by-board">
                {Object.entries(summary.revenue_by_board).map(([name, rev]) => (
                  <p key={name}>{name}: <span className="text-zinc-200 font-medium">{rev.toFixed(2)}</span></p>
                ))}
              </div>
              <p className="text-xs text-zinc-500 mt-1">Pro Board</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Sessions Table */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader className="pb-2">
          <CardTitle className="text-zinc-300 text-sm flex items-center gap-2">
            <Filter className="w-4 h-4" />
            {loading ? 'Laden...' : `${sessions.length} Sessions`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="sessions-table">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-xs">
                  <th className="text-left py-2 px-2">Datum</th>
                  <th className="text-left py-2 px-2">Board</th>
                  <th className="text-left py-2 px-2">Modus</th>
                  <th className="text-right py-2 px-2">Preis</th>
                  <th className="text-right py-2 px-2">Credits</th>
                  <th className="text-left py-2 px-2">Status</th>
                  <th className="text-left py-2 px-2">Erstellt von</th>
                </tr>
              </thead>
              <tbody>
                {sessions.slice(0, 100).map((s, i) => (
                  <tr key={i} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                    <td className="py-1.5 px-2 text-zinc-300 text-xs">{formatDate(s.date)}</td>
                    <td className="py-1.5 px-2 text-zinc-300">{s.board}</td>
                    <td className="py-1.5 px-2 text-zinc-400 text-xs">{s.pricing_mode}</td>
                    <td className="py-1.5 px-2 text-right text-zinc-200 font-mono">{s.price_total.toFixed(2)}</td>
                    <td className="py-1.5 px-2 text-right text-zinc-400 font-mono">{s.credits_total}</td>
                    <td className="py-1.5 px-2">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        s.status === 'finished' ? 'bg-emerald-900/40 text-emerald-400' :
                        s.status === 'active' ? 'bg-amber-900/40 text-amber-400' :
                        'bg-zinc-800 text-zinc-400'
                      }`}>{s.status}</span>
                    </td>
                    <td className="py-1.5 px-2 text-zinc-500 text-xs">{s.created_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {sessions.length > 100 && (
              <p className="text-xs text-zinc-500 mt-2">Zeigt 100 von {sessions.length}. CSV Export fuer alle.</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
