import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Users, Plus, Edit, Trash2, RefreshCw, KeyRound, Shield, ShieldCheck } from 'lucide-react';
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

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminUsers() {
  const { token, user: currentUser } = useAuth();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    display_name: '',
    role: 'staff',
    pin: ''
  });

  const fetchUsers = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/users`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setUsers(response.data);
    } catch (error) {
      console.error('Failed to fetch users:', error);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const openCreateDialog = () => {
    setEditingUser(null);
    setFormData({
      username: '',
      password: '',
      display_name: '',
      role: 'staff',
      pin: ''
    });
    setShowDialog(true);
  };

  const openEditDialog = (user) => {
    setEditingUser(user);
    setFormData({
      username: user.username,
      password: '',
      display_name: user.display_name || '',
      role: user.role,
      pin: ''
    });
    setShowDialog(true);
  };

  const handleSubmit = async () => {
    try {
      if (editingUser) {
        await axios.put(`${API}/users/${editingUser.id}`, {
          display_name: formData.display_name || null,
          role: formData.role,
          pin: formData.pin || null
        }, {
          headers: { Authorization: `Bearer ${token}` }
        });
        toast.success('Benutzer aktualisiert');
      } else {
        if (!formData.username || !formData.password) {
          toast.error('Benutzername und Passwort erforderlich');
          return;
        }
        await axios.post(`${API}/users`, formData, {
          headers: { Authorization: `Bearer ${token}` }
        });
        toast.success('Benutzer erstellt');
      }
      setShowDialog(false);
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Speichern');
    }
  };

  const handleDelete = async (user) => {
    if (user.id === currentUser?.id) {
      toast.error('Sie können sich nicht selbst löschen');
      return;
    }
    if (!window.confirm(`Benutzer "${user.username}" wirklich löschen?`)) return;
    
    try {
      await axios.delete(`${API}/users/${user.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success('Benutzer gelöscht');
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Fehler beim Löschen');
    }
  };

  const toggleUserActive = async (user) => {
    if (user.id === currentUser?.id) {
      toast.error('Sie können sich nicht selbst deaktivieren');
      return;
    }
    
    try {
      await axios.put(`${API}/users/${user.id}`, {
        is_active: !user.is_active
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      toast.success(user.is_active ? 'Benutzer deaktiviert' : 'Benutzer aktiviert');
      fetchUsers();
    } catch (error) {
      toast.error('Fehler beim Aktualisieren');
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
    <div data-testid="admin-users">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-heading uppercase tracking-wider text-white">Benutzer</h1>
          <p className="text-zinc-500">Admin- und Staff-Verwaltung</p>
        </div>
        <Button
          onClick={openCreateDialog}
          data-testid="add-user-btn"
          className="bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading tracking-wider"
        >
          <Plus className="w-4 h-4 mr-2" />
          Neuer Benutzer
        </Button>
      </div>

      {/* User List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {users.map((user) => (
          <Card key={user.id} className={`bg-zinc-900 border-zinc-800 ${!user.is_active ? 'opacity-50' : ''}`} data-testid={`user-item-${user.username}`}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-12 h-12 rounded-full flex items-center justify-center ${
                    user.role === 'admin' ? 'bg-amber-500/20' : 'bg-zinc-800'
                  }`}>
                    {user.role === 'admin' ? (
                      <ShieldCheck className="w-6 h-6 text-amber-500" />
                    ) : (
                      <Shield className="w-6 h-6 text-zinc-500" />
                    )}
                  </div>
                  <div>
                    <CardTitle className="text-white">{user.display_name || user.username}</CardTitle>
                    <p className="text-sm text-zinc-500">@{user.username}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-3 py-1 text-xs uppercase rounded-sm ${
                    user.role === 'admin' 
                      ? 'bg-amber-500/20 text-amber-500 border border-amber-500/30' 
                      : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
                  }`}>
                    {user.role === 'admin' ? 'Admin' : 'Staff'}
                  </span>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="text-sm text-zinc-500">
                  {user.is_active ? (
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                      Aktiv
                    </span>
                  ) : (
                    <span className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full bg-red-500"></span>
                      Inaktiv
                    </span>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => toggleUserActive(user)}
                    disabled={user.id === currentUser?.id}
                    className="text-zinc-400 hover:text-amber-500"
                  >
                    {user.is_active ? 'Deaktivieren' : 'Aktivieren'}
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => openEditDialog(user)}
                    data-testid={`edit-user-${user.username}`}
                    className="text-zinc-400 hover:text-amber-500"
                  >
                    <Edit className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => handleDelete(user)}
                    disabled={user.id === currentUser?.id}
                    data-testid={`delete-user-${user.username}`}
                    className="text-zinc-400 hover:text-red-500"
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="bg-zinc-900 border-zinc-800">
          <DialogHeader>
            <DialogTitle className="font-heading uppercase tracking-wider text-white">
              {editingUser ? 'Benutzer bearbeiten' : 'Neuer Benutzer'}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {!editingUser && (
              <>
                <div className="space-y-2">
                  <label className="text-sm text-zinc-500 uppercase tracking-wider">Benutzername</label>
                  <Input
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    placeholder="max.mustermann"
                    data-testid="user-username-input"
                    className="input-industrial"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm text-zinc-500 uppercase tracking-wider">Passwort</label>
                  <Input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="••••••••"
                    data-testid="user-password-input"
                    className="input-industrial"
                  />
                </div>
              </>
            )}

            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider">Anzeigename</label>
              <Input
                value={formData.display_name}
                onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                placeholder="Max Mustermann"
                data-testid="user-displayname-input"
                className="input-industrial"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider">Rolle</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  onClick={() => setFormData({ ...formData, role: 'staff' })}
                  className={`p-3 rounded-sm border-2 transition-all ${
                    formData.role === 'staff'
                      ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                      : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                  }`}
                >
                  <Shield className="w-5 h-5 mx-auto mb-1" />
                  <span className="text-xs uppercase">Staff / Wirt</span>
                </button>
                <button
                  onClick={() => setFormData({ ...formData, role: 'admin' })}
                  className={`p-3 rounded-sm border-2 transition-all ${
                    formData.role === 'admin'
                      ? 'border-amber-500 bg-amber-500/20 text-amber-500'
                      : 'border-zinc-700 text-zinc-400 hover:border-zinc-600'
                  }`}
                >
                  <ShieldCheck className="w-5 h-5 mx-auto mb-1" />
                  <span className="text-xs uppercase">Admin</span>
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-zinc-500 uppercase tracking-wider flex items-center gap-2">
                <KeyRound className="w-4 h-4" />
                Quick-PIN (4 Ziffern)
              </label>
              <Input
                type="text"
                maxLength={4}
                value={formData.pin}
                onChange={(e) => setFormData({ ...formData, pin: e.target.value.replace(/\D/g, '') })}
                placeholder="1234"
                data-testid="user-pin-input"
                className="input-industrial font-mono tracking-widest"
              />
              <p className="text-xs text-zinc-600">Optional. Ermöglicht schnelles Einloggen mit PIN.</p>
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
              data-testid="save-user-btn"
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
