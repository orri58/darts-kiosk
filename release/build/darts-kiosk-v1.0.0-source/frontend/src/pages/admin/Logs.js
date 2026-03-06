import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { FileText, RefreshCw, Filter, Clock, User, Target } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminLogs() {
  const { token } = useAuth();
  const { t } = useI18n();
  const [auditLogs, setAuditLogs] = useState([]);
  const [sessionLogs, setSessionLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const [auditRes, sessionRes] = await Promise.all([
        axios.get(`${API}/logs/audit?limit=50`, { headers: { Authorization: `Bearer ${token}` } }),
        axios.get(`${API}/logs/sessions?limit=50`, { headers: { Authorization: `Bearer ${token}` } })
      ]);
      setAuditLogs(auditRes.data);
      setSessionLogs(sessionRes.data);
    } catch (error) {
      console.error('Failed to fetch logs:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getActionColor = (action) => {
    if (action.includes('login')) return 'text-blue-400';
    if (action.includes('unlock')) return 'text-emerald-400';
    if (action.includes('lock')) return 'text-red-400';
    if (action.includes('create')) return 'text-amber-400';
    if (action.includes('update')) return 'text-purple-400';
    if (action.includes('delete')) return 'text-red-500';
    return 'text-zinc-400';
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30';
      case 'finished': return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
      case 'expired': return 'bg-amber-500/20 text-amber-400 border-amber-500/30';
      case 'cancelled': return 'bg-red-500/20 text-red-400 border-red-500/30';
      default: return 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-amber-500 animate-spin" />
      </div>
    );
  }

  return (
    <div data-testid="admin-logs">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-heading uppercase tracking-wider text-white">{t('logs')}</h1>
          <p className="text-zinc-500">Audit- und Session-Protokolle</p>
        </div>
        <Button
          onClick={fetchLogs}
          variant="outline"
          className="border-zinc-700 text-zinc-400 hover:text-white"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Aktualisieren
        </Button>
      </div>

      <Tabs defaultValue="audit" className="space-y-6">
        <TabsList className="bg-zinc-900 border border-zinc-800 p-1">
          <TabsTrigger value="audit" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <FileText className="w-4 h-4 mr-2" />
            Audit Log
          </TabsTrigger>
          <TabsTrigger value="sessions" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black">
            <Target className="w-4 h-4 mr-2" />
            Sessions
          </TabsTrigger>
        </TabsList>

        {/* Audit Logs Tab */}
        <TabsContent value="audit">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white text-lg">Audit-Protokoll</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {auditLogs.length === 0 ? (
                  <p className="text-center text-zinc-500 py-8">Keine Einträge vorhanden</p>
                ) : (
                  auditLogs.map((log) => (
                    <div 
                      key={log.id} 
                      className="flex items-center gap-4 p-3 bg-zinc-800/50 rounded-sm border border-zinc-800 hover:border-zinc-700 transition-colors"
                    >
                      <div className="flex-shrink-0">
                        <Clock className="w-4 h-4 text-zinc-600" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`font-mono text-sm ${getActionColor(log.action)}`}>
                            {log.action}
                          </span>
                          {log.entity_type && (
                            <span className="text-xs text-zinc-600 bg-zinc-800 px-2 py-0.5 rounded">
                              {log.entity_type}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-1 text-xs text-zinc-500">
                          <User className="w-3 h-3" />
                          <span>{log.username || 'system'}</span>
                          <span>•</span>
                          <span>{formatDate(log.created_at)}</span>
                        </div>
                        {log.details && (
                          <div className="mt-1 text-xs text-zinc-600 font-mono truncate">
                            {JSON.stringify(log.details)}
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Session Logs Tab */}
        <TabsContent value="sessions">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white text-lg">Session-Verlauf</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3 max-h-[600px] overflow-y-auto">
                {sessionLogs.length === 0 ? (
                  <p className="text-center text-zinc-500 py-8">Keine Sessions vorhanden</p>
                ) : (
                  sessionLogs.map((session) => (
                    <div 
                      key={session.id} 
                      className="p-4 bg-zinc-800/50 rounded-sm border border-zinc-800 hover:border-zinc-700 transition-colors"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <span className="text-sm font-mono text-zinc-400">{session.id.slice(0, 8)}...</span>
                          <div className="flex items-center gap-2 mt-1">
                            <Target className="w-4 h-4 text-amber-500" />
                            <span className="text-white font-medium">{session.game_type || 'N/A'}</span>
                          </div>
                        </div>
                        <span className={`px-2 py-1 text-xs uppercase rounded-sm border ${getStatusColor(session.status)}`}>
                          {session.status}
                        </span>
                      </div>
                      
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                        <div>
                          <p className="text-zinc-600 text-xs uppercase">Modus</p>
                          <p className="text-zinc-300">{session.pricing_mode}</p>
                        </div>
                        <div>
                          <p className="text-zinc-600 text-xs uppercase">Spieler</p>
                          <p className="text-zinc-300">{session.players_count}</p>
                        </div>
                        <div>
                          <p className="text-zinc-600 text-xs uppercase">Credits</p>
                          <p className="text-zinc-300">{session.credits_remaining} / {session.credits_total}</p>
                        </div>
                        <div>
                          <p className="text-zinc-600 text-xs uppercase">Preis</p>
                          <p className="text-amber-500 font-mono">{session.price_total?.toFixed(2)} €</p>
                        </div>
                      </div>
                      
                      <div className="mt-3 pt-3 border-t border-zinc-800 flex items-center gap-4 text-xs text-zinc-500">
                        <span>Start: {formatDate(session.started_at)}</span>
                        {session.ended_at && <span>Ende: {formatDate(session.ended_at)}</span>}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
