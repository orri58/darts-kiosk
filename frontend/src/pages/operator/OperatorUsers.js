import { useState, useEffect } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { Users, Plus, Edit2, UserX, UserCheck, X } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import axios from 'axios';

const ROLE_LABELS = {
  superadmin: 'Super-Admin',
  installer: 'Aufsteller',
  owner: 'Besitzer',
  staff: 'Mitarbeiter',
};

export default function OperatorUsers() {
  const { apiBase, authHeaders, user: currentUser, isSuperadmin, canManageStaff } = useCentralAuth();
  const { data: users, loading, refetch } = useCentralData('users', { skipScope: true });
  const { data: customers } = useCentralData('scope/customers', { skipScope: true });
  const { data: roles } = useCentralData('roles', { skipScope: true });
  const [showForm, setShowForm] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [form, setForm] = useState({ username: '', password: '', display_name: '', role: 'staff', allowed_customer_ids: [] });

  const creatableRoles = roles?.can_create || [];

  const resetForm = () => {
    setForm({ username: '', password: '', display_name: '', role: 'staff', allowed_customer_ids: [] });
    setEditUser(null);
    setShowForm(false);
  };

  const handleEdit = (u) => {
    setEditUser(u);
    setForm({
      username: u.username,
      password: '',
      display_name: u.display_name || '',
      role: u.role,
      allowed_customer_ids: u.allowed_customer_ids || [],
    });
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editUser) {
        const body = { ...form };
        if (!body.password) delete body.password;
        await axios.put(`${apiBase}/users/${editUser.id}`, body, { headers: authHeaders });
        toast.success('Benutzer aktualisiert');
      } else {
        await axios.post(`${apiBase}/users`, form, { headers: authHeaders });
        toast.success('Benutzer erstellt');
      }
      resetForm();
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Fehler');
    }
  };

  const handleToggleStatus = async (u) => {
    const newStatus = u.status === 'active' ? 'disabled' : 'active';
    try {
      await axios.put(`${apiBase}/users/${u.id}`, { status: newStatus }, { headers: authHeaders });
      toast.success(newStatus === 'active' ? 'Benutzer aktiviert' : 'Benutzer deaktiviert');
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Fehler');
    }
  };

  const toggleCustomer = (cid) => {
    setForm(prev => ({
      ...prev,
      allowed_customer_ids: prev.allowed_customer_ids.includes(cid)
        ? prev.allowed_customer_ids.filter(id => id !== cid)
        : [...prev.allowed_customer_ids, cid],
    }));
  };

  if (loading) {
    return <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" /></div>;
  }

  return (
    <div className="space-y-5" data-testid="operator-users-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Benutzerverwaltung</h1>
          <p className="text-sm text-zinc-500 mt-0.5">{users?.length || 0} Benutzer</p>
        </div>
        {canManageStaff && creatableRoles.length > 0 && (
          <Button onClick={() => { resetForm(); setShowForm(true); }} className="bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="create-user-btn">
            <Plus className="w-4 h-4 mr-1.5" /> Neuer Benutzer
          </Button>
        )}
      </div>

      {/* User Table */}
      <div className="rounded-xl border border-zinc-800 overflow-hidden">
        <table className="w-full text-sm" data-testid="users-table">
          <thead>
            <tr className="bg-zinc-900/50 text-zinc-400 text-left">
              <th className="px-4 py-2.5 font-medium">Benutzer</th>
              <th className="px-4 py-2.5 font-medium">Rolle</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Kunden-Scope</th>
              <th className="px-4 py-2.5 font-medium text-right">Aktionen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {(users || []).map(u => (
              <tr key={u.id} className="text-zinc-300 hover:bg-zinc-900/30">
                <td className="px-4 py-2.5">
                  <div>
                    <span className="font-medium">{u.display_name || u.username}</span>
                    {u.display_name && <span className="text-xs text-zinc-500 ml-1.5">@{u.username}</span>}
                  </div>
                </td>
                <td className="px-4 py-2.5">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    u.role === 'superadmin' ? 'bg-purple-500/10 text-purple-400' :
                    u.role === 'installer' ? 'bg-blue-500/10 text-blue-400' :
                    u.role === 'owner' ? 'bg-emerald-500/10 text-emerald-400' :
                    'bg-zinc-700 text-zinc-400'
                  }`}>{ROLE_LABELS[u.role] || u.role}</span>
                </td>
                <td className="px-4 py-2.5">
                  <span className={`text-xs ${u.status === 'active' ? 'text-emerald-400' : 'text-red-400'}`}>
                    {u.status === 'active' ? 'Aktiv' : 'Deaktiviert'}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-zinc-400">
                  {u.role === 'superadmin' ? 'Alle' : (u.allowed_customer_ids?.length || 0) + ' Kunden'}
                </td>
                <td className="px-4 py-2.5 text-right">
                  {u.id !== currentUser?.id && (
                    <div className="flex items-center justify-end gap-1.5">
                      <button onClick={() => handleEdit(u)} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors" data-testid={`edit-user-${u.username}`}>
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleToggleStatus(u)} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white transition-colors" data-testid={`toggle-user-${u.username}`}>
                        {u.status === 'active' ? <UserX className="w-3.5 h-3.5" /> : <UserCheck className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Create/Edit Form Modal */}
      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" data-testid="user-form-modal">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white">{editUser ? 'Benutzer bearbeiten' : 'Neuer Benutzer'}</h2>
              <button onClick={resetForm} className="text-zinc-400 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="block text-xs text-zinc-400 mb-1">Benutzername</label>
                <input
                  type="text"
                  value={form.username}
                  onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                  disabled={!!editUser}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white disabled:opacity-50"
                  required
                  data-testid="user-form-username"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">Anzeigename</label>
                <input
                  type="text"
                  value={form.display_name}
                  onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white"
                  data-testid="user-form-displayname"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">{editUser ? 'Neues Passwort (leer = unverändert)' : 'Passwort'}</label>
                <input
                  type="password"
                  value={form.password}
                  onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white"
                  required={!editUser}
                  minLength={4}
                  data-testid="user-form-password"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">Rolle</label>
                <select
                  value={form.role}
                  onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white"
                  data-testid="user-form-role"
                >
                  {creatableRoles.map(r => (
                    <option key={r} value={r}>{ROLE_LABELS[r] || r}</option>
                  ))}
                </select>
              </div>
              {form.role !== 'superadmin' && (
                <div>
                  <label className="block text-xs text-zinc-400 mb-1.5">Kunden-Zuordnung</label>
                  <div className="space-y-1 max-h-32 overflow-y-auto bg-zinc-800/50 rounded-lg p-2">
                    {(customers || []).map(c => (
                      <label key={c.id} className="flex items-center gap-2 text-sm text-zinc-300 cursor-pointer hover:bg-zinc-700/30 px-2 py-1 rounded">
                        <input
                          type="checkbox"
                          checked={form.allowed_customer_ids.includes(c.id)}
                          onChange={() => toggleCustomer(c.id)}
                          className="rounded border-zinc-600"
                        />
                        {c.name}
                      </label>
                    ))}
                    {(!customers || customers.length === 0) && (
                      <p className="text-xs text-zinc-500 px-2">Keine Kunden vorhanden</p>
                    )}
                  </div>
                </div>
              )}
              <div className="flex gap-2 pt-2">
                <Button type="submit" className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="user-form-submit">
                  {editUser ? 'Speichern' : 'Erstellen'}
                </Button>
                <Button type="button" variant="outline" onClick={resetForm} className="text-sm border-zinc-700 text-zinc-400">
                  Abbrechen
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
