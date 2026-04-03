import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  BarChart3,
  CalendarRange,
  FileDown,
  Filter,
  Hash,
  RefreshCw,
  Target,
  Wallet,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import {
  AdminEmptyState,
  AdminPage,
  AdminSection,
  AdminStatCard,
  AdminStatsGrid,
  AdminStatusPill,
} from '../../components/admin/AdminShell';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const MODE_LABELS = {
  per_game: 'Spielbasiert (Legacy)',
  per_time: 'Zeitbasiert (Legacy)',
  per_player: 'Credits / Matchstart',
};

const STATUS_META = {
  active: { label: 'Aktiv', tone: 'amber' },
  finished: { label: 'Beendet', tone: 'emerald' },
  expired: { label: 'Abgelaufen', tone: 'blue' },
  aborted: { label: 'Abgebrochen', tone: 'red' },
  cancelled: { label: 'Abgebrochen', tone: 'red' },
};

function buildReportParams({ preset, dateFrom, dateTo, filterBoard, filterMode }) {
  const params = new URLSearchParams();

  if (preset && !dateFrom && !dateTo) params.append('preset', preset);
  if (dateFrom) params.append('date_from', `${dateFrom}T00:00:00`);
  if (dateTo) params.append('date_to', `${dateTo}T23:59:59`);
  if (filterBoard) params.append('board_id', filterBoard);
  if (filterMode) params.append('pricing_mode', filterMode);

  return params;
}

function formatDateTime(value) {
  if (!value) return '–';
  return new Date(value).toLocaleString('de-DE', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatMoney(value) {
  return `${Number(value || 0).toFixed(2)} €`;
}

function formatSessionVolume(session) {
  if (session.pricing_mode === 'per_time') {
    return session.minutes_total ? `${session.minutes_total} min` : 'Zeit offen';
  }

  if (session.credits_total || session.credits_remaining === 0) {
    return `${session.credits_remaining ?? 0} / ${session.credits_total ?? 0}`;
  }

  return '–';
}

export default function Reports() {
  const { token } = useAuth();
  const { t } = useI18n();

  const [sessions, setSessions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [boards, setBoards] = useState([]);

  const [preset, setPreset] = useState('month');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [filterBoard, setFilterBoard] = useState('');
  const [filterMode, setFilterMode] = useState('');

  useEffect(() => {
    const fetchBoards = async () => {
      try {
        const res = await axios.get(`${API}/boards`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        setBoards(res.data || []);
      } catch {
        /* ignore */
      }
    };

    fetchBoards();
  }, [token]);

  const fetchReport = useCallback(async () => {
    setLoading(true);
    try {
      const params = buildReportParams({ preset, dateFrom, dateTo, filterBoard, filterMode });
      const res = await axios.get(`${API}/reports/sessions?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setSessions(res.data.sessions || []);
      setSummary(res.data.summary || null);
    } catch {
      toast.error('Report konnte nicht geladen werden');
    } finally {
      setLoading(false);
    }
  }, [token, preset, dateFrom, dateTo, filterBoard, filterMode]);

  useEffect(() => {
    fetchReport();
  }, [fetchReport]);

  const exportCSV = async () => {
    const params = buildReportParams({ preset, dateFrom, dateTo, filterBoard, filterMode });
    try {
      const res = await axios.get(`${API}/reports/sessions/csv?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob',
      });
      const blob = new Blob([res.data], { type: 'text/csv;charset=utf-8' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `darts-sessions-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      toast.error('CSV-Export fehlgeschlagen');
    }
  };

  const clearFilters = () => {
    setPreset('month');
    setDateFrom('');
    setDateTo('');
    setFilterBoard('');
    setFilterMode('');
  };

  const presets = [
    { id: 'today', label: 'Heute' },
    { id: 'week', label: '7 Tage' },
    { id: 'month', label: '30 Tage' },
    { id: '', label: 'Alle' },
  ];

  const metrics = useMemo(() => {
    const activeCount = sessions.filter((session) => session.status === 'active').length;
    const uniqueBoards = new Set(sessions.map((session) => session.board_id || session.board).filter(Boolean)).size;
    const boardRanking = Object.entries(summary?.revenue_by_board || {})
      .map(([board, revenue]) => ({ board, revenue: Number(revenue || 0) }))
      .sort((a, b) => b.revenue - a.revenue);

    return {
      activeCount,
      uniqueBoards,
      topBoard: boardRanking[0] || null,
      boardRanking,
    };
  }, [sessions, summary]);

  const scopeLabel = useMemo(() => {
    if (dateFrom || dateTo) {
      if (dateFrom && dateTo) return `${dateFrom} → ${dateTo}`;
      if (dateFrom) return `ab ${dateFrom}`;
      return `bis ${dateTo}`;
    }

    if (preset === 'today') return 'heute';
    if (preset === 'week') return 'letzte 7 Tage';
    if (preset === 'month') return 'letzte 30 Tage';
    return 'gesamter Bestand';
  }, [preset, dateFrom, dateTo]);

  if (loading && !summary) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <AdminPage
      eyebrow="Local bookkeeping"
      title={t('reports')}
      description="Session-Export und Nacharbeit für den Venue-Betrieb. Die Seite zeigt lokale Session-Daten mit Status und Filtern — kein vollwertiges FiBu-System und kein zentraler Lizenzreport."
      actions={
        <div className="flex flex-wrap gap-2">
          <Button
            onClick={fetchReport}
            variant="outline"
            className="border-zinc-700 text-zinc-300 hover:text-white"
          >
            <RefreshCw className="w-4 h-4 mr-2" /> Aktualisieren
          </Button>
          <Button
            data-testid="export-csv-btn"
            onClick={exportCSV}
            className="bg-emerald-600 hover:bg-emerald-500 text-white"
          >
            <FileDown className="w-4 h-4 mr-2" /> CSV exportieren
          </Button>
        </div>
      }
    >
      <AdminStatsGrid>
        <AdminStatCard
          icon={Wallet}
          label="Gebuchter Umsatz"
          value={formatMoney(summary?.total_revenue || 0)}
          hint={`Scope: ${scopeLabel}`}
          tone="emerald"
        />
        <AdminStatCard
          icon={Hash}
          label="Sessions im Report"
          value={summary?.session_count || 0}
          hint="Lokale Session-Einträge nach Filter"
          tone="amber"
        />
        <AdminStatCard
          icon={BarChart3}
          label="Ø pro Session"
          value={formatMoney(summary?.average_per_session || 0)}
          hint="Rein aus den geladenen Session-Daten berechnet"
          tone="blue"
        />
        <AdminStatCard
          icon={Target}
          label="Boards im Scope"
          value={metrics.uniqueBoards}
          hint={metrics.topBoard ? `Top Board: ${metrics.topBoard.board}` : 'Kein Board-Umsatz im Filter'}
          tone="violet"
        />
      </AdminStatsGrid>

      <div className="grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
        <AdminSection
          title="Filter & Export"
          description="Preset-Filter für schnelle Nacharbeit oder ein eigener Zeitraum für Tagesabschluss und CSV-Export."
          actions={
            <Button
              variant="outline"
              size="sm"
              onClick={clearFilters}
              className="border-zinc-700 text-zinc-300 hover:text-white"
            >
              Filter zurücksetzen
            </Button>
          }
        >
          <div className="space-y-5">
            <div>
              <p className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Schnellfenster</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {presets.map((item) => (
                  <Button
                    key={item.id || 'all'}
                    size="sm"
                    variant={preset === item.id ? 'default' : 'outline'}
                    onClick={() => {
                      setPreset(item.id);
                      setDateFrom('');
                      setDateTo('');
                    }}
                    className={
                      preset === item.id
                        ? 'bg-amber-500 text-black hover:bg-amber-400'
                        : 'border-zinc-700 text-zinc-300 hover:text-white'
                    }
                    data-testid={`preset-${item.id || 'all'}`}
                  >
                    {item.label}
                  </Button>
                ))}
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <div>
                <label className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Von</label>
                <Input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => {
                    setDateFrom(e.target.value);
                    setPreset('');
                  }}
                  className="mt-2 bg-zinc-950 border-zinc-800 text-zinc-200"
                  data-testid="date-from"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Bis</label>
                <Input
                  type="date"
                  value={dateTo}
                  onChange={(e) => {
                    setDateTo(e.target.value);
                    setPreset('');
                  }}
                  className="mt-2 bg-zinc-950 border-zinc-800 text-zinc-200"
                  data-testid="date-to"
                />
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Board</label>
                <select
                  value={filterBoard}
                  onChange={(e) => setFilterBoard(e.target.value)}
                  className="mt-2 h-10 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 text-sm text-zinc-200"
                  data-testid="filter-board"
                >
                  <option value="">Alle Boards</option>
                  {boards.map((board) => (
                    <option key={board.board_id} value={board.board_id}>
                      {board.name}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-[11px] uppercase tracking-[0.24em] text-zinc-500">Modus</label>
                <select
                  value={filterMode}
                  onChange={(e) => setFilterMode(e.target.value)}
                  className="mt-2 h-10 w-full rounded-md border border-zinc-800 bg-zinc-950 px-3 text-sm text-zinc-200"
                  data-testid="filter-mode"
                >
                  <option value="">Alle Modi</option>
                  <option value="per_player">Credits / Matchstart</option>
                  <option value="per_game">Spielbasiert (Legacy)</option>
                  <option value="per_time">Zeitbasiert (Legacy)</option>
                </select>
              </div>
            </div>

            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4 text-sm leading-6 text-zinc-400">
              Diese Oberfläche liest ausschließlich lokale Session-Datensätze. Sie ist gut für Schichtabschluss,
              CSV-Export und schnelle Rückfragen — aber nicht dafür gedacht, externe Buchhaltung oder zentrale
              Lizenz-/Fleet-Themen vorzutäuschen.
            </div>
          </div>
        </AdminSection>

        <div className="space-y-6">
          <AdminSection title="Board-Umsatz im Filter" description="Welche Boards im aktuellen Fenster den größten Anteil tragen.">
            {metrics.boardRanking.length > 0 ? (
              <div className="space-y-3" data-testid="revenue-by-board">
                {metrics.boardRanking.slice(0, 6).map((entry, index) => (
                  <div
                    key={entry.board}
                    className="flex items-center justify-between gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3"
                  >
                    <div className="min-w-0">
                      <p className="text-xs uppercase tracking-[0.22em] text-zinc-600">Platz {index + 1}</p>
                      <p className="truncate font-medium text-white">{entry.board}</p>
                    </div>
                    <AdminStatusPill tone={index === 0 ? 'emerald' : 'neutral'}>
                      {formatMoney(entry.revenue)}
                    </AdminStatusPill>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-500">Noch keine Umsätze im aktuellen Filterfenster.</p>
            )}
          </AdminSection>

          <AdminSection title="Report-Status" description="Schnelle Einordnung, bevor jemand falsche Schlüsse zieht.">
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                <span className="text-zinc-400">Offene Sessions im Report</span>
                <AdminStatusPill tone={metrics.activeCount > 0 ? 'amber' : 'neutral'}>
                  {metrics.activeCount}
                </AdminStatusPill>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                <span className="text-zinc-400">Datenquelle</span>
                <AdminStatusPill tone="blue">Lokal</AdminStatusPill>
              </div>
              <div className="flex items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                <span className="text-zinc-400">CSV enthält</span>
                <span className="font-medium text-white">alle Treffer, nicht nur die ersten 100</span>
              </div>
            </div>
          </AdminSection>
        </div>
      </div>

      <AdminSection
        title="Session-Liste"
        description="Die ersten 100 Treffer direkt im Browser. Für Vollständigkeit und Weitergabe ist der CSV-Export der richtige Weg."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <AdminStatusPill tone="blue">
              <CalendarRange className="w-3 h-3" /> {scopeLabel}
            </AdminStatusPill>
            {loading && (
              <AdminStatusPill tone="amber">
                <RefreshCw className="w-3 h-3 animate-spin" /> lädt
              </AdminStatusPill>
            )}
          </div>
        }
      >
        {sessions.length === 0 ? (
          <AdminEmptyState
            icon={Filter}
            title="Keine Sessions im aktuellen Filter"
            description="Entweder gab es in diesem Fenster keine lokalen Verkäufe oder die Filter sind gerade zu eng gesetzt."
          />
        ) : (
          <div className="space-y-4">
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm" data-testid="sessions-table">
                <thead>
                  <tr className="border-b border-zinc-800 text-left text-[11px] uppercase tracking-[0.22em] text-zinc-500">
                    <th className="px-3 py-3">Start</th>
                    <th className="px-3 py-3">Board</th>
                    <th className="px-3 py-3">Modus</th>
                    <th className="px-3 py-3 text-right">Preis</th>
                    <th className="px-3 py-3 text-right">Umfang</th>
                    <th className="px-3 py-3 text-right">Spieler</th>
                    <th className="px-3 py-3">Status</th>
                    <th className="px-3 py-3">Erstellt von</th>
                  </tr>
                </thead>
                <tbody>
                  {sessions.slice(0, 100).map((session) => {
                    const status = STATUS_META[session.status] || {
                      label: session.status || 'Unbekannt',
                      tone: 'neutral',
                    };

                    return (
                      <tr key={session.session_id} className="border-b border-zinc-900 align-top hover:bg-zinc-900/40">
                        <td className="px-3 py-3 text-zinc-300">{formatDateTime(session.date)}</td>
                        <td className="px-3 py-3">
                          <div>
                            <p className="font-medium text-white">{session.board}</p>
                            <p className="text-xs font-mono text-zinc-500">{session.board_id}</p>
                          </div>
                        </td>
                        <td className="px-3 py-3 text-zinc-400">{MODE_LABELS[session.pricing_mode] || session.pricing_mode}</td>
                        <td className="px-3 py-3 text-right font-medium text-zinc-100">{formatMoney(session.price_total)}</td>
                        <td className="px-3 py-3 text-right text-zinc-400">{formatSessionVolume(session)}</td>
                        <td className="px-3 py-3 text-right text-zinc-400">{session.players_count || '–'}</td>
                        <td className="px-3 py-3">
                          <div className="space-y-1">
                            <AdminStatusPill tone={status.tone}>{status.label}</AdminStatusPill>
                            {session.ended_reason ? (
                              <p className="text-xs text-zinc-500">Grund: {session.ended_reason}</p>
                            ) : null}
                          </div>
                        </td>
                        <td className="px-3 py-3 text-zinc-500">{session.created_by || '–'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            {sessions.length > 100 && (
              <p className="text-sm text-zinc-500">
                Browseransicht zeigt 100 von {sessions.length} Treffern. Der CSV-Export enthält den vollständigen Filterumfang.
              </p>
            )}
          </div>
        )}
      </AdminSection>
    </AdminPage>
  );
}
