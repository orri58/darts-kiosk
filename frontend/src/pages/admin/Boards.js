import { useCallback, useEffect, useMemo, useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Copy, ExternalLink, Link2, MapPin, Pencil, Plus, RefreshCw, Shield, Target, Trash2, Wifi } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
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

const STATUS_TONES = {
  locked: 'neutral',
  unlocked: 'amber',
  in_game: 'emerald',
  offline: 'red',
};

export default function AdminBoards() {
  const { token, isAdmin } = useAuth();
  const { t } = useI18n();
  const [boards, setBoards] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingBoard, setEditingBoard] = useState(null);
  const [formData, setFormData] = useState({
    board_id: '',
    name: '',
    location: '',
    autodarts_target_url: '',
    agent_api_base_url: '',
  });

  const fetchBoards = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/boards`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setBoards(response.data || []);
    } catch (error) {
      console.error('Failed to fetch boards:', error);
      toast.error('Boards konnten nicht geladen werden');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchBoards();
  }, [fetchBoards]);

  const metrics = useMemo(() => {
    return {
      total: boards.length,
      master: boards.filter((board) => board.is_master).length,
      remote: boards.filter((board) => board.agent_api_base_url).length,
      configuredTargets: boards.filter((board) => board.autodarts_target_url).length,
    };
  }, [boards]);

  const openCreateDialog = () => {
    setEditingBoard(null);
    setFormData({
      board_id: `BOARD-${boards.length + 1}`,
      name: `Dartboard ${boards.length + 1}`,
      location: '',
      autodarts_target_url: 'https://play.autodarts.io',
      agent_api_base_url: '',
    });
    setShowDialog(true);
  };

  const openEditDialog = (board) => {
    setEditingBoard(board);
    setFormData({
      board_id: board.board_id,
      name: board.name,
      location: board.location || '',
      autodarts_target_url: board.autodarts_target_url || '',
      agent_api_base_url: board.agent_api_base_url || '',
    });
    setShowDialog(true);
  };

  const handleSubmit = async () => {
    try {
      const headers = { Authorization: `Bearer ${token}` };
      if (editingBoard) {
        await axios.put(
          `${API}/boards/${editingBoard.board_id}`,
          {
            name: formData.name,
            location: formData.location,
            autodarts_target_url: formData.autodarts_target_url,
            agent_api_base_url: formData.agent_api_base_url,
          },
          { headers }
        );
        toast.success('Board aktualisiert');
      } else {
        await axios.post(`${API}/boards`, formData, { headers });
        toast.success('Board erstellt');
      }
      setShowDialog(false);
      fetchBoards();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Speichern');
    }
  };

  const handleDelete = async (board) => {
    if (!window.confirm(`Board "${board.name}" wirklich löschen?`)) return;

    try {
      await axios.delete(`${API}/boards/${board.board_id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success('Board gelöscht');
      fetchBoards();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Löschen');
    }
  };

  const copyToClipboard = async (value, label) => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label} kopiert`);
    } catch {
      toast.error('Kopieren fehlgeschlagen');
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
    <AdminPage
      eyebrow="Board topology"
      title={t('boards')}
      description="Boards, Standorte, Autodarts-Ziele und Agent-Endpunkte in einer produktionsnäheren Oberfläche. Kein blindes CRUD mehr — die Seite zeigt jetzt auch, was wirklich konfiguriert ist."
      actions={
        <div className="flex flex-wrap gap-2">
          <Button onClick={fetchBoards} variant="outline" className="border-zinc-700 text-zinc-300 hover:text-white">
            <RefreshCw className="w-4 h-4 mr-2" /> Aktualisieren
          </Button>
          {isAdmin && (
            <Button onClick={openCreateDialog} data-testid="add-board-btn" className="bg-amber-500 hover:bg-amber-400 text-black">
              <Plus className="w-4 h-4 mr-2" /> Neues Board
            </Button>
          )}
        </div>
      }
    >
      <AdminStatsGrid>
        <AdminStatCard icon={Target} label="Boards gesamt" value={metrics.total} hint="Lokale Board-Definitionen" tone="amber" />
        <AdminStatCard icon={Shield} label="Master-Boards" value={metrics.master} hint="Boards mit Master-Rolle" tone="blue" />
        <AdminStatCard icon={Link2} label="Autodarts-Ziele" value={metrics.configuredTargets} hint="Mit Ziel-URL gepflegt" tone="emerald" />
        <AdminStatCard icon={Wifi} label="Remote Agents" value={metrics.remote} hint="Mit Agent-API-Endpunkt" tone="violet" />
      </AdminStatsGrid>

      <AdminSection title="Board-Verzeichnis" description="Jedes Board mit seiner tatsächlichen Konfiguration, nicht nur Name und Status.">
        {boards.length === 0 ? (
          <AdminEmptyState
            icon={Target}
            title="Noch keine Boards angelegt"
            description="Lege das erste Board an, damit Dashboard, Kiosk und Autodarts-Pairing sinnvoll funktionieren."
            action={
              isAdmin ? (
                <Button onClick={openCreateDialog} className="bg-amber-500 hover:bg-amber-400 text-black">
                  <Plus className="w-4 h-4 mr-2" /> Erstes Board anlegen
                </Button>
              ) : null
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {boards.map((board) => (
              <div key={board.id} className="rounded-3xl border border-zinc-800 bg-zinc-900/60 p-5 shadow-[0_16px_48px_rgba(0,0,0,0.24)]" data-testid={`board-item-${board.board_id}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-lg font-semibold text-white">{board.name}</p>
                      <AdminStatusPill tone={STATUS_TONES[board.status] || 'neutral'}>{board.status}</AdminStatusPill>
                      {board.is_master && <AdminStatusPill tone="amber">Master</AdminStatusPill>}
                    </div>
                    <p className="mt-1 text-sm font-mono text-zinc-500">{board.board_id}</p>
                  </div>

                  {isAdmin && (
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="icon" onClick={() => openEditDialog(board)} data-testid={`edit-board-${board.board_id}`} className="text-zinc-400 hover:text-amber-400">
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDelete(board)} data-testid={`delete-board-${board.board_id}`} className="text-zinc-400 hover:text-red-400">
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  )}
                </div>

                <div className="mt-4 space-y-3">
                  <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                    <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Standort</p>
                    <div className="mt-2 flex items-center gap-2 text-zinc-200">
                      <MapPin className="w-4 h-4 text-zinc-500" />
                      <span>{board.location || 'Nicht gesetzt'}</span>
                    </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Autodarts URL</p>
                        {board.autodarts_target_url && (
                          <button type="button" onClick={() => copyToClipboard(board.autodarts_target_url, 'Autodarts URL')} className="text-zinc-500 hover:text-zinc-200">
                            <Copy className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                      <p className="mt-2 break-all text-sm text-zinc-200">{board.autodarts_target_url || 'Nicht gesetzt'}</p>
                    </div>
                    <div className="rounded-2xl border border-zinc-800 bg-zinc-950/80 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <p className="text-[11px] uppercase tracking-[0.22em] text-zinc-600">Agent API</p>
                        {board.agent_api_base_url && (
                          <button type="button" onClick={() => copyToClipboard(board.agent_api_base_url, 'Agent API URL')} className="text-zinc-500 hover:text-zinc-200">
                            <Copy className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                      <p className="mt-2 break-all text-sm text-zinc-200">{board.agent_api_base_url || 'Lokal / nicht gesetzt'}</p>
                    </div>
                  </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-2">
                  <Button asChild variant="outline" className="border-zinc-700 text-zinc-200 hover:text-white">
                    <a href={`/kiosk/${board.board_id}`} target="_blank" rel="noreferrer">
                      Kiosk <ExternalLink className="w-4 h-4 ml-2" />
                    </a>
                  </Button>
                  {board.autodarts_target_url && (
                    <Button asChild variant="outline" className="border-zinc-700 text-zinc-200 hover:text-white">
                      <a href={board.autodarts_target_url} target="_blank" rel="noreferrer">
                        Autodarts <ExternalLink className="w-4 h-4 ml-2" />
                      </a>
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </AdminSection>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="bg-zinc-950 border-zinc-800 text-white sm:max-w-xl">
          <DialogHeader>
            <DialogTitle className="font-heading uppercase tracking-[0.12em] text-white">
              {editingBoard ? 'Board bearbeiten' : 'Neues Board'}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {!editingBoard && (
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Board ID</label>
                <Input value={formData.board_id} onChange={(e) => setFormData({ ...formData, board_id: e.target.value })} placeholder="BOARD-1" data-testid="board-id-input" className="bg-zinc-900 border-zinc-700 text-white" />
              </div>
            )}
            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider">Name</label>
              <Input value={formData.name} onChange={(e) => setFormData({ ...formData, name: e.target.value })} placeholder="Dartboard 1" data-testid="board-name-input" className="bg-zinc-900 border-zinc-700 text-white" />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider">Standort</label>
              <Input value={formData.location} onChange={(e) => setFormData({ ...formData, location: e.target.value })} placeholder="Erdgeschoss, neben der Bar" data-testid="board-location-input" className="bg-zinc-900 border-zinc-700 text-white" />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider">Autodarts URL</label>
              <Input value={formData.autodarts_target_url} onChange={(e) => setFormData({ ...formData, autodarts_target_url: e.target.value })} placeholder="https://play.autodarts.io" data-testid="board-autodarts-input" className="bg-zinc-900 border-zinc-700 text-white" />
            </div>
            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider">Agent API URL (optional)</label>
              <Input value={formData.agent_api_base_url} onChange={(e) => setFormData({ ...formData, agent_api_base_url: e.target.value })} placeholder="http://192.168.1.100:8001" data-testid="board-agent-input" className="bg-zinc-900 border-zinc-700 text-white" />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setShowDialog(false)} className="border-zinc-700 text-zinc-300">Abbrechen</Button>
            <Button onClick={handleSubmit} data-testid="save-board-btn" className="bg-amber-500 hover:bg-amber-400 text-black">Speichern</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AdminPage>
  );
}
