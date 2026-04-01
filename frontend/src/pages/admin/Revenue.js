import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { Calendar, RefreshCw, Target, TrendingUp, Wallet } from 'lucide-react';
import { BarChart, Bar, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Button } from '../../components/ui/button';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';
import { AdminPage, AdminSection, AdminStatCard, AdminStatsGrid, AdminStatusPill } from '../../components/admin/AdminShell';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminRevenue() {
  const { token } = useAuth();
  const { t } = useI18n();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [days, setDays] = useState(7);

  const fetchRevenue = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/revenue/summary?days=${days}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setData(response.data);
    } catch (error) {
      console.error('Failed to fetch revenue:', error);
    } finally {
      setLoading(false);
    }
  }, [token, days]);

  useEffect(() => {
    fetchRevenue();
  }, [fetchRevenue]);

  const chartData = useMemo(() => {
    return data?.by_date
      ? Object.entries(data.by_date)
          .map(([date, info]) => ({
            date,
            shortDate: date.slice(5),
            total: info.total,
            count: info.count,
          }))
          .reverse()
      : [];
  }, [data]);

  const topBoards = useMemo(() => {
    return Object.entries(data?.by_board || {})
      .map(([name, revenue]) => ({ name, revenue }))
      .sort((a, b) => b.revenue - a.revenue)
      .slice(0, 5);
  }, [data]);

  const averagePerSession = data?.total_sessions > 0 ? data.total_revenue / data.total_sessions : 0;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <AdminPage
      eyebrow="Venue revenue"
      title={t('revenue')}
      description="Sauberer Blick auf gebuchte lokale Sessions — inklusive Board-Verteilung, Tagesverlauf und Durchschnittswerten statt nur einer einsamen Balkengrafik."
      actions={
        <div className="flex flex-wrap gap-2">
          {[7, 14, 30].map((value) => (
            <Button
              key={value}
              variant={days === value ? 'default' : 'outline'}
              onClick={() => setDays(value)}
              className={days === value ? 'bg-amber-500 text-black hover:bg-amber-400' : 'border-zinc-700 text-zinc-300 hover:text-white'}
            >
              {value} Tage
            </Button>
          ))}
          <Button onClick={fetchRevenue} variant="outline" className="border-zinc-700 text-zinc-300 hover:text-white">
            <RefreshCw className="w-4 h-4 mr-2" /> Aktualisieren
          </Button>
        </div>
      }
    >
      <AdminStatsGrid>
        <AdminStatCard icon={Wallet} label="Gebuchter Umsatz" value={`${(data?.total_revenue || 0).toFixed(2)} €`} hint={`Zeitraum: ${days} Tage`} tone="emerald" />
        <AdminStatCard icon={Target} label="Abgeschlossene Sessions" value={data?.total_sessions || 0} hint="Nur beendete / expirte / abgebrochene Sessions" tone="amber" />
        <AdminStatCard icon={TrendingUp} label="Ø pro Session" value={`${averagePerSession.toFixed(2)} €`} hint="Lokaler Venue-Durchschnitt" tone="blue" />
        <AdminStatCard icon={Calendar} label="Aktive Tage" value={chartData.length} hint="Tage mit gebuchtem Umsatz im Fenster" tone="violet" />
      </AdminStatsGrid>

      <div className="grid gap-6 xl:grid-cols-[1.35fr,0.65fr]">
        <AdminSection title="Umsatz pro Tag" description="Wie sich die gebuchten Umsätze im gewählten Fenster verteilen.">
          {chartData.length > 0 ? (
            <div className="h-[340px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="shortDate" stroke="#71717a" tick={{ fill: '#71717a', fontSize: 12 }} />
                  <YAxis stroke="#71717a" tick={{ fill: '#71717a', fontSize: 12 }} tickFormatter={(value) => `${value}€`} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#09090b',
                      border: '1px solid #27272a',
                      borderRadius: '16px',
                    }}
                    labelStyle={{ color: '#e4e4e7' }}
                    itemStyle={{ color: '#f59e0b' }}
                    formatter={(value, name) => [name === 'count' ? value : `${Number(value).toFixed(2)} €`, name === 'count' ? 'Sessions' : 'Umsatz']}
                    labelFormatter={(label, payload) => payload?.[0]?.payload?.date || label}
                  />
                  <Bar dataKey="total" fill="#f59e0b" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex h-[340px] items-center justify-center rounded-3xl border border-dashed border-zinc-800 bg-zinc-950/50 text-zinc-500">
              Keine Umsatzdaten im gewählten Zeitraum.
            </div>
          )}
        </AdminSection>

        <div className="space-y-6">
          <AdminSection title="Top Boards" description="Welche Boards den größten Anteil tragen.">
            {topBoards.length > 0 ? (
              <div className="space-y-3">
                {topBoards.map((board, index) => (
                  <div key={board.name} className="rounded-2xl border border-zinc-800 bg-zinc-900/70 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm text-zinc-500">Platz {index + 1}</p>
                        <p className="font-medium text-white">{board.name}</p>
                      </div>
                      <AdminStatusPill tone={index === 0 ? 'emerald' : 'neutral'}>{board.revenue.toFixed(2)} €</AdminStatusPill>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-zinc-500">Noch keine Board-Umsätze im aktuellen Fenster.</p>
            )}
          </AdminSection>

          <AdminSection title="Operator-Hinweis" description="Was diese Ansicht absichtlich nicht tut.">
            <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-4 text-sm leading-6 text-zinc-400">
              Diese Revenue-Ansicht bleibt lokal und bewusst pragmatisch: sie zeigt gebuchte Sessionumsätze pro Venue-Fenster. Tiefere Abrechnung, Lizenz- oder Zentralsync-Themen gehören später in einen separaten Layer — nicht hier mitten in die Tresen-UI.
            </div>
          </AdminSection>
        </div>
      </div>

      {chartData.length > 0 && (
        <AdminSection title="Tagesliste" description="Schnelle Nachkontrolle ohne CSV-Export.">
          <div className="space-y-3">
            {chartData.slice().reverse().map((day) => (
              <div key={day.date} className="flex flex-col gap-3 rounded-2xl border border-zinc-800 bg-zinc-900/60 px-4 py-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="font-medium text-white">{day.date}</p>
                  <p className="text-sm text-zinc-500">{day.count} Sessions</p>
                </div>
                <AdminStatusPill tone="amber">{day.total.toFixed(2)} €</AdminStatusPill>
              </div>
            ))}
          </div>
        </AdminSection>
      )}
    </AdminPage>
  );
}
