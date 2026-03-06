import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { TrendingUp, RefreshCw, Euro, Calendar, Target } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';

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
        headers: { Authorization: `Bearer ${token}` }
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

  // Prepare chart data
  const chartData = data?.by_date ? Object.entries(data.by_date).map(([date, info]) => ({
    date: date.slice(5), // MM-DD format
    total: info.total,
    count: info.count
  })).reverse() : [];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <div data-testid="admin-revenue">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-heading uppercase tracking-wider text-white">{t('revenue')}</h1>
          <p className="text-zinc-500">Einnahmen-Übersicht</p>
        </div>
        <div className="flex gap-2">
          {[7, 14, 30].map((d) => (
            <Button
              key={d}
              variant={days === d ? 'default' : 'outline'}
              onClick={() => setDays(d)}
              className={days === d ? 'bg-amber-500 text-black' : 'border-zinc-700 text-zinc-400'}
            >
              {d} Tage
            </Button>
          ))}
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-sm bg-amber-500/20 flex items-center justify-center">
                <Euro className="w-6 h-6 text-amber-500" />
              </div>
              <div>
                <p className="text-sm text-zinc-500 uppercase">Gesamtumsatz</p>
                <p className="text-3xl font-mono font-bold text-white" data-testid="total-revenue">
                  {(data?.total_revenue || 0).toFixed(2)} €
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-sm bg-emerald-500/20 flex items-center justify-center">
                <Target className="w-6 h-6 text-emerald-500" />
              </div>
              <div>
                <p className="text-sm text-zinc-500 uppercase">Sessions</p>
                <p className="text-3xl font-mono font-bold text-white" data-testid="total-sessions">
                  {data?.total_sessions || 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="p-6">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-sm bg-blue-500/20 flex items-center justify-center">
                <TrendingUp className="w-6 h-6 text-blue-500" />
              </div>
              <div>
                <p className="text-sm text-zinc-500 uppercase">Durchschnitt/Session</p>
                <p className="text-3xl font-mono font-bold text-white">
                  {data?.total_sessions > 0 
                    ? (data.total_revenue / data.total_sessions).toFixed(2) 
                    : '0.00'} €
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Chart */}
      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Calendar className="w-5 h-5 text-amber-500" />
            Umsatz pro Tag
          </CardTitle>
        </CardHeader>
        <CardContent>
          {chartData.length > 0 ? (
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis 
                    dataKey="date" 
                    stroke="#71717a"
                    tick={{ fill: '#71717a', fontSize: 12 }}
                  />
                  <YAxis 
                    stroke="#71717a"
                    tick={{ fill: '#71717a', fontSize: 12 }}
                    tickFormatter={(value) => `${value}€`}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: '#18181b', 
                      border: '1px solid #27272a',
                      borderRadius: '4px'
                    }}
                    labelStyle={{ color: '#e4e4e7' }}
                    itemStyle={{ color: '#f59e0b' }}
                    formatter={(value) => [`${value.toFixed(2)} €`, 'Umsatz']}
                  />
                  <Bar 
                    dataKey="total" 
                    fill="#f59e0b" 
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-[300px] flex items-center justify-center text-zinc-500">
              <div className="text-center">
                <TrendingUp className="w-16 h-16 mx-auto mb-4 text-zinc-700" />
                <p>Keine Umsatzdaten im gewählten Zeitraum</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Daily Breakdown */}
      {chartData.length > 0 && (
        <Card className="bg-zinc-900 border-zinc-800 mt-6">
          <CardHeader>
            <CardTitle className="text-white text-lg">Tagesübersicht</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {chartData.slice().reverse().map((day) => (
                <div 
                  key={day.date} 
                  className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm border border-zinc-800"
                >
                  <div className="flex items-center gap-3">
                    <Calendar className="w-4 h-4 text-zinc-600" />
                    <span className="text-zinc-300 font-mono">{day.date}</span>
                  </div>
                  <div className="flex items-center gap-6">
                    <span className="text-sm text-zinc-500">
                      {day.count} Sessions
                    </span>
                    <span className="text-amber-500 font-mono font-bold">
                      {day.total.toFixed(2)} €
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
