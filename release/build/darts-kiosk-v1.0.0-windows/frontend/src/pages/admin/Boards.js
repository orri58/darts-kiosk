import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Target, Plus, Edit, Trash2, RefreshCw, MapPin, Link } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../../components/ui/dialog';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

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
    agent_api_base_url: ''
  });

  const fetchBoards = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/boards`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setBoards(response.data);
    } catch (error) {
      console.error('Failed to fetch boards:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchBoards();
  }, [fetchBoards]);

  const openCreateDialog = () => {
    setEditingBoard(null);
    setFormData({
      board_id: `BOARD-${boards.length + 1}`,
      name: `Dartboard ${boards.length + 1}`,
      location: '',
      autodarts_target_url: 'https://play.autodarts.io',
      agent_api_base_url: ''
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
      agent_api_base_url: board.agent_api_base_url || ''
    });
    setShowDialog(true);
  };

  const handleSubmit = async () => {
    try {
      if (editingBoard) {
        await axios.put(`${API}/boards/${editingBoard.board_id}`, {
          name: formData.name,
          location: formData.location,
          autodarts_target_url: formData.autodarts_target_url,
          agent_api_base_url: formData.agent_api_base_url
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        toast.success('Board aktualisiert');
      } else {
        await axios.post(`${API}/boards`, formData, {
          headers: { Authorization: `Bearer ${token}` }
        });
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
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Board gelöscht');
      fetchBoards();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Löschen');
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
    <div data-testid="admin-boards">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-heading uppercase tracking-wider text-white">{t('boards')}</h1>
          <p className="text-zinc-500">Dartboard-Verwaltung</p>
        </div>
        {isAdmin && (
          <Button
            onClick={openCreateDialog}
            data-testid="add-board-btn"
            className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading tracking-wider"
          >
            <Plus className="w-4 h-4 mr-2" />
            Neues Board
          </Button>
        )}
      </div>

      {/* Board List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {boards.map((board) => (
          <Card key={board.id} className="bg-zinc-900 border-zinc-800" data-testid={`board-item-${board.board_id}`}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-sm bg-zinc-800 flex items-center justify-center">
                    <Target className="w-6 h-6 text-amber-500" />
                  </div>
                  <div>
                    <CardTitle className="text-white">{board.name}</CardTitle>
                    <p className="text-sm text-zinc-500 font-mono">{board.board_id}</p>
                  </div>
                </div>
                {isAdmin && (
                  <div className="flex gap-2">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => openEditDialog(board)}
                      data-testid={`edit-board-${board.board_id}`}
                      className="text-zinc-400 hover:text-amber-500"
                    >
                      <Edit className="w-4 h-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(board)}
                      data-testid={`delete-board-${board.board_id}`}
                      className="text-zinc-400 hover:text-red-500"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {board.location && (
                <div className="flex items-center gap-2 text-sm text-zinc-400">
                  <MapPin className="w-4 h-4 text-zinc-600" />
                  {board.location}
                </div>
              )}
              <div className="flex items-center gap-2 text-sm text-zinc-500">
                <span className={`w-2 h-2 rounded-full ${
                  board.status === 'locked' ? 'bg-zinc-500' :
                  board.status === 'unlocked' ? 'bg-amber-500' :
                  board.status === 'in_game' ? 'bg-emerald-500' : 'bg-red-500'
                }`}></span>
                Status: <span className="text-zinc-300 capitalize">{board.status}</span>
              </div>
              {board.is_master && (
                <span className="inline-block px-2 py-1 bg-amber-500/20 text-amber-500 text-xs uppercase rounded-sm">
                  Master
                </span>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {boards.length === 0 && (
        <div className="text-center py-12 text-zinc-500">
          <Target className="w-16 h-16 mx-auto mb-4 text-zinc-700" />
          <p className="text-lg">Keine Boards vorhanden</p>
          <p className="text-sm">Erstellen Sie ein neues Board um zu beginnen</p>
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="font-heading uppercase tracking-wider text-white">
              {editingBoard ? 'Board bearbeiten' : 'Neues Board'}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {!editingBoard && (
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Board ID</label>
                <Input
                  value={formData.board_id}
                  onChange={(e) => setFormData({ ...formData, board_id: e.target.value })}
                  placeholder="BOARD-1"
                  data-testid="board-id-input"
                  className="input-industrial"
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider">Name</label>
              <Input
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                placeholder="Dartboard 1"
                data-testid="board-name-input"
                className="input-industrial"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider">Standort</label>
              <Input
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                placeholder="Erdgeschoss, neben der Bar"
                data-testid="board-location-input"
                className="input-industrial"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                <Link className="w-4 h-4" />
                Autodarts URL
              </label>
              <Input
                value={formData.autodarts_target_url}
                onChange={(e) => setFormData({ ...formData, autodarts_target_url: e.target.value })}
                placeholder="https://play.autodarts.io"
                data-testid="board-autodarts-input"
                className="input-industrial"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                <Link className="w-4 h-4" />
                Agent API URL (optional)
              </label>
              <Input
                value={formData.agent_api_base_url}
                onChange={(e) => setFormData({ ...formData, agent_api_base_url: e.target.value })}
                placeholder="http://192.168.1.100:8001"
                data-testid="board-agent-input"
                className="input-industrial"
              />
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setShowDialog(false)}
              className="border-zinc-700"
            >
              Abbrechen
            </Button>
            <Button
              onClick={handleSubmit}
              data-testid="save-board-btn"
              className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading"
            >
              Speichern
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
