import { useMemo, useState } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { MapPin, Plus, Edit2, Ban, CheckCircle, Building2, Archive } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import axios from 'axios';
import { ProductPageHeader, ProductSection, ProductStatCard, SurfaceBadge } from '../../components/shell/ProductShell';
import { ProductPageState, ProductDataTable } from '../../components/shell/ProductDataDisplay';
import { ProductDetailCard, ProductInlineActions } from '../../components/shell/ProductDetail';

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
  const list = useMemo(() => locations || [], [locations]);
  const metrics = useMemo(() => ({
    total: list.length,
    active: list.filter((loc) => loc.status === 'active').length,
    archived: list.filter((loc) => loc.status !== 'active').length,
    linkedCustomers: new Set(list.map((loc) => loc.customer_id).filter(Boolean)).size,
  }), [list]);

  if (loading) return <ProductPageState kind="loading" title="Standorte werden geladen" description="Scope, Kundenbezug und Betriebsstatus werden vorbereitet." data-testid="operator-locations-loading" />;
  if (error) return <ProductPageState kind="error" title="Standorte konnten nicht geladen werden" description={error} data-testid="operator-locations-error" />;

  return (
    <div className="space-y-6" data-testid="operator-locations">
      <ProductPageHeader
        eyebrow="Operator control surface"
        title="Standorte"
        badge={<SurfaceBadge tone="emerald">Deployment scope</SurfaceBadge>}
        description="Standortführung im selben UI-System wie Fleet und Commercial-Flows — mit sauberem Scope-Bezug statt alter Tabelleninsel."
        actions={
          canManage ? (
            <Button onClick={() => { resetForm(); setShowForm(true); }} className="bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="create-location-btn">
              <Plus className="w-4 h-4 mr-1.5" /> Neuer Standort
            </Button>
          ) : null
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <ProductStatCard icon={MapPin} label="Standorte gesamt" value={metrics.total} hint="Im aktuellen Operator-Scope" data-testid="operator-locations-total" />
        <ProductStatCard icon={CheckCircle} label="Aktiv" value={metrics.active} hint="Aktiv im Portfolio" tone={metrics.active > 0 ? 'emerald' : 'default'} data-testid="operator-locations-active" />
        <ProductStatCard icon={Archive} label="Archiviert" value={metrics.archived} hint="Nicht aktiv im Betrieb" tone={metrics.archived > 0 ? 'amber' : 'default'} data-testid="operator-locations-archived" />
        <ProductStatCard icon={Building2} label="Kunden verknüpft" value={metrics.linkedCustomers} hint="Distinct Customer Scope" tone="blue" data-testid="operator-locations-customers" />
      </div>

      <ProductSection
        eyebrow="Deployment map"
        title="Standortliste"
        description="Kunde, Adresse und Status in einer gemeinsamen Operator-Tabelle."
        actions={<ProductInlineActions mode="operator" items={[{ label: 'Aktualisieren', onClick: refetch, className: 'border-zinc-700 text-zinc-300 hover:bg-zinc-800' }]} />}
      >
        <div className="p-4">
          {list.length === 0 ? (
            <ProductPageState kind="empty" compact title="Keine Standorte im Scope" description="Sobald Standorte angelegt oder sichtbar sind, landen sie hier mit Kundenbezug und Status." data-testid="operator-locations-empty" />
          ) : (
            <ProductDataTable
              columns={[
                { key: 'location', label: 'Standort' },
                { key: 'customer', label: 'Kunde' },
                { key: 'address', label: 'Adresse' },
                { key: 'status', label: 'Status' },
                ...(canManage ? [{ key: 'actions', label: 'Aktionen', className: 'text-right' }] : []),
              ]}
              data-testid="locations-table"
            >
              {list.map((loc) => (
                <tr key={loc.id} className="text-zinc-300 hover:bg-zinc-900/30">
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-medium text-white">{loc.name}</p>
                      <p className="mt-1 font-mono text-[11px] text-zinc-500">{loc.id}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-zinc-400">{customerMap[loc.customer_id] || loc.customer_id?.slice(0, 8) || '—'}</td>
                  <td className="px-4 py-3 text-zinc-400">{loc.address || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${loc.status === 'active' ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400' : 'border-zinc-500/20 bg-zinc-500/10 text-zinc-400'}`}>
                      {loc.status === 'active' ? 'Aktiv' : 'Archiviert'}
                    </span>
                  </td>
                  {canManage ? (
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button onClick={() => handleEdit(loc)} className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white" data-testid={`edit-location-${loc.id}`}>
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => handleToggle(loc)} className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white" data-testid={`toggle-location-${loc.id}`}>
                          {loc.status === 'active' ? <Ban className="w-3.5 h-3.5" /> : <CheckCircle className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                    </td>
                  ) : null}
                </tr>
              ))}
            </ProductDataTable>
          )}
        </div>
      </ProductSection>

      {showForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" data-testid="location-form-modal">
          <ProductDetailCard title={editItem ? 'Standort bearbeiten' : 'Neuer Standort'} eyebrow="Operator action" description="Scope, Kunde und Stammdaten ohne UI-Sonderweg pflegen.">
            <div className="w-full max-w-md">
              <div className="mb-4 flex items-center justify-end">
                <button onClick={resetForm} className="text-zinc-400 hover:text-white"><span className="sr-only">Schließen</span>×</button>
              </div>
              <form onSubmit={handleSubmit} className="space-y-3">
                {!editItem && (
                  <div>
                    <label className="mb-1 block text-xs text-zinc-400">Kunde</label>
                    <select value={form.customer_id} onChange={e => setForm(f => ({ ...f, customer_id: e.target.value }))} className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white" required data-testid="location-form-customer">
                      <option value="">Bitte wählen</option>
                      {(customers || []).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                  </div>
                )}
                <div>
                  <label className="mb-1 block text-xs text-zinc-400">Name</label>
                  <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white" required data-testid="location-form-name" />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-zinc-400">Adresse</label>
                  <input type="text" value={form.address} onChange={e => setForm(f => ({ ...f, address: e.target.value }))} className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white" data-testid="location-form-address" />
                </div>
                <div className="flex gap-2 pt-2">
                  <Button type="submit" className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="location-form-submit">{editItem ? 'Speichern' : 'Erstellen'}</Button>
                  <Button type="button" variant="outline" onClick={resetForm} className="border-zinc-700 text-sm text-zinc-400">Abbrechen</Button>
                </div>
              </form>
            </div>
          </ProductDetailCard>
        </div>
      )}
    </div>
  );
}
