import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  KeyRound, Building2, MapPin, Monitor, FileKey,
  Plus, RefreshCw, Ban, CheckCircle, Clock, ArrowUpRight,
  Users, AlertTriangle, Shield
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useAuth } from '../../context/AuthContext';
import { useI18n } from '../../context/I18nContext';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const STATUS_COLORS = {
  active: 'text-emerald-400 bg-emerald-500/10',
  grace: 'text-amber-400 bg-amber-500/10',
  expired: 'text-red-400 bg-red-500/10',
  blocked: 'text-red-400 bg-red-500/10',
  test: 'text-blue-400 bg-blue-500/10',
  no_license: 'text-zinc-500 bg-zinc-500/10',
};

function StatusBadge({ status, t }) {
  const key = `lic_status_${status}`;
  const colorClass = STATUS_COLORS[status] || STATUS_COLORS.no_license;
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${colorClass}`} data-testid={`lic-status-${status}`}>
      {t(key) || status}
    </span>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <Card className="bg-zinc-900 border-zinc-800">
      <CardContent className="p-4 flex items-center gap-3">
        <div className={`p-2 rounded ${color || 'bg-zinc-800'}`}>
          <Icon className="w-5 h-5 text-white" />
        </div>
        <div>
          <p className="text-2xl font-bold text-white">{value}</p>
          <p className="text-xs text-zinc-400">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}

function SimpleForm({ fields, onSubmit, submitLabel }) {
  const [values, setValues] = useState({});
  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(values);
    setValues({});
  };
  return (
    <form onSubmit={handleSubmit} className="space-y-3 p-4 bg-zinc-800/50 rounded-sm">
      {fields.map(f => (
        <div key={f.name} className="flex flex-col gap-1">
          <label className="text-xs text-zinc-400">{f.label}</label>
          {f.type === 'select' ? (
            <select
              className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white"
              value={values[f.name] || ''}
              onChange={e => setValues(v => ({...v, [f.name]: e.target.value}))}
              required={f.required}
              data-testid={`lic-form-${f.name}`}
            >
              <option value="">-- Waehlen --</option>
              {f.options?.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          ) : (
            <input
              type={f.type || 'text'}
              className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white"
              placeholder={f.placeholder}
              value={values[f.name] || ''}
              onChange={e => setValues(v => ({...v, [f.name]: e.target.value}))}
              required={f.required}
              data-testid={`lic-form-${f.name}`}
            />
          )}
        </div>
      ))}
      <Button type="submit" className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="lic-form-submit">
        <Plus className="w-4 h-4 mr-1" /> {submitLabel}
      </Button>
    </form>
  );
}

export default function Licensing() {
  const { token } = useAuth();
  const { t } = useI18n();
  const headers = { Authorization: `Bearer ${token}` };

  const [dashboard, setDashboard] = useState(null);
  const [customers, setCustomers] = useState([]);
  const [locations, setLocations] = useState([]);
  const [devices, setDevices] = useState([]);
  const [licenses, setLicenses] = useState([]);
  const [showForm, setShowForm] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [dash, cust, loc, dev, lic] = await Promise.all([
        axios.get(`${API}/licensing/dashboard`, { headers }),
        axios.get(`${API}/licensing/customers`, { headers }),
        axios.get(`${API}/licensing/locations`, { headers }),
        axios.get(`${API}/licensing/devices`, { headers }),
        axios.get(`${API}/licensing/licenses`, { headers }),
      ]);
      setDashboard(dash.data);
      setCustomers(cust.data);
      setLocations(loc.data);
      setDevices(dev.data);
      setLicenses(lic.data);
    } catch (err) {
      toast.error('Lizenzdaten konnten nicht geladen werden');
    }
  }, [token]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const createEntity = async (endpoint, data) => {
    try {
      await axios.post(`${API}/licensing/${endpoint}`, data, { headers });
      toast.success('Erstellt');
      setShowForm(null);
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    }
  };

  const licenseAction = async (id, action, body = {}) => {
    try {
      await axios.post(`${API}/licensing/licenses/${id}/${action}`, body, { headers });
      toast.success(`Lizenz: ${action}`);
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    }
  };

  return (
    <div className="space-y-6" data-testid="licensing-page">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <KeyRound className="w-6 h-6 text-amber-500" /> {t('licensing')}
        </h1>
        <Button variant="ghost" onClick={fetchAll} className="text-zinc-400" data-testid="lic-refresh">
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      {/* Dashboard Stats */}
      {dashboard && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3" data-testid="lic-dashboard-stats">
          <StatCard icon={Building2} label={t('lic_customers')} value={dashboard.customers} color="bg-blue-500/20" />
          <StatCard icon={MapPin} label={t('lic_locations')} value={dashboard.locations} color="bg-purple-500/20" />
          <StatCard icon={Monitor} label={t('lic_devices')} value={dashboard.devices} color="bg-cyan-500/20" />
          <StatCard icon={FileKey} label={t('lic_licenses')} value={dashboard.licenses_total} color="bg-amber-500/20" />
          <StatCard icon={CheckCircle} label={t('lic_status_active')} value={dashboard.licenses_active} color="bg-emerald-500/20" />
          <StatCard icon={Ban} label={t('lic_status_blocked')} value={dashboard.licenses_blocked} color="bg-red-500/20" />
        </div>
      )}

      <Tabs defaultValue="customers" className="w-full">
        <TabsList className="bg-zinc-800 border border-zinc-700" data-testid="lic-tabs">
          <TabsTrigger value="customers" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="lic-tab-customers">
            <Building2 className="w-4 h-4 mr-1" /> {t('lic_customers')}
          </TabsTrigger>
          <TabsTrigger value="locations" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="lic-tab-locations">
            <MapPin className="w-4 h-4 mr-1" /> {t('lic_locations')}
          </TabsTrigger>
          <TabsTrigger value="devices" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="lic-tab-devices">
            <Monitor className="w-4 h-4 mr-1" /> {t('lic_devices')}
          </TabsTrigger>
          <TabsTrigger value="licenses" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="lic-tab-licenses">
            <FileKey className="w-4 h-4 mr-1" /> {t('lic_licenses')}
          </TabsTrigger>
        </TabsList>

        {/* Customers */}
        <TabsContent value="customers">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-white text-base">{t('lic_customers')}</CardTitle>
              <Button size="sm" onClick={() => setShowForm(showForm === 'customer' ? null : 'customer')}
                className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="lic-add-customer-btn">
                <Plus className="w-4 h-4 mr-1" /> {t('lic_create_customer')}
              </Button>
            </CardHeader>
            <CardContent className="space-y-2">
              {showForm === 'customer' && (
                <SimpleForm
                  fields={[
                    { name: 'name', label: t('lic_name'), required: true, placeholder: 'Cafe Berlin' },
                    { name: 'contact_email', label: t('lic_email'), type: 'email', placeholder: 'info@cafe.de' },
                    { name: 'contact_phone', label: t('lic_phone'), placeholder: '+49 30 12345' },
                  ]}
                  onSubmit={d => createEntity('customers', d)}
                  submitLabel={t('lic_create_customer')}
                />
              )}
              {customers.length === 0 && <p className="text-sm text-zinc-500">{t('lic_no_data')}</p>}
              {customers.map(c => (
                <div key={c.id} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm" data-testid={`lic-customer-${c.id}`}>
                  <div>
                    <p className="text-sm text-white font-medium">{c.name}</p>
                    <p className="text-xs text-zinc-500">{c.contact_email} {c.contact_phone && `| ${c.contact_phone}`}</p>
                  </div>
                  <StatusBadge status={c.status} t={t} />
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Locations */}
        <TabsContent value="locations">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-white text-base">{t('lic_locations')}</CardTitle>
              <Button size="sm" onClick={() => setShowForm(showForm === 'location' ? null : 'location')}
                className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="lic-add-location-btn">
                <Plus className="w-4 h-4 mr-1" /> {t('lic_create_location')}
              </Button>
            </CardHeader>
            <CardContent className="space-y-2">
              {showForm === 'location' && (
                <SimpleForm
                  fields={[
                    { name: 'customer_id', label: t('lic_customers'), required: true, type: 'select',
                      options: customers.map(c => ({ value: c.id, label: c.name })) },
                    { name: 'name', label: t('lic_name'), required: true, placeholder: 'Standort Mitte' },
                    { name: 'address', label: t('lic_address'), placeholder: 'Alexanderplatz 1, Berlin' },
                  ]}
                  onSubmit={d => createEntity('locations', d)}
                  submitLabel={t('lic_create_location')}
                />
              )}
              {locations.length === 0 && <p className="text-sm text-zinc-500">{t('lic_no_data')}</p>}
              {locations.map(loc => {
                const cust = customers.find(c => c.id === loc.customer_id);
                return (
                  <div key={loc.id} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm" data-testid={`lic-location-${loc.id}`}>
                    <div>
                      <p className="text-sm text-white font-medium">{loc.name}</p>
                      <p className="text-xs text-zinc-500">{cust?.name} {loc.address && `| ${loc.address}`}</p>
                    </div>
                    <StatusBadge status={loc.status} t={t} />
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Devices */}
        <TabsContent value="devices">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-white text-base">{t('lic_devices')}</CardTitle>
              <Button size="sm" onClick={() => setShowForm(showForm === 'device' ? null : 'device')}
                className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="lic-add-device-btn">
                <Plus className="w-4 h-4 mr-1" /> {t('lic_create_device')}
              </Button>
            </CardHeader>
            <CardContent className="space-y-2">
              {showForm === 'device' && (
                <SimpleForm
                  fields={[
                    { name: 'location_id', label: t('lic_locations'), required: true, type: 'select',
                      options: locations.map(l => ({ value: l.id, label: l.name })) },
                    { name: 'device_name', label: t('lic_device_name'), placeholder: 'Board 1' },
                    { name: 'board_id', label: t('lic_board_id'), placeholder: 'BOARD-1' },
                  ]}
                  onSubmit={d => createEntity('devices', d)}
                  submitLabel={t('lic_create_device')}
                />
              )}
              {devices.length === 0 && <p className="text-sm text-zinc-500">{t('lic_no_data')}</p>}
              {devices.map(d => {
                const loc = locations.find(l => l.id === d.location_id);
                return (
                  <div key={d.id} className="flex items-center justify-between p-3 bg-zinc-800/50 rounded-sm" data-testid={`lic-device-${d.id}`}>
                    <div>
                      <p className="text-sm text-white font-medium">{d.device_name || d.board_id || d.id}</p>
                      <p className="text-xs text-zinc-500">{loc?.name} {d.board_id && `| Board: ${d.board_id}`}</p>
                    </div>
                    <StatusBadge status={d.status} t={t} />
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Licenses */}
        <TabsContent value="licenses">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-white text-base">{t('lic_licenses')}</CardTitle>
              <Button size="sm" onClick={() => setShowForm(showForm === 'license' ? null : 'license')}
                className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="lic-add-license-btn">
                <Plus className="w-4 h-4 mr-1" /> {t('lic_create_license')}
              </Button>
            </CardHeader>
            <CardContent className="space-y-2">
              {showForm === 'license' && (
                <SimpleForm
                  fields={[
                    { name: 'customer_id', label: t('lic_customers'), required: true, type: 'select',
                      options: customers.map(c => ({ value: c.id, label: c.name })) },
                    { name: 'plan_type', label: t('lic_plan'), type: 'select',
                      options: [
                        { value: 'standard', label: 'Standard' },
                        { value: 'premium', label: 'Premium' },
                        { value: 'test', label: 'Test' },
                      ]},
                    { name: 'max_devices', label: t('lic_max_devices'), type: 'number', placeholder: '1' },
                    { name: 'ends_at', label: t('lic_ends_at'), type: 'datetime-local' },
                    { name: 'grace_days', label: t('lic_grace_days'), type: 'number', placeholder: '7' },
                  ]}
                  onSubmit={d => {
                    const body = { ...d };
                    if (body.max_devices) body.max_devices = parseInt(body.max_devices);
                    if (body.grace_days) body.grace_days = parseInt(body.grace_days);
                    if (body.ends_at) body.ends_at = new Date(body.ends_at).toISOString();
                    if (!body.plan_type) body.plan_type = 'standard';
                    createEntity('licenses', body);
                  }}
                  submitLabel={t('lic_create_license')}
                />
              )}
              {licenses.length === 0 && <p className="text-sm text-zinc-500">{t('lic_no_data')}</p>}
              {licenses.map(lic => {
                const cust = customers.find(c => c.id === lic.customer_id);
                return (
                  <div key={lic.id} className="p-3 bg-zinc-800/50 rounded-sm space-y-2" data-testid={`lic-license-${lic.id}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <FileKey className="w-4 h-4 text-amber-500" />
                        <span className="text-sm text-white font-medium">{cust?.name || lic.customer_id}</span>
                        <span className="text-xs text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">{lic.plan_type}</span>
                      </div>
                      <StatusBadge status={lic.status} t={t} />
                    </div>
                    <div className="flex flex-wrap gap-3 text-xs text-zinc-400">
                      <span>{t('lic_max_devices')}: {lic.max_devices}</span>
                      {lic.ends_at && <span>{t('lic_ends_at')}: {new Date(lic.ends_at).toLocaleDateString('de-DE')}</span>}
                      {lic.grace_until && <span>{t('lic_grace_until')}: {new Date(lic.grace_until).toLocaleDateString('de-DE')}</span>}
                      <span>{t('lic_grace_days')}: {lic.grace_days}</span>
                    </div>
                    <div className="flex gap-2 pt-1">
                      {lic.status !== 'blocked' && (
                        <Button size="sm" variant="outline" className="border-red-500/30 text-red-400 text-xs"
                          onClick={() => { if (confirm(t('lic_block_confirm'))) licenseAction(lic.id, 'block'); }}
                          data-testid={`lic-block-${lic.id}`}>
                          <Ban className="w-3 h-3 mr-1" /> {t('lic_block')}
                        </Button>
                      )}
                      {lic.status === 'blocked' && (
                        <Button size="sm" variant="outline" className="border-emerald-500/30 text-emerald-400 text-xs"
                          onClick={() => licenseAction(lic.id, 'activate')}
                          data-testid={`lic-activate-${lic.id}`}>
                          <CheckCircle className="w-3 h-3 mr-1" /> {t('lic_activate')}
                        </Button>
                      )}
                      <Button size="sm" variant="outline" className="border-amber-500/30 text-amber-400 text-xs"
                        onClick={() => licenseAction(lic.id, 'extend', { days: 30 })}
                        data-testid={`lic-extend-${lic.id}`}>
                        <ArrowUpRight className="w-3 h-3 mr-1" /> {t('lic_extend')} +30d
                      </Button>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
