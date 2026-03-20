import { useState } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { KeyRound, Plus, Edit2, Ban, CheckCircle, AlertTriangle, X } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import axios from 'axios';

const STATUS_CONF = {
  active: 'bg-emerald-500/10 text-emerald-400',
  grace: 'bg-amber-500/10 text-amber-400',
  expired: 'bg-red-500/10 text-red-400',
  blocked: 'bg-red-500/10 text-red-400',
  test: 'bg-blue-500/10 text-blue-400',
};
const STATUS_LABELS = { active: 'Aktiv', grace: 'Toleranz', expired: 'Abgelaufen', blocked: 'Gesperrt', test: 'Test' };

export default function OperatorLicenses() {
  const { apiBase, authHeaders, canManage } = useCentralAuth();
  const { data: licenses, loading, error, refetch } = useCentralData('licensing/licenses');
  const { data: customers } = useCentralData('licensing/customers', { skipScope: true });
  const { data: locations } = useCentralData('licensing/locations', { skipScope: true });
  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [form, setForm] = useState({ customer_id: '', location_id: '', plan_type: 'standard', max_devices: 1, starts_at: '', ends_at: '', grace_days: 7, status: 'active' });

  const resetForm = () => {
    setForm({ customer_id: '', location_id: '', plan_type: 'standard', max_devices: 1, starts_at: '', ends_at: '', grace_days: 7, status: 'active' });
    setEditItem(null);
    setShowForm(false);
  };

  const handleEdit = (lic) => {
    setEditItem(lic);
    setForm({
      customer_id: lic.customer_id, location_id: lic.location_id || '',
      plan_type: lic.plan_type, max_devices: lic.max_devices,
      starts_at: lic.starts_at?.slice(0, 10) || '', ends_at: lic.ends_at?.slice(0, 10) || '',
      grace_days: lic.grace_days || 7, status: lic.status,
    });
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const body = { ...form, max_devices: parseInt(form.max_devices), grace_days: parseInt(form.grace_days) };
      if (body.starts_at) body.starts_at = new Date(body.starts_at).toISOString();
      if (body.ends_at) body.ends_at = new Date(body.ends_at).toISOString();
      else body.ends_at = null;
      if (editItem) {
        await axios.put(`${apiBase}/licensing/licenses/${editItem.id}`, body, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
        toast.success('Lizenz aktualisiert');
      } else {
        await axios.post(`${apiBase}/licensing/licenses`, body, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
        toast.success('Lizenz erstellt');
      }
      resetForm();
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Fehler');
    }
  };

  const customerMap = Object.fromEntries((customers || []).map(c => [c.id, c.name]));
  const locationMap = Object.fromEntries((locations || []).map(l => [l.id, l.name]));

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="text-center py-12 text-red-400"><AlertTriangle className="w-8 h-8 mx-auto mb-2" /><p>{error}</p></div>;

  return (
    <div className="space-y-5" data-testid="operator-licenses">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Lizenzen</h1>
          <p className="text-sm text-zinc-500 mt-0.5">{licenses?.length || 0} Lizenzen</p>
        </div>
        {canManage && (
          <Button onClick={() => { resetForm(); setShowForm(true); }} className="bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="create-license-btn">
            <Plus className="w-4 h-4 mr-1.5" /> Neue Lizenz
          </Button>
        )}
      </div>

      <div className="rounded-xl border border-zinc-800 overflow-hidden">
        <table className="w-full text-sm" data-testid="licenses-table">
          <thead>
            <tr className="bg-zinc-900/50 text-zinc-400 text-left">
              <th className="px-4 py-2.5 font-medium">Kunde</th>
              <th className="px-4 py-2.5 font-medium">Standort</th>
              <th className="px-4 py-2.5 font-medium">Plan</th>
              <th className="px-4 py-2.5 font-medium">Geräte</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Gültig bis</th>
              {canManage && <th className="px-4 py-2.5 font-medium text-right">Aktionen</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {(licenses || []).map(lic => (
              <tr key={lic.id} className="text-zinc-300 hover:bg-zinc-900/30">
                <td className="px-4 py-2.5 font-medium">{customerMap[lic.customer_id] || lic.customer_id?.slice(0, 8)}</td>
                <td className="px-4 py-2.5 text-zinc-400">{locationMap[lic.location_id] || '—'}</td>
                <td className="px-4 py-2.5">{lic.plan_type}</td>
                <td className="px-4 py-2.5">{lic.max_devices}</td>
                <td className="px-4 py-2.5">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_CONF[lic.status] || 'bg-zinc-700 text-zinc-400'}`}>
                    {STATUS_LABELS[lic.status] || lic.status}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-zinc-400">{lic.ends_at ? new Date(lic.ends_at).toLocaleDateString('de-DE') : 'Unbegrenzt'}</td>
                {canManage && (
                  <td className="px-4 py-2.5 text-right">
                    <button onClick={() => handleEdit(lic)} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white" data-testid={`edit-license-${lic.id}`}>
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" data-testid="license-form-modal">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white">{editItem ? 'Lizenz bearbeiten' : 'Neue Lizenz'}</h2>
              <button onClick={resetForm} className="text-zinc-400 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-3">
              {!editItem && (
                <>
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1">Kunde</label>
                    <select value={form.customer_id} onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" required data-testid="license-form-customer">
                      <option value="">Bitte wählen</option>
                      {(customers || []).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs text-zinc-400 mb-1">Standort (optional)</label>
                    <select value={form.location_id} onChange={e => setForm(f => ({ ...f, location_id: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" data-testid="license-form-location">
                      <option value="">Alle Standorte</option>
                      {(locations || []).filter(l => !form.customer_id || l.customer_id === form.customer_id).map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                    </select>
                  </div>
                </>
              )}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Plan</label>
                  <select value={form.plan_type} onChange={e => setForm(f => ({ ...f, plan_type: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" data-testid="license-form-plan">
                    <option value="standard">Standard</option>
                    <option value="premium">Premium</option>
                    <option value="test">Test</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Max. Geräte</label>
                  <input type="number" min="1" value={form.max_devices} onChange={e => setForm(f => ({ ...f, max_devices: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" data-testid="license-form-maxdevices" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Start</label>
                  <input type="date" value={form.starts_at} onChange={e => setForm(f => ({ ...f, starts_at: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" data-testid="license-form-start" />
                </div>
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Ende (leer = unbegrenzt)</label>
                  <input type="date" value={form.ends_at} onChange={e => setForm(f => ({ ...f, ends_at: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" data-testid="license-form-end" />
                </div>
              </div>
              {editItem && (
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Status</label>
                  <select value={form.status} onChange={e => setForm(f => ({ ...f, status: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" data-testid="license-form-status">
                    <option value="active">Aktiv</option>
                    <option value="blocked">Gesperrt</option>
                    <option value="test">Test</option>
                  </select>
                </div>
              )}
              <div className="flex gap-2 pt-2">
                <Button type="submit" className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="license-form-submit">{editItem ? 'Speichern' : 'Erstellen'}</Button>
                <Button type="button" variant="outline" onClick={resetForm} className="text-sm border-zinc-700 text-zinc-400">Abbrechen</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
