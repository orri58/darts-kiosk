import { useState } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { Building2, Plus, Edit2, Ban, CheckCircle, AlertTriangle, X } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import axios from 'axios';

export default function OperatorCustomers() {
  const { apiBase, authHeaders, canManage } = useCentralAuth();
  const { data: customers, loading, error, refetch } = useCentralData('licensing/customers');
  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [form, setForm] = useState({ name: '', contact_email: '' });

  const resetForm = () => { setForm({ name: '', contact_email: '' }); setEditItem(null); setShowForm(false); };

  const handleEdit = (c) => {
    setEditItem(c);
    setForm({ name: c.name, contact_email: c.contact_email || '' });
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editItem) {
        await axios.put(`${apiBase}/licensing/customers/${editItem.id}`, form, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
        toast.success('Kunde aktualisiert');
      } else {
        await axios.post(`${apiBase}/licensing/customers`, form, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
        toast.success('Kunde erstellt');
      }
      resetForm();
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Fehler');
    }
  };

  const handleToggleStatus = async (c) => {
    const newStatus = c.status === 'active' ? 'inactive' : 'active';
    try {
      await axios.put(`${apiBase}/licensing/customers/${c.id}`, { status: newStatus }, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
      toast.success(newStatus === 'active' ? 'Kunde aktiviert' : 'Kunde deaktiviert');
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Fehler');
    }
  };

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="text-center py-12 text-red-400"><AlertTriangle className="w-8 h-8 mx-auto mb-2" /><p>{error}</p></div>;

  return (
    <div className="space-y-5" data-testid="operator-customers">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Kunden</h1>
          <p className="text-sm text-zinc-500 mt-0.5">{customers?.length || 0} Kunden</p>
        </div>
        {canManage && (
          <Button onClick={() => { resetForm(); setShowForm(true); }} className="bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="create-customer-btn">
            <Plus className="w-4 h-4 mr-1.5" /> Neuer Kunde
          </Button>
        )}
      </div>

      <div className="rounded-xl border border-zinc-800 overflow-hidden">
        <table className="w-full text-sm" data-testid="customers-table">
          <thead>
            <tr className="bg-zinc-900/50 text-zinc-400 text-left">
              <th className="px-4 py-2.5 font-medium">Kunde</th>
              <th className="px-4 py-2.5 font-medium">E-Mail</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Erstellt</th>
              {canManage && <th className="px-4 py-2.5 font-medium text-right">Aktionen</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {(customers || []).map(c => (
              <tr key={c.id} className="text-zinc-300 hover:bg-zinc-900/30">
                <td className="px-4 py-2.5 font-medium">{c.name}</td>
                <td className="px-4 py-2.5 text-zinc-400">{c.contact_email || '—'}</td>
                <td className="px-4 py-2.5">
                  <StatusBadge status={c.status} />
                </td>
                <td className="px-4 py-2.5 text-xs text-zinc-400">{c.created_at ? new Date(c.created_at).toLocaleDateString('de-DE') : '—'}</td>
                {canManage && (
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <button onClick={() => handleEdit(c)} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white" data-testid={`edit-customer-${c.id}`}>
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleToggleStatus(c)} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white" data-testid={`toggle-customer-${c.id}`}>
                        {c.status === 'active' ? <Ban className="w-3.5 h-3.5" /> : <CheckCircle className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" data-testid="customer-form-modal">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white">{editItem ? 'Kunde bearbeiten' : 'Neuer Kunde'}</h2>
              <button onClick={resetForm} className="text-zinc-400 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="block text-xs text-zinc-400 mb-1">Name</label>
                <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" required data-testid="customer-form-name" />
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">E-Mail</label>
                <input type="email" value={form.contact_email} onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" data-testid="customer-form-email" />
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="customer-form-submit">{editItem ? 'Speichern' : 'Erstellen'}</Button>
                <Button type="button" variant="outline" onClick={resetForm} className="text-sm border-zinc-700 text-zinc-400">Abbrechen</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  const conf = {
    active: 'bg-emerald-500/10 text-emerald-400',
    inactive: 'bg-zinc-500/10 text-zinc-400',
    blocked: 'bg-red-500/10 text-red-400',
  };
  const labels = { active: 'Aktiv', inactive: 'Inaktiv', blocked: 'Gesperrt' };
  return <span className={`text-xs px-2 py-0.5 rounded-full ${conf[status] || conf.inactive}`}>{labels[status] || status}</span>;
}
