import { useMemo, useState } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { Users, Plus, Edit2, UserX, UserCheck, Shield, Building2, KeyRound, X } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import axios from 'axios';
import { ProductPageHeader, ProductSection, ProductStatCard, SurfaceBadge } from '../../components/shell/ProductShell';
import { ProductPageState, ProductDataTable } from '../../components/shell/ProductDataDisplay';
import { ProductDetailCard, ProductInlineActions } from '../../components/shell/ProductDetail';

const ROLE_LABELS = {
  superadmin: 'Super-Admin',
  installer: 'Aufsteller',
  owner: 'Besitzer',
  staff: 'Mitarbeiter',
};

export default function OperatorUsers() {
  const { apiBase, authHeaders, user: currentUser, canManageStaff } = useCentralAuth();
  const { data: users, loading, refetch } = useCentralData('users', { skipScope: true });
  const { data: customers } = useCentralData('scope/customers', { skipScope: true });
  const { data: roles } = useCentralData('roles', { skipScope: true });
  const [showForm, setShowForm] = useState(false);
  const [editUser, setEditUser] = useState(null);
  const [form, setForm] = useState({ username: '', password: '', display_name: '', role: 'staff', allowed_customer_ids: [] });

  const creatableRoles = roles?.can_create || [];
  const list = useMemo(() => users || [], [users]);
  const metrics = useMemo(() => ({
    total: list.length,
    active: list.filter((u) => u.status === 'active').length,
    privileged: list.filter((u) => ['superadmin', 'owner'].includes(u.role)).length,
    scoped: list.filter((u) => u.role !== 'superadmin' && (u.allowed_customer_ids?.length || 0) > 0).length,
  }), [list]);

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
    return <ProductPageState kind="loading" title="Benutzer werden geladen" description="Rollen, Scope-Zuordnung und Status werden aus dem Central Layer vorbereitet." data-testid="operator-users-loading" />;
  }

  return (
    <div className="space-y-6" data-testid="operator-users-page">
      <ProductPageHeader
        eyebrow="Operator control surface"
        title="Benutzerverwaltung"
        badge={<SurfaceBadge tone="violet">Access control</SurfaceBadge>}
        description="Rollen, Aktivstatus und Kunden-Scope jetzt in derselben Produkt-Anatomie wie die restlichen Operator-Steuerflächen."
        actions={
          canManageStaff && creatableRoles.length > 0 ? (
            <Button onClick={() => { resetForm(); setShowForm(true); }} className="bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="create-user-btn">
              <Plus className="w-4 h-4 mr-1.5" /> Neuer Benutzer
            </Button>
          ) : null
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <ProductStatCard icon={Users} label="Benutzer gesamt" value={metrics.total} hint="Sichtbar im Operator-Layer" data-testid="operator-users-total" />
        <ProductStatCard icon={UserCheck} label="Aktiv" value={metrics.active} hint="Mit aktuellem Zugriff" tone={metrics.active > 0 ? 'emerald' : 'default'} data-testid="operator-users-active" />
        <ProductStatCard icon={Shield} label="Privilegiert" value={metrics.privileged} hint="Owner / Super-Admin" tone="purple" data-testid="operator-users-privileged" />
        <ProductStatCard icon={Building2} label="Scoped" value={metrics.scoped} hint="Kunden explizit zugewiesen" tone="blue" data-testid="operator-users-scoped" />
      </div>

      <ProductSection
        eyebrow="Access roster"
        title="Benutzerliste"
        description="Direkte Steuerung für Rollenbild, Aktivstatus und Kunden-Scope."
        actions={<ProductInlineActions mode="operator" items={[{ label: 'Aktualisieren', onClick: refetch, className: 'border-zinc-700 text-zinc-300 hover:bg-zinc-800' }]} />}
      >
        <div className="p-4">
          {list.length === 0 ? (
            <ProductPageState kind="empty" compact title="Keine Benutzer sichtbar" description="Neue Benutzer erscheinen hier mit Rolle, Status und Scope-Verteilung." data-testid="operator-users-empty" />
          ) : (
            <ProductDataTable
              columns={[
                { key: 'user', label: 'Benutzer' },
                { key: 'role', label: 'Rolle' },
                { key: 'status', label: 'Status' },
                { key: 'scope', label: 'Kunden-Scope' },
                { key: 'password', label: 'Passwort' },
                { key: 'actions', label: 'Aktionen', className: 'text-right' },
              ]}
              data-testid="users-table"
            >
              {list.map((u) => (
                <tr key={u.id} className="text-zinc-300 hover:bg-zinc-900/30">
                  <td className="px-4 py-3">
                    <div>
                      <span className="font-medium text-white">{u.display_name || u.username}</span>
                      {u.display_name && <span className="ml-1.5 text-xs text-zinc-500">@{u.username}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs ${
                      u.role === 'superadmin' ? 'bg-purple-500/10 text-purple-400' :
                      u.role === 'installer' ? 'bg-blue-500/10 text-blue-400' :
                      u.role === 'owner' ? 'bg-emerald-500/10 text-emerald-400' :
                      'bg-zinc-700 text-zinc-400'
                    }`}>{ROLE_LABELS[u.role] || u.role}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs ${u.status === 'active' ? 'text-emerald-400' : 'text-red-400'}`}>
                      {u.status === 'active' ? 'Aktiv' : 'Deaktiviert'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-zinc-400">
                    {u.role === 'superadmin' ? 'Alle' : `${u.allowed_customer_ids?.length || 0} Kunden`}
                  </td>
                  <td className="px-4 py-3 text-xs text-zinc-500">
                    {u.id === currentUser?.id ? 'Eigenes Konto' : '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {u.id !== currentUser?.id && (
                      <div className="flex items-center justify-end gap-1.5">
                        <button onClick={() => handleEdit(u)} className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white" data-testid={`edit-user-${u.username}`}>
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => handleToggleStatus(u)} className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white" data-testid={`toggle-user-${u.username}`}>
                          {u.status === 'active' ? <UserX className="w-3.5 h-3.5" /> : <UserCheck className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
            </ProductDataTable>
          )}
        </div>
      </ProductSection>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" data-testid="user-form-modal">
          <ProductDetailCard title={editUser ? 'Benutzer bearbeiten' : 'Neuer Benutzer'} eyebrow="Operator action" description="Rolle, Login und Kunden-Scope ohne Sonder-UI pflegen.">
            <div className="w-full max-w-md">
              <div className="mb-4 flex items-center justify-end">
                <button onClick={resetForm} className="text-zinc-400 hover:text-white"><X className="w-5 h-5" /></button>
              </div>
              <form onSubmit={handleSubmit} className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs text-zinc-400">Benutzername</label>
                  <input
                    type="text"
                    value={form.username}
                    onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                    disabled={!!editUser}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white disabled:opacity-50"
                    required
                    data-testid="user-form-username"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-zinc-400">Anzeigename</label>
                  <input
                    type="text"
                    value={form.display_name}
                    onChange={e => setForm(f => ({ ...f, display_name: e.target.value }))}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white"
                    data-testid="user-form-displayname"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-zinc-400">{editUser ? 'Neues Passwort (leer = unverändert)' : 'Passwort'}</label>
                  <input
                    type="password"
                    value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white"
                    required={!editUser}
                    minLength={4}
                    data-testid="user-form-password"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-zinc-400">Rolle</label>
                  <select
                    value={form.role}
                    onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                    className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white"
                    data-testid="user-form-role"
                  >
                    {creatableRoles.map(r => (
                      <option key={r} value={r}>{ROLE_LABELS[r] || r}</option>
                    ))}
                  </select>
                </div>
                {form.role !== 'superadmin' && (
                  <div>
                    <label className="mb-1.5 block text-xs text-zinc-400">Kunden-Zuordnung</label>
                    <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg bg-zinc-800/50 p-2">
                      {(customers || []).map(c => (
                        <label key={c.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm text-zinc-300 hover:bg-zinc-700/30">
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
                        <p className="px-2 text-xs text-zinc-500">Keine Kunden vorhanden</p>
                      )}
                    </div>
                  </div>
                )}
                <div className="flex gap-2 pt-2">
                  <Button type="submit" className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="user-form-submit">
                    {editUser ? 'Speichern' : 'Erstellen'}
                  </Button>
                  <Button type="button" variant="outline" onClick={resetForm} className="border-zinc-700 text-sm text-zinc-400">
                    Abbrechen
                  </Button>
                </div>
              </form>
            </div>
          </ProductDetailCard>
        </div>
      )}
    </div>
  );
}
