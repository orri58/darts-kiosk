import { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Edit,
  KeyRound,
  Plus,
  RefreshCw,
  Shield,
  ShieldCheck,
  Trash2,
  UserCog,
  UserRound,
  Users,
  UserX,
} from 'lucide-react';
import { Button } from '../../components/ui/button';
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
import {
  AdminEmptyState,
  AdminPage,
  AdminSection,
  AdminStatCard,
  AdminStatsGrid,
  AdminStatusPill,
} from '../../components/admin/AdminShell';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function AdminUsers() {
  const { token, user: currentUser } = useAuth();
  const { t } = useI18n();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [formData, setFormData] = useState({
    username: '',
    password: '',
    display_name: '',
    role: 'staff',
    pin: '',
  });

  const fetchUsers = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/users`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setUsers(response.data || []);
    } catch (error) {
      console.error('Failed to fetch users:', error);
      toast.error('Benutzer konnten nicht geladen werden');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const metrics = useMemo(() => ({
    total: users.length,
    active: users.filter((user) => user.is_active).length,
    admins: users.filter((user) => user.role === 'admin').length,
    withPin: users.filter((user) => user.pin_hash || user.pin_enabled || user.pin_configured).length,
  }), [users]);

  const openCreateDialog = () => {
    setEditingUser(null);
    setFormData({
      username: '',
      password: '',
      display_name: '',
      role: 'staff',
      pin: '',
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
      pin: '',
    });
    setShowDialog(true);
  };

  const handleSubmit = async () => {
    try {
      if (editingUser) {
        await axios.put(`${API}/users/${editingUser.id}`, {
          display_name: formData.display_name || null,
          role: formData.role,
          pin: formData.pin || null,
        }, {
          headers: { Authorization: `Bearer ${token}` },
        });
        toast.success('Benutzer aktualisiert');
      } else {
        if (!formData.username || !formData.password) {
          toast.error('Benutzername und Passwort erforderlich');
          return;
        }
        await axios.post(`${API}/users`, formData, {
          headers: { Authorization: `Bearer ${token}` },
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
        headers: { Authorization: `Bearer ${token}` },
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
        is_active: !user.is_active,
      }, {
        headers: { Authorization: `Bearer ${token}` },
      });
      toast.success(user.is_active ? 'Benutzer deaktiviert' : 'Benutzer aktiviert');
      fetchUsers();
    } catch (error) {
      toast.error('Fehler beim Aktualisieren');
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <RefreshCw className="h-8 w-8 animate-spin text-amber-500" />
      </div>
    );
  }

  return (
    <AdminPage
      eyebrow="Access control"
      title={t('users')}
      description="Admin- und Staff-Zugänge ordentlich verwalten: Rollen, Aktivstatus und Quick-PINs ohne Basteloptik."
      actions={
        <div className="flex flex-wrap gap-2">
          <Button onClick={fetchUsers} variant="outline" className="border-zinc-700 text-zinc-300 hover:text-white">
            <RefreshCw className="mr-2 h-4 w-4" /> Aktualisieren
          </Button>
          <Button
            onClick={openCreateDialog}
            data-testid="add-user-btn"
            className="bg-amber-500 text-black hover:bg-amber-400"
          >
            <Plus className="mr-2 h-4 w-4" /> Neuer Benutzer
          </Button>
        </div>
      }
    >
      <AdminStatsGrid>
        <AdminStatCard icon={Users} label="Benutzer gesamt" value={metrics.total} hint="Alle lokalen Accounts" tone="amber" />
        <AdminStatCard icon={UserRound} label="Aktiv" value={metrics.active} hint="Derzeit nutzbare Zugänge" tone="emerald" />
        <AdminStatCard icon={ShieldCheck} label="Admins" value={metrics.admins} hint="Mit erweiterten Rechten" tone="blue" />
        <AdminStatCard icon={KeyRound} label="PIN-Fähig" value={metrics.withPin} hint="Accounts mit Quick-Login" tone="violet" />
      </AdminStatsGrid>

      <AdminSection
        title="Benutzerverzeichnis"
        description="Operatoren sehen sofort Rolle, Status und Bearbeitungsoptionen. Kritische Selbst-Aktionen bleiben bewusst blockiert."
        actions={<AdminStatusPill tone="amber">{currentUser?.username || 'Session'}</AdminStatusPill>}
      >
        {users.length === 0 ? (
          <AdminEmptyState
            icon={UserX}
            title="Noch keine Benutzer angelegt"
            description="Lege mindestens einen Staff- oder Admin-Account an, damit die Bedienoberfläche nicht an einem Einzelkonto hängt."
            action={
              <Button onClick={openCreateDialog} className="bg-amber-500 text-black hover:bg-amber-400">
                <Plus className="mr-2 h-4 w-4" /> Ersten Benutzer anlegen
              </Button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {users.map((user) => {
              const isCurrentUser = user.id === currentUser?.id;
              const isAdmin = user.role === 'admin';
              const hasPin = Boolean(user.pin_hash || user.pin_enabled || user.pin_configured);

              return (
                <div
                  key={user.id}
                  className={`overflow-hidden rounded-[1.7rem] border shadow-[0_16px_48px_rgba(0,0,0,0.22)] ${
                    user.is_active
                      ? 'border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.68)]'
                      : 'border-[rgb(var(--color-border-rgb)/0.72)] bg-[rgb(var(--color-bg-rgb)/0.42)] opacity-75'
                  }`}
                  data-testid={`user-item-${user.username}`}
                >
                  <div className="border-b border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-bg-rgb)/0.26)] px-5 py-4">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                      <div className="flex min-w-0 items-start gap-4">
                        <div className={`flex h-14 w-14 items-center justify-center rounded-3xl border ${isAdmin ? 'border-amber-500/30 bg-amber-500/12 text-amber-400' : 'border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-bg-rgb)/0.58)] text-[var(--color-text-secondary)]'}`}>
                          {isAdmin ? <ShieldCheck className="h-6 w-6" /> : <Shield className="h-6 w-6" />}
                        </div>
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="truncate text-lg font-semibold text-[var(--color-text)]">
                              {user.display_name || user.username}
                            </p>
                            {isCurrentUser && <AdminStatusPill tone="blue">Aktuelle Session</AdminStatusPill>}
                          </div>
                          <p className="mt-1 truncate font-mono text-sm text-[var(--color-text-secondary)]">@{user.username}</p>
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <AdminStatusPill tone={isAdmin ? 'amber' : 'neutral'}>
                          {isAdmin ? 'Admin' : 'Staff'}
                        </AdminStatusPill>
                        <AdminStatusPill tone={user.is_active ? 'emerald' : 'red'}>
                          {user.is_active ? 'Aktiv' : 'Inaktiv'}
                        </AdminStatusPill>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-4 px-5 py-5">
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.76)] bg-[rgb(var(--color-bg-rgb)/0.34)] px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">Rolle</p>
                        <p className="mt-2 text-sm font-medium text-[var(--color-text)]">{isAdmin ? 'Systemzugriff erweitert' : 'Operator / Tresen'}</p>
                      </div>
                      <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.76)] bg-[rgb(var(--color-bg-rgb)/0.34)] px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">Quick-PIN</p>
                        <p className="mt-2 text-sm font-medium text-[var(--color-text)]">{hasPin ? 'Konfiguriert' : 'Nicht gesetzt'}</p>
                      </div>
                      <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.76)] bg-[rgb(var(--color-bg-rgb)/0.34)] px-4 py-3">
                        <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">Sicherheit</p>
                        <p className="mt-2 text-sm font-medium text-[var(--color-text)]">{isCurrentUser ? 'Selbstschutz aktiv' : 'Verwaltbar'}</p>
                      </div>
                    </div>

                    <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                      <div className="text-sm text-[var(--color-text-secondary)]">
                        {isCurrentUser
                          ? 'Eigenes Konto bleibt vor Selbst-Deaktivierung und Selbst-Löschung geschützt.'
                          : 'Statuswechsel und Rollenpflege direkt von hier.'}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => toggleUserActive(user)}
                          disabled={isCurrentUser}
                          className="border-[rgb(var(--color-border-rgb)/0.8)] text-[var(--color-text-secondary)] hover:border-[rgb(var(--color-primary-rgb)/0.28)] hover:text-[var(--color-text)]"
                        >
                          {user.is_active ? 'Deaktivieren' : 'Aktivieren'}
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => openEditDialog(user)}
                          data-testid={`edit-user-${user.username}`}
                          className="border-[rgb(var(--color-border-rgb)/0.8)] text-[var(--color-text-secondary)] hover:border-[rgb(var(--color-primary-rgb)/0.28)] hover:text-[var(--color-primary)]"
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={() => handleDelete(user)}
                          disabled={isCurrentUser}
                          data-testid={`delete-user-${user.username}`}
                          className="border-[rgb(var(--color-border-rgb)/0.8)] text-[var(--color-text-secondary)] hover:border-[rgb(var(--color-accent-rgb)/0.28)] hover:text-[var(--color-accent)]"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </AdminSection>

      <AdminSection title="Rollenlogik" description="Kurz erklärt, damit die Oberfläche auch für gelegentliche Operatoren selbsterklärend bleibt.">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-4 text-sm text-[var(--color-text-secondary)]">
            <p className="font-medium text-[var(--color-text)]">Staff</p>
            <p className="mt-2 leading-6">Für Tresen und Tagesbetrieb. Schnell, praktisch, ohne unnötig tiefe Systemrechte.</p>
          </div>
          <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-4 text-sm text-[var(--color-text-secondary)]">
            <p className="font-medium text-[var(--color-text)]">Admin</p>
            <p className="mt-2 leading-6">Für Konfiguration, Wartung und kritische Betriebsentscheidungen.</p>
          </div>
          <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.78)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-4 text-sm text-[var(--color-text-secondary)]">
            <p className="font-medium text-[var(--color-text)]">Quick-PIN</p>
            <p className="mt-2 leading-6">Optional für schnelle Logins am Gerät. Kein Muss, aber praktisch im Schichtbetrieb.</p>
          </div>
        </div>
      </AdminSection>

      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="overflow-hidden border-[rgb(var(--color-border-rgb)/0.88)] bg-[rgb(var(--color-bg-rgb)/0.98)] p-0 text-[var(--color-text)] sm:max-w-xl">
          <DialogHeader>
            <div className="border-b border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] px-6 py-5">
              <DialogTitle className="flex items-center gap-2 font-heading uppercase tracking-[0.12em] text-[var(--color-text)]">
                <UserCog className="h-5 w-5 text-[var(--color-primary)]" />
                {editingUser ? 'Benutzer bearbeiten' : 'Neuer Benutzer'}
              </DialogTitle>
              <p className="mt-2 text-sm text-[var(--color-text-secondary)]">
                Rollen, Anzeigename und Quick-PIN bleiben an einem Ort. Beim Anlegen sind Benutzername und Passwort Pflicht.
              </p>
            </div>
          </DialogHeader>

          <div className="space-y-5 px-6 py-5">
            {!editingUser && (
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <label className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">Benutzername</label>
                  <Input
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    placeholder="max.mustermann"
                    data-testid="user-username-input"
                    className="h-12 rounded-2xl border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.52)] text-[var(--color-text)]"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">Passwort</label>
                  <Input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder="••••••••"
                    data-testid="user-password-input"
                    className="h-12 rounded-2xl border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.52)] text-[var(--color-text)]"
                  />
                </div>
              </div>
            )}

            <div className="space-y-2">
              <label className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">Anzeigename</label>
              <Input
                value={formData.display_name}
                onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                placeholder="Max Mustermann"
                data-testid="user-displayname-input"
                className="h-12 rounded-2xl border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.52)] text-[var(--color-text)]"
              />
            </div>

            <div className="space-y-3">
              <label className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">Rolle</label>
              <div className="grid gap-3 sm:grid-cols-2">
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, role: 'staff' })}
                  className={`rounded-3xl border p-4 text-left transition ${
                    formData.role === 'staff'
                      ? 'border-[rgb(var(--color-primary-rgb)/0.3)] bg-[rgb(var(--color-primary-rgb)/0.12)] text-[var(--color-text)]'
                      : 'border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.5)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                  }`}
                >
                  <Shield className="mb-3 h-5 w-5" />
                  <p className="font-medium">Staff / Wirt</p>
                  <p className="mt-1 text-sm opacity-80">Für Alltag, Freischalten und Bedienung.</p>
                </button>
                <button
                  type="button"
                  onClick={() => setFormData({ ...formData, role: 'admin' })}
                  className={`rounded-3xl border p-4 text-left transition ${
                    formData.role === 'admin'
                      ? 'border-[rgb(var(--color-primary-rgb)/0.3)] bg-[rgb(var(--color-primary-rgb)/0.12)] text-[var(--color-text)]'
                      : 'border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.5)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]'
                  }`}
                >
                  <ShieldCheck className="mb-3 h-5 w-5" />
                  <p className="font-medium">Admin</p>
                  <p className="mt-1 text-sm opacity-80">Für Konfiguration, Wartung und Systemflächen.</p>
                </button>
              </div>
            </div>

            <div className="rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.54)] p-4">
              <label className="flex items-center gap-2 text-[11px] uppercase tracking-[0.24em] text-[var(--color-text-muted)]">
                <KeyRound className="h-4 w-4" /> Quick-PIN (4 Ziffern)
              </label>
              <Input
                type="text"
                maxLength={4}
                value={formData.pin}
                onChange={(e) => setFormData({ ...formData, pin: e.target.value.replace(/\D/g, '') })}
                placeholder="1234"
                data-testid="user-pin-input"
                className="mt-3 h-12 rounded-2xl border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.52)] font-mono tracking-[0.35em] text-[var(--color-text)]"
              />
              <p className="mt-2 text-xs text-[var(--color-text-secondary)]">Optional. Praktisch für schnelle Logins im Schichtbetrieb.</p>
            </div>
          </div>

          <DialogFooter className="gap-2 border-t border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.42)] px-6 py-4">
            <Button variant="outline" onClick={() => setShowDialog(false)} className="rounded-2xl border-[rgb(var(--color-border-rgb)/0.82)] text-[var(--color-text-secondary)]">
              Abbrechen
            </Button>
            <Button onClick={handleSubmit} data-testid="save-user-btn" className="rounded-2xl bg-[var(--color-primary)] text-[hsl(var(--primary-foreground))] hover:opacity-90">
              Speichern
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AdminPage>
  );
}
