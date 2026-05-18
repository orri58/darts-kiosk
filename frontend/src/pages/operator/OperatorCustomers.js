import { useMemo, useState } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { Building2, Plus, Edit2, Ban, CheckCircle, AlertTriangle, X, Mail, Activity } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import axios from 'axios';
import { ProductPageHeader, ProductSection, ProductStatCard, SurfaceBadge } from '../../components/shell/ProductShell';
import { ProductPageState, ProductDataTable } from '../../components/shell/ProductDataDisplay';
import { ProductDetailCard, ProductInlineActions } from '../../components/shell/ProductDetail';

export default function OperatorCustomers() {
  const { apiBase, authHeaders, canManage } = useCentralAuth();
  const { data: customers, loading, error, refetch } = useCentralData('licensing/customers');
  const [showForm, setShowForm] = useState(false);
  const [editItem, setEditItem] = useState(null);
  const [form, setForm] = useState({ name: '', contact_email: '' });

  const list = useMemo(() => customers || [], [customers]);
  const metrics = useMemo(() => ({
    total: list.length,
    active: list.filter((item) => item.status === 'active').length,
    inactive: list.filter((item) => item.status === 'inactive').length,
    withEmail: list.filter((item) => Boolean(item.contact_email)).length,
  }), [list]);

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

  if (loading) return <ProductPageState kind="loading" title="Kunden werden geladen" description="Verträge, Zustände und Kontaktbasis werden aus dem Central Scope gelesen." data-testid="operator-customers-loading" />;
  if (error) return <ProductPageState kind="error" title="Kunden konnten nicht geladen werden" description={error} data-testid="operator-customers-error" />;

  return (
    <div className="space-y-6" data-testid="operator-customers">
      <ProductPageHeader
        eyebrow="Operator control surface"
        title="Kunden"
        badge={<SurfaceBadge tone="blue">Portfolio</SurfaceBadge>}
        description="Kundenstamm in derselben Produkt-Systematik wie Geräte, Lizenzen und Remote Actions — weniger CRUD-Wand, mehr steuerbare Übersicht."
        actions={
          canManage ? (
            <Button onClick={() => { resetForm(); setShowForm(true); }} className="bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="create-customer-btn">
              <Plus className="w-4 h-4 mr-1.5" /> Neuer Kunde
            </Button>
          ) : null
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <ProductStatCard icon={Building2} label="Kunden gesamt" value={metrics.total} hint="Im aktuellen Scope sichtbar" data-testid="operator-customers-total" />
        <ProductStatCard icon={Activity} label="Aktiv" value={metrics.active} hint="Produktiv nutzbar" tone={metrics.active > 0 ? 'emerald' : 'default'} data-testid="operator-customers-active" />
        <ProductStatCard icon={AlertTriangle} label="Inaktiv" value={metrics.inactive} hint="Ohne aktive Betreuung" tone={metrics.inactive > 0 ? 'amber' : 'default'} data-testid="operator-customers-inactive" />
        <ProductStatCard icon={Mail} label="Mit Kontakt" value={metrics.withEmail} hint="E-Mail für Follow-up vorhanden" tone="blue" data-testid="operator-customers-contact" />
      </div>

      <ProductSection
        eyebrow="Customer ledger"
        title="Kundenliste"
        description="Direkte Operator-Sicht auf Kontakt, Status und Eingriffe."
        actions={<ProductInlineActions mode="operator" items={[{ label: 'Aktualisieren', onClick: refetch, className: 'border-zinc-700 text-zinc-300 hover:bg-zinc-800' }]} />}
      >
        <div className="p-4">
          {list.length === 0 ? (
            <ProductPageState kind="empty" compact title="Keine Kunden im Scope" description="Sobald Kunden angelegt oder sichtbar sind, erscheinen sie hier mit Status und Kontaktinformationen." data-testid="operator-customers-empty" />
          ) : (
            <ProductDataTable
              columns={[
                { key: 'customer', label: 'Kunde' },
                { key: 'email', label: 'E-Mail' },
                { key: 'status', label: 'Status' },
                { key: 'created', label: 'Erstellt' },
                ...(canManage ? [{ key: 'actions', label: 'Aktionen', className: 'text-right' }] : []),
              ]}
              data-testid="customers-table"
            >
              {list.map((c) => (
                <tr key={c.id} className="text-zinc-300 hover:bg-zinc-900/30">
                  <td className="px-4 py-3">
                    <div>
                      <p className="font-medium text-white">{c.name}</p>
                      <p className="mt-1 font-mono text-[11px] text-zinc-500">{c.id}</p>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-zinc-400">{c.contact_email || '—'}</td>
                  <td className="px-4 py-3"><StatusBadge status={c.status} /></td>
                  <td className="px-4 py-3 text-xs text-zinc-400">{c.created_at ? new Date(c.created_at).toLocaleDateString('de-DE') : '—'}</td>
                  {canManage ? (
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1.5">
                        <button onClick={() => handleEdit(c)} className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white" data-testid={`edit-customer-${c.id}`}>
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button onClick={() => handleToggleStatus(c)} className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-800 hover:text-white" data-testid={`toggle-customer-${c.id}`}>
                          {c.status === 'active' ? <Ban className="w-3.5 h-3.5" /> : <CheckCircle className="w-3.5 h-3.5" />}
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" data-testid="customer-form-modal">
          <ProductDetailCard title={editItem ? 'Kunde bearbeiten' : 'Neuer Kunde'} eyebrow="Operator action" description="Kompakter Steuerdialog für Stammdaten im gemeinsamen Product-System.">
            <div className="w-full max-w-md">
              <div className="mb-4 flex items-center justify-end">
                <button onClick={resetForm} className="text-zinc-400 hover:text-white"><X className="w-5 h-5" /></button>
              </div>
              <form onSubmit={handleSubmit} className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs text-zinc-400">Name</label>
                  <input type="text" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white" required data-testid="customer-form-name" />
                </div>
                <div>
                  <label className="mb-1 block text-xs text-zinc-400">E-Mail</label>
                  <input type="email" value={form.contact_email} onChange={e => setForm(f => ({ ...f, contact_email: e.target.value }))} className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white" data-testid="customer-form-email" />
                </div>
                <div className="flex gap-2 pt-2">
                  <Button type="submit" className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-sm" data-testid="customer-form-submit">{editItem ? 'Speichern' : 'Erstellen'}</Button>
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

function StatusBadge({ status }) {
  const conf = {
    active: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    inactive: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/20',
    blocked: 'bg-red-500/10 text-red-400 border-red-500/20',
  };
  const labels = { active: 'Aktiv', inactive: 'Inaktiv', blocked: 'Gesperrt' };
  return <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${conf[status] || conf.inactive}`}>{labels[status] || status}</span>;
}
