import { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useCentralAuth } from '../../context/CentralAuthContext';
import axios from 'axios';
import { KeyRound, Plus, CheckCircle, AlertTriangle, Ban, Shield, Clock, Archive, Filter, ChevronRight } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';

const STATUS_CONF = {
  active: { cls: 'bg-emerald-500/10 text-emerald-400', label: 'Aktiv', icon: CheckCircle },
  grace: { cls: 'bg-amber-500/10 text-amber-400', label: 'Toleranz', icon: Clock },
  expired: { cls: 'bg-red-500/10 text-red-400', label: 'Abgelaufen', icon: AlertTriangle },
  blocked: { cls: 'bg-red-500/10 text-red-400', label: 'Gesperrt', icon: Ban },
  test: { cls: 'bg-blue-500/10 text-blue-400', label: 'Test', icon: Shield },
  deactivated: { cls: 'bg-zinc-500/10 text-zinc-400', label: 'Deaktiviert', icon: Ban },
  archived: { cls: 'bg-zinc-600/10 text-zinc-500', label: 'Archiviert', icon: Archive },
};
const STATUS_OPTIONS = [
  { value: '', label: 'Alle Status' },
  { value: 'active', label: 'Aktiv' },
  { value: 'test', label: 'Test' },
  { value: 'grace', label: 'Toleranz' },
  { value: 'expired', label: 'Abgelaufen' },
  { value: 'deactivated', label: 'Deaktiviert' },
  { value: 'archived', label: 'Archiviert' },
];

function StatusBadge({ status }) {
  const c = STATUS_CONF[status] || STATUS_CONF.active;
  const Icon = c.icon;
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs ${c.cls}`}><Icon className="w-3 h-3" />{c.label}</span>;
}

export default function OperatorLicenses() {
  const { apiBase, authHeaders, canManage } = useCentralAuth();
  const navigate = useNavigate();
  const [licenses, setLicenses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [createdLicenseId, setCreatedLicenseId] = useState(null);

  // Fetch with filter
  const fetchLicenses = useCallback(async () => {
    setLoading(true);
    try {
      const params = statusFilter ? `?status=${statusFilter}` : '';
      const res = await axios.get(`${apiBase}/licensing/licenses${params}`, { headers: authHeaders });
      setLicenses(res.data);
    } catch (err) {
      toast.error('Fehler beim Laden');
    } finally {
      setLoading(false);
    }
  }, [apiBase, authHeaders, statusFilter]);

  useEffect(() => { fetchLicenses(); }, [fetchLicenses]);

  // Create license
  const [form, setForm] = useState({ customer_id: '', location_id: '', plan_type: 'standard', max_devices: 1, status: 'active', notes: '' });
  const [customers, setCustomers] = useState([]);
  const [locations, setLocations] = useState([]);

  useEffect(() => {
    if (showCreate) {
      axios.get(`${apiBase}/licensing/customers`, { headers: authHeaders }).then(r => setCustomers(r.data)).catch(() => {});
    }
  }, [showCreate, apiBase, authHeaders]);

  useEffect(() => {
    if (form.customer_id) {
      axios.get(`${apiBase}/licensing/locations?customer_id=${form.customer_id}`, { headers: authHeaders }).then(r => setLocations(r.data)).catch(() => {});
    } else {
      setLocations([]);
    }
  }, [form.customer_id, apiBase, authHeaders]);

  const handleCreate = async () => {
    if (!form.customer_id) { toast.error('Kunde erforderlich'); return; }
    try {
      const payload = { ...form, max_devices: parseInt(form.max_devices) || 1 };
      if (!payload.location_id) delete payload.location_id;
      if (!payload.notes) delete payload.notes;
      const res = await axios.post(`${apiBase}/licensing/licenses`, payload, { headers: authHeaders });
      toast.success('Lizenz erstellt');
      setCreatedLicenseId(res.data.id);
      setShowCreate(false);
      fetchLicenses();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    }
  };

  const activeLicenses = licenses.filter(l => ['active', 'test', 'grace'].includes(l.status));
  const inactiveLicenses = licenses.filter(l => !['active', 'test', 'grace'].includes(l.status));

  return (
    <div data-testid="licenses-page" className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-zinc-100 flex items-center gap-2">
          <KeyRound className="w-5 h-5 text-zinc-500" /> Lizenzen
          <span className="text-zinc-600 text-sm ml-2">({licenses.length})</span>
        </h1>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-md px-2">
            <Filter className="w-3.5 h-3.5 text-zinc-500" />
            <select data-testid="status-filter" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
              className="bg-transparent text-zinc-300 text-sm py-1.5 outline-none cursor-pointer">
              {STATUS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          {canManage && (
            <Button data-testid="create-license-btn" onClick={() => setShowCreate(true)} size="sm" className="bg-emerald-600 hover:bg-emerald-700">
              <Plus className="w-4 h-4 mr-1.5" /> Neue Lizenz
            </Button>
          )}
        </div>
      </div>

      {/* Post-creation CTA */}
      {createdLicenseId && (
        <div data-testid="onboarding-cta" className="bg-emerald-900/20 border border-emerald-700/30 rounded-lg p-4 flex items-center justify-between">
          <div>
            <p className="text-emerald-400 font-medium text-sm">Lizenz erstellt!</p>
            <p className="text-zinc-400 text-xs mt-1">Nächster Schritt: Aktivierungstoken erstellen und Gerät verbinden.</p>
          </div>
          <Button data-testid="goto-license-detail-btn" onClick={() => navigate(`/portal/licenses/${createdLicenseId}`)} size="sm" className="bg-emerald-600 hover:bg-emerald-700">
            Gerät jetzt verbinden <ChevronRight className="w-4 h-4 ml-1" />
          </Button>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
          <div data-testid="create-license-modal" className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 w-full max-w-md space-y-4">
            <h2 className="text-zinc-100 font-medium">Neue Lizenz erstellen</h2>
            <div>
              <label className="text-zinc-400 text-sm">Kunde *</label>
              <select data-testid="create-customer" value={form.customer_id} onChange={e => setForm({ ...form, customer_id: e.target.value, location_id: '' })}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 text-sm mt-1">
                <option value="">Auswählen...</option>
                {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-zinc-400 text-sm">Standort</label>
              <select data-testid="create-location" value={form.location_id} onChange={e => setForm({ ...form, location_id: e.target.value })}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 text-sm mt-1">
                <option value="">Alle Standorte</option>
                {locations.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-zinc-400 text-sm">Plan</label>
                <select data-testid="create-plan" value={form.plan_type} onChange={e => setForm({ ...form, plan_type: e.target.value })}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 text-sm mt-1">
                  <option value="standard">Standard</option>
                  <option value="premium">Premium</option>
                  <option value="enterprise">Enterprise</option>
                  <option value="test">Test</option>
                </select>
              </div>
              <div>
                <label className="text-zinc-400 text-sm">Max. Geräte</label>
                <input data-testid="create-max-devices" type="number" min="1" value={form.max_devices}
                  onChange={e => setForm({ ...form, max_devices: e.target.value })}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 text-sm mt-1" />
              </div>
            </div>
            <div>
              <label className="text-zinc-400 text-sm">Notizen</label>
              <input data-testid="create-notes" value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
                className="w-full bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-zinc-200 text-sm mt-1" placeholder="Optional" />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="outline" size="sm" onClick={() => { setShowCreate(false); setForm({ customer_id: '', location_id: '', plan_type: 'standard', max_devices: 1, status: 'active', notes: '' }); }}
                className="border-zinc-700 text-zinc-400">Abbrechen</Button>
              <Button data-testid="create-confirm-btn" size="sm" onClick={handleCreate} className="bg-emerald-600 hover:bg-emerald-700">Erstellen</Button>
            </div>
          </div>
        </div>
      )}

      {/* License Table */}
      {loading ? (
        <div className="text-zinc-500 py-8 text-center">Laden...</div>
      ) : licenses.length === 0 ? (
        <div data-testid="licenses-empty-state" className="text-center py-16">
          <KeyRound className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
          <p className="text-zinc-400">{statusFilter ? `Keine ${STATUS_OPTIONS.find(o => o.value === statusFilter)?.label || ''} Lizenzen` : 'Noch keine Lizenzen vorhanden'}</p>
          {canManage && !statusFilter && <p className="text-zinc-600 text-sm mt-1">Erstellen Sie eine erste Lizenz, um Geräte zu verbinden.</p>}
        </div>
      ) : (
        <div className="space-y-4">
          {/* Active */}
          {activeLicenses.length > 0 && (
            <div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-zinc-800 text-zinc-500 text-xs">
                    <th className="text-left px-4 py-2">Plan</th>
                    <th className="text-left px-4 py-2">Kunde</th>
                    <th className="text-left px-4 py-2">Geräte</th>
                    <th className="text-left px-4 py-2">Status</th>
                    <th className="text-left px-4 py-2">Gültig bis</th>
                    <th className="px-4 py-2"></th>
                  </tr></thead>
                  <tbody>
                    {activeLicenses.map(lic => (
                      <tr key={lic.id} data-testid={`license-row-${lic.id}`}
                        className="border-b border-zinc-800/50 hover:bg-zinc-800/30 cursor-pointer transition-colors"
                        onClick={() => navigate(`/portal/licenses/${lic.id}`)}>
                        <td className="px-4 py-2.5 text-zinc-200 font-medium">{lic.plan_type}</td>
                        <td className="px-4 py-2.5 text-zinc-400">{lic.customer_name || lic.customer_id?.slice(0, 8)}</td>
                        <td className="px-4 py-2.5 text-zinc-400">{lic.device_count ?? 0}/{lic.max_devices}</td>
                        <td className="px-4 py-2.5"><StatusBadge status={lic.status} /></td>
                        <td className="px-4 py-2.5 text-zinc-500">{lic.ends_at ? new Date(lic.ends_at).toLocaleDateString('de-DE') : 'Unbegrenzt'}</td>
                        <td className="px-4 py-2.5"><ChevronRight className="w-4 h-4 text-zinc-600" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Inactive */}
          {inactiveLicenses.length > 0 && (
            <div>
              <p className="text-zinc-600 text-xs font-medium uppercase tracking-wider px-1 mb-2">Inaktive Lizenzen ({inactiveLicenses.length})</p>
              <div className="overflow-x-auto">
                <table className="w-full text-sm opacity-70">
                  <tbody>
                    {inactiveLicenses.map(lic => (
                      <tr key={lic.id} data-testid={`license-row-${lic.id}`}
                        className="border-b border-zinc-800/30 hover:bg-zinc-800/20 cursor-pointer transition-colors"
                        onClick={() => navigate(`/portal/licenses/${lic.id}`)}>
                        <td className="px-4 py-2 text-zinc-400">{lic.plan_type}</td>
                        <td className="px-4 py-2 text-zinc-400">{lic.customer_name || lic.customer_id?.slice(0, 8)}</td>
                        <td className="px-4 py-2 text-zinc-500">{lic.device_count ?? 0}/{lic.max_devices}</td>
                        <td className="px-4 py-2"><StatusBadge status={lic.status} /></td>
                        <td className="px-4 py-2 text-zinc-600">{lic.ends_at ? new Date(lic.ends_at).toLocaleDateString('de-DE') : '—'}</td>
                        <td className="px-4 py-2"><ChevronRight className="w-4 h-4 text-zinc-700" /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
