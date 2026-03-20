import { useState } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { MapPin, Plus, Edit2, Ban, CheckCircle, AlertTriangle, X } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import axios from 'axios';

export default function OperatorLocations() {
  const { apiBase, authHeaders, canManage } = useCentralAuth();
  const { data: locations, loading, error, refetch } = useCentralData('licensing/locations');
  const { data: customers } = useCentralData('licensing/customers', { skipScope: true });
  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [form, setForm] = useState({ name: '', address: '', customer_id: '' });

  const resetForm = () => { setForm({ name: '', address: '', customer_id: '' }); setEditItem(null); setShowForm(false); };

  const handleEdit = (loc) => {
    setEditItem(loc);
    setForm({ name: loc.name, address: loc.address || '', customer_id: loc.customer_id });
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editItem) {
        await axios.put(`${apiBase}/licensing/locations/${editItem.id}`, form, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
        toast.success('Standort aktualisiert');
      } else {
        await axios.post(`${apiBase}/licensing/locations`, form, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
        toast.success('Standort erstellt');
      }
      resetForm();
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Fehler');
    }
  };

  const handleToggle = async (loc) => {
    const newStatus = loc.status === 'active' ? 'archived' : 'active';
    try {
      await axios.put(`${apiBase}/licensing/locations/${loc.id}`, { status: newStatus }, { headers: { ...authHeaders, 'Content-Type': 'application/json' } });
      toast.success(newStatus === 'active' ? 'Standort aktiviert' : 'Standort archiviert');
      refetch();
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Fehler');
    }
  };

  const customerMap = Object.fromEntries((customers || []).map(c => [c.id, c.name]));

  if (loading) return <div className="flex justify-center py-12"><div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" /></div>;
  if (error) return <div className="text-center py-12 text-red-400"><AlertTriangle className="w-8 h-8 mx-auto mb-2" /><p>{error}</p></div>;

  return (
    <div className="space-y-5" data-testid="operator-locations">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">Standorte</h1>
          <p className="text-sm text-zinc-500 mt-0.5">{locations?.length || 0} Standorte</p>
        </div>
        {canManage && (
          <Button onClick={() => { resetForm(); setShowForm(true); }} className="bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="create-location-btn">
            <Plus className="w-4 h-4 mr-1.5" /> Neuer Standort
          </Button>
        )}
      </div>

      <div className="rounded-xl border border-zinc-800 overflow-hidden">
        <table className="w-full text-sm" data-testid="locations-table">
          <thead>
            <tr className="bg-zinc-900/50 text-zinc-400 text-left">
              <th className="px-4 py-2.5 font-medium">Standort</th>
              <th className="px-4 py-2.5 font-medium">Kunde</th>
              <th className="px-4 py-2.5 font-medium">Adresse</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              {canManage && <th className="px-4 py-2.5 font-medium text-right">Aktionen</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800/50">
            {(locations || []).map(loc => (
              <tr key={loc.id} className="text-zinc-300 hover:bg-zinc-900/30">
                <td className="px-4 py-2.5 font-medium">{loc.name}</td>
                <td className="px-4 py-2.5 text-zinc-400">{customerMap[loc.customer_id] || loc.customer_id?.slice(0, 8)}</td>
                <td className="px-4 py-2.5 text-zinc-400">{loc.address || '—'}</td>
                <td className="px-4 py-2.5">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${loc.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-zinc-500/10 text-zinc-400'}`}>
                    {loc.status === 'active' ? 'Aktiv' : 'Archiviert'}
                  </span>
                </td>
                {canManage && (
                  <td className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-1.5">
                      <button onClick={() => handleEdit(loc)} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white" data-testid={`edit-location-${loc.id}`}>
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                      <button onClick={() => handleToggle(loc)} className="p-1.5 rounded-md hover:bg-zinc-800 text-zinc-400 hover:text-white" data-testid={`toggle-location-${loc.id}`}>
                        {loc.status === 'active' ? <Ban className="w-3.5 h-3.5" /> : <CheckCircle className="w-3.5 h-3.5" />}
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" data-testid="location-form-modal">
          <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 w-full max-w-md">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-base font-semibold text-white">{editItem ? 'Standort bearbeiten' : 'Neuer Standort'}</h2>
              <button onClick={resetForm} className="text-zinc-400 hover:text-white"><X className="w-5 h-5" /></button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-3">
              {!editItem && (
                <div>
                  <label className="block text-xs text-zinc-400 mb-1">Kunde</label>
                  <select value={form.customer_id} onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" required data-testid="location-form-customer">
                    <option value="">Bitte wählen</option>
                    {(customers || []).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              )}
              <div>
                <label className="block text-xs text-zinc-400 mb-1">Name</label>
                <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" required data-testid="location-form-name" />
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">Adresse</label>
                <input type="text" value={form.address} onChange={e => setForm(f => ({ ...f, address: e.target.value }))} className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white" data-testid="location-form-address" />
              </div>
              <div className="flex gap-2 pt-2">
                <Button type="submit" className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="location-form-submit">{editItem ? 'Speichern' : 'Erstellen'}</Button>
                <Button type="button" variant="outline" onClick={resetForm} className="text-sm border-zinc-700 text-zinc-400">Abbrechen</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
