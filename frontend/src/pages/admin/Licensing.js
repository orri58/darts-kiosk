import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  KeyRound, Building2, MapPin, Monitor, FileKey,
  Plus, RefreshCw, Ban, CheckCircle, Clock, ArrowUpRight,
  Users, AlertTriangle, Shield, Link2, Unlink, Fingerprint,
  ScrollText, Filter, Activity, Wifi, WifiOff, Server, Settings2, Save,
  Ticket, Copy, XCircle, Eye
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

const BINDING_COLORS = {
  bound: 'text-emerald-400 bg-emerald-500/10',
  unbound: 'text-zinc-400 bg-zinc-500/10',
  mismatch_grace: 'text-amber-400 bg-amber-500/10',
  mismatch_expired: 'text-red-400 bg-red-500/10',
  first_bind: 'text-blue-400 bg-blue-500/10',
};

function BindingBadge({ status, t }) {
  const key = `lic_binding_${status || 'unbound'}`;
  const colorClass = BINDING_COLORS[status] || BINDING_COLORS.unbound;
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${colorClass}`} data-testid={`lic-binding-${status}`}>
      {t(key) || status || 'unbound'}
    </span>
  );
}

const AUDIT_COLORS = {
  LICENSE_CREATED: 'text-blue-400 bg-blue-500/10',
  LICENSE_ACTIVATED: 'text-emerald-400 bg-emerald-500/10',
  LICENSE_BLOCKED: 'text-red-400 bg-red-500/10',
  LICENSE_EXTENDED: 'text-cyan-400 bg-cyan-500/10',
  LICENSE_EXPIRED: 'text-zinc-400 bg-zinc-500/10',
  BIND_CREATED: 'text-emerald-400 bg-emerald-500/10',
  BIND_MISMATCH_DETECTED: 'text-amber-400 bg-amber-500/10',
  BIND_GRACE_ACTIVE: 'text-amber-400 bg-amber-500/10',
  BIND_BLOCKED: 'text-red-400 bg-red-500/10',
  DEVICE_REBOUND: 'text-cyan-400 bg-cyan-500/10',
  LICENSE_CHECK_SUCCESS: 'text-emerald-400 bg-emerald-500/10',
  LICENSE_CHECK_FAILED: 'text-red-400 bg-red-500/10',
  REMOTE_SYNC_OK: 'text-emerald-400 bg-emerald-500/10',
  REMOTE_SYNC_FAILED: 'text-amber-400 bg-amber-500/10',
  SYNC_CONFIG_UPDATED: 'text-blue-400 bg-blue-500/10',
  REG_TOKEN_CREATED: 'text-blue-400 bg-blue-500/10',
  REG_TOKEN_REVOKED: 'text-red-400 bg-red-500/10',
  REG_TOKEN_USED: 'text-cyan-400 bg-cyan-500/10',
  DEVICE_REGISTERED: 'text-emerald-400 bg-emerald-500/10',
  DEVICE_REGISTRATION_FAILED: 'text-red-400 bg-red-500/10',
  DEVICE_REGISTERED_BIND_CONFLICT: 'text-red-400 bg-red-500/10',
};

function AuditBadge({ action }) {
  const colorClass = AUDIT_COLORS[action] || 'text-zinc-400 bg-zinc-500/10';
  return (
    <span className={`text-xs px-1.5 py-0.5 rounded font-mono whitespace-nowrap ${colorClass}`} data-testid={`lic-audit-badge-${action}`}>
      {action}
    </span>
  );
}

const TOKEN_STATUS_COLORS = {
  active: 'text-emerald-400 bg-emerald-500/10',
  used: 'text-blue-400 bg-blue-500/10',
  expired: 'text-zinc-400 bg-zinc-500/10',
  revoked: 'text-red-400 bg-red-500/10',
};

function TokenStatusBadge({ status }) {
  const colorClass = TOKEN_STATUS_COLORS[status] || TOKEN_STATUS_COLORS.expired;
  const labels = { active: 'Aktiv', used: 'Verwendet', expired: 'Abgelaufen', revoked: 'Widerrufen' };
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${colorClass}`} data-testid={`token-status-${status}`}>
      {labels[status] || status}
    </span>
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
  const [deviceIdentity, setDeviceIdentity] = useState(null);
  const [auditLog, setAuditLog] = useState({ entries: [], total: 0 });
  const [auditFilter, setAuditFilter] = useState({ action: '', limit: 30 });
  const [checkStatus, setCheckStatus] = useState(null);
  const [syncConfig, setSyncConfig] = useState({ enabled: false, server_url: '', api_key_masked: '', api_key_set: false, interval_hours: 6, device_name: '' });
  const [syncForm, setSyncForm] = useState({ server_url: '', api_key: '', interval_hours: 6, device_name: '', enabled: false });
  const [syncStatus, setSyncStatus] = useState(null);
  const [regTokens, setRegTokens] = useState([]);
  const [showTokenForm, setShowTokenForm] = useState(false);
  const [tokenForm, setTokenForm] = useState({ customer_id: '', location_id: '', license_id: '', device_name_template: '', expires_in_hours: 72, note: '' });
  const [newRawToken, setNewRawToken] = useState(null);
  const [regStatus, setRegStatus] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [dash, cust, loc, dev, lic, identity, checkSt, syncCfg, syncSt, regSt] = await Promise.all([
        axios.get(`${API}/licensing/dashboard`, { headers }),
        axios.get(`${API}/licensing/customers`, { headers }),
        axios.get(`${API}/licensing/locations`, { headers }),
        axios.get(`${API}/licensing/devices`, { headers }),
        axios.get(`${API}/licensing/licenses`, { headers }),
        axios.get(`${API}/licensing/device-identity`, { headers }).catch(() => ({ data: null })),
        axios.get(`${API}/licensing/check-status`, { headers }).catch(() => ({ data: null })),
        axios.get(`${API}/licensing/sync-config`, { headers }).catch(() => ({ data: {} })),
        axios.get(`${API}/licensing/sync-status`, { headers }).catch(() => ({ data: null })),
        axios.get(`${API}/licensing/registration-status`).catch(() => ({ data: null })),
      ]);
      setDashboard(dash.data);
      setCustomers(cust.data);
      setLocations(loc.data);
      setDevices(dev.data);
      setLicenses(lic.data);
      setDeviceIdentity(identity.data);
      setCheckStatus(checkSt.data);
      if (syncCfg.data) {
        setSyncConfig(syncCfg.data);
        setSyncForm({
          server_url: syncCfg.data.server_url || '',
          api_key: '',
          interval_hours: syncCfg.data.interval_hours || 6,
          device_name: syncCfg.data.device_name || '',
          enabled: syncCfg.data.enabled || false,
        });
      }
      setSyncStatus(syncSt.data);
      setRegStatus(regSt.data);
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

  const rebindDevice = async (deviceId) => {
    if (!deviceIdentity?.install_id) {
      toast.error(t('lic_no_device_identity'));
      return;
    }
    if (!confirm(t('lic_rebind_confirm'))) return;
    try {
      await axios.post(`${API}/licensing/devices/${deviceId}/rebind`,
        { new_install_id: deviceIdentity.install_id }, { headers });
      toast.success(t('lic_rebind_success'));
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    }
  };

  const fetchAuditLog = useCallback(async () => {
    try {
      const params = new URLSearchParams({ limit: auditFilter.limit });
      if (auditFilter.action) params.set('action', auditFilter.action);
      const res = await axios.get(`${API}/licensing/audit-log?${params}`, { headers });
      setAuditLog(res.data);
    } catch { /* silent */ }
  }, [token, auditFilter]);

  const triggerCheck = async () => {
    try {
      await axios.post(`${API}/licensing/check-now`, {}, { headers });
      toast.success(t('lic_check_triggered'));
      setTimeout(() => { fetchAll(); fetchAuditLog(); }, 2000);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    }
  };

  const saveSyncConfig = async () => {
    try {
      const body = { ...syncForm };
      if (!body.api_key) delete body.api_key; // don't overwrite if empty
      await axios.post(`${API}/licensing/sync-config`, body, { headers });
      toast.success(t('lic_sync_config_saved') || 'Sync-Konfiguration gespeichert');
      fetchAll();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    }
  };

  const triggerSyncNow = async () => {
    try {
      await axios.post(`${API}/licensing/sync-now`, {}, { headers });
      toast.success(t('lic_sync_triggered') || 'Sync gestartet');
      setTimeout(() => { fetchAll(); fetchAuditLog(); }, 3000);
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Fehler');
    }
  };

  // === Registration Token Functions (v3.5.1) ===

  const fetchRegTokens = async () => {
    try {
      // Tokens are on the CENTRAL server — use sync config URL
      const syncCfgUrl = syncConfig.server_url || syncForm.server_url;
      if (!syncCfgUrl) {
        toast.error('Keine zentrale Server-URL konfiguriert');
        return;
      }
      const res = await axios.get(`${syncCfgUrl}/api/registration-tokens`, {
        headers: { Authorization: 'Bearer admin-secret-token' },
      });
      setRegTokens(res.data);
    } catch (err) {
      toast.error('Tokens konnten nicht geladen werden: ' + (err.response?.data?.detail || err.message));
    }
  };

  const createRegToken = async () => {
    try {
      const syncCfgUrl = syncConfig.server_url || syncForm.server_url;
      if (!syncCfgUrl) {
        toast.error('Keine zentrale Server-URL konfiguriert');
        return;
      }
      const body = { ...tokenForm };
      if (!body.customer_id) delete body.customer_id;
      if (!body.location_id) delete body.location_id;
      if (!body.license_id) delete body.license_id;
      if (!body.device_name_template) delete body.device_name_template;
      if (!body.note) delete body.note;

      const res = await axios.post(`${syncCfgUrl}/api/registration-tokens`, body, {
        headers: { Authorization: 'Bearer admin-secret-token', 'Content-Type': 'application/json' },
      });
      setNewRawToken(res.data.raw_token);
      setShowTokenForm(false);
      setTokenForm({ customer_id: '', location_id: '', license_id: '', device_name_template: '', expires_in_hours: 72, note: '' });
      fetchRegTokens();
      toast.success('Token erstellt');
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Token konnte nicht erstellt werden');
    }
  };

  const revokeRegToken = async (tokenId) => {
    try {
      const syncCfgUrl = syncConfig.server_url || syncForm.server_url;
      await axios.post(`${syncCfgUrl}/api/registration-tokens/${tokenId}/revoke`, {}, {
        headers: { Authorization: 'Bearer admin-secret-token' },
      });
      toast.success('Token widerrufen');
      fetchRegTokens();
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
          <TabsTrigger value="audit" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="lic-tab-audit" onClick={() => fetchAuditLog()}>
            <ScrollText className="w-4 h-4 mr-1" /> {t('lic_audit_log')}
          </TabsTrigger>
          <TabsTrigger value="sync" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="lic-tab-sync">
            <Server className="w-4 h-4 mr-1" /> {t('lic_sync') || 'Sync'}
          </TabsTrigger>
          <TabsTrigger value="tokens" className="data-[state=active]:bg-amber-500 data-[state=active]:text-black" data-testid="lic-tab-tokens" onClick={() => fetchRegTokens()}>
            <Ticket className="w-4 h-4 mr-1" /> {t('lic_reg_tokens') || 'Tokens'}
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
          {/* Device Identity Card */}
          {deviceIdentity && (
            <Card className="bg-zinc-900 border-zinc-800 mb-4">
              <CardContent className="p-4">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded bg-cyan-500/20">
                    <Fingerprint className="w-5 h-5 text-cyan-400" />
                  </div>
                  <div className="flex-1">
                    <p className="text-xs text-zinc-400">{t('lic_this_device')}</p>
                    <p className="text-sm text-white font-mono" data-testid="lic-device-install-id">{deviceIdentity.install_id}</p>
                    {deviceIdentity.fingerprints && (
                      <p className="text-xs text-zinc-500 mt-0.5">
                        {deviceIdentity.fingerprints.hostname} / {deviceIdentity.fingerprints.platform}
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
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
                const isThisDevice = deviceIdentity && d.install_id === deviceIdentity.install_id;
                const isMismatch = d.binding_status === 'mismatch_grace' || d.binding_status === 'mismatch_expired';
                const isMismatchExpired = d.binding_status === 'mismatch_expired';
                return (
                  <div key={d.id} className={`p-3 rounded-sm space-y-2 ${isMismatchExpired ? 'bg-red-500/5 border border-red-500/20' : isMismatch ? 'bg-amber-500/5 border border-amber-500/20' : 'bg-zinc-800/50'}`} data-testid={`lic-device-${d.id}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Monitor className="w-4 h-4 text-cyan-400" />
                        <span className="text-sm text-white font-medium">{d.device_name || d.board_id || d.id.slice(0, 8)}</span>
                        {isThisDevice && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-400" data-testid="lic-this-device-badge">
                            {t('lic_this_device')}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <BindingBadge status={d.binding_status} t={t} />
                        <StatusBadge status={d.status} t={t} />
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-3 text-xs text-zinc-400">
                      <span>{loc?.name}</span>
                      {d.board_id && <span>Board: {d.board_id}</span>}
                      {d.install_id && (
                        <span className="font-mono text-zinc-500" data-testid={`lic-device-iid-${d.id}`}>
                          ID: {d.install_id.slice(0, 12)}...
                        </span>
                      )}
                      {d.last_seen_at && <span>{t('lic_last_seen')}: {new Date(d.last_seen_at).toLocaleString('de-DE')}</span>}
                    </div>
                    {isMismatch && (
                      <div className="space-y-1.5 mt-1">
                        <div className="flex items-center gap-2">
                          <AlertTriangle className={`w-3.5 h-3.5 ${isMismatchExpired ? 'text-red-400' : 'text-amber-400'}`} />
                          <span className={`text-xs ${isMismatchExpired ? 'text-red-400' : 'text-amber-400'}`}>
                            {isMismatchExpired ? t('lic_binding_mismatch_expired_hint') : t('lic_binding_mismatch_grace_hint')}
                          </span>
                          <Button size="sm" variant="outline" className="border-amber-500/30 text-amber-400 text-xs ml-auto"
                            onClick={() => rebindDevice(d.id)} data-testid={`lic-rebind-${d.id}`}>
                            <Link2 className="w-3 h-3 mr-1" /> {t('lic_rebind')}
                          </Button>
                        </div>
                        {d.mismatch_detected_at && (
                          <p className="text-xs text-zinc-500" data-testid={`lic-mismatch-ts-${d.id}`}>
                            {t('lic_mismatch_since')}: {new Date(d.mismatch_detected_at).toLocaleString('de-DE')}
                          </p>
                        )}
                        {d.previous_install_id && (
                          <p className="text-xs text-zinc-500 font-mono" data-testid={`lic-prev-iid-${d.id}`}>
                            {t('lic_previous_id')}: {d.previous_install_id.slice(0, 12)}...
                          </p>
                        )}
                      </div>
                    )}
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

        {/* Audit Log */}
        <TabsContent value="audit">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-3 flex flex-row items-center justify-between">
              <CardTitle className="text-white text-base">{t('lic_audit_log')}</CardTitle>
              <div className="flex items-center gap-2">
                {checkStatus && (
                  <span className="text-xs text-zinc-400" data-testid="lic-check-status">
                    {t('lic_last_check')}: {checkStatus.last_check_at ? new Date(checkStatus.last_check_at).toLocaleString('de-DE') : '—'}
                    {checkStatus.last_check_ok === false && <span className="text-red-400 ml-1">({t('lic_check_failed')})</span>}
                    {checkStatus.last_check_ok === true && <span className="text-emerald-400 ml-1">OK</span>}
                    {checkStatus.last_check_source && <span className="text-zinc-500 ml-1">({checkStatus.last_check_source})</span>}
                  </span>
                )}
                <Button size="sm" onClick={triggerCheck} className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="lic-trigger-check-btn">
                  <Activity className="w-4 h-4 mr-1" /> {t('lic_check_now')}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {/* Filter */}
              <div className="flex items-center gap-2 mb-3">
                <Filter className="w-4 h-4 text-zinc-400" />
                <select
                  className="bg-zinc-800 border border-zinc-700 text-sm text-white rounded px-2 py-1"
                  value={auditFilter.action}
                  onChange={e => { setAuditFilter(f => ({ ...f, action: e.target.value })); setTimeout(fetchAuditLog, 100); }}
                  data-testid="lic-audit-filter-action"
                >
                  <option value="">{t('lic_all_events')}</option>
                  {['LICENSE_CREATED','LICENSE_ACTIVATED','LICENSE_BLOCKED','LICENSE_EXTENDED',
                    'BIND_CREATED','BIND_MISMATCH_DETECTED','BIND_BLOCKED','DEVICE_REBOUND',
                    'LICENSE_CHECK_SUCCESS','LICENSE_CHECK_FAILED',
                    'REMOTE_SYNC_OK','REMOTE_SYNC_FAILED','SYNC_CONFIG_UPDATED',
                    'REG_TOKEN_CREATED','REG_TOKEN_REVOKED','REG_TOKEN_USED',
                    'DEVICE_REGISTERED','DEVICE_REGISTRATION_FAILED','DEVICE_REGISTERED_BIND_CONFLICT'].map(a => (
                    <option key={a} value={a}>{a}</option>
                  ))}
                </select>
                <span className="text-xs text-zinc-500">{auditLog.total} {t('lic_entries')}</span>
              </div>

              {/* Entries */}
              {auditLog.entries.length === 0 && <p className="text-sm text-zinc-500">{t('lic_no_data')}</p>}
              <div className="space-y-1.5 max-h-[500px] overflow-y-auto">
                {auditLog.entries.map(e => (
                  <div key={e.id} className="flex items-start gap-3 p-2 bg-zinc-800/50 rounded text-xs" data-testid={`lic-audit-${e.id}`}>
                    <div className="flex-shrink-0 w-[140px] text-zinc-500">
                      {e.timestamp ? new Date(e.timestamp).toLocaleString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit', day: '2-digit', month: '2-digit' }) : '—'}
                    </div>
                    <div className="flex-shrink-0">
                      <AuditBadge action={e.action} />
                    </div>
                    <div className="flex-1 text-zinc-300 break-all">
                      {e.message || e.action}
                      {e.actor && e.actor !== 'system' && (
                        <span className="text-zinc-500 ml-2">({e.actor})</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Sync (v3.5.0) */}
        <TabsContent value="sync">
          <div className="space-y-4">
            {/* Sync Status Card */}
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-white text-base flex items-center gap-2">
                  {syncStatus?.sync?.connected
                    ? <Wifi className="w-5 h-5 text-emerald-400" />
                    : <WifiOff className="w-5 h-5 text-zinc-500" />
                  }
                  {t('lic_sync_status') || 'Sync-Status'}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="p-3 bg-zinc-800/50 rounded" data-testid="sync-status-connection">
                    <p className="text-xs text-zinc-400 mb-1">{t('lic_sync_connection') || 'Verbindung'}</p>
                    <p className={`text-sm font-medium ${syncStatus?.sync?.connected ? 'text-emerald-400' : 'text-zinc-500'}`}>
                      {syncStatus?.sync?.connected
                        ? (t('lic_sync_connected') || 'Server verbunden')
                        : (t('lic_sync_offline') || 'Offline-Modus')
                      }
                    </p>
                  </div>
                  <div className="p-3 bg-zinc-800/50 rounded" data-testid="sync-status-last-sync">
                    <p className="text-xs text-zinc-400 mb-1">{t('lic_sync_last_sync') || 'Letzter Sync'}</p>
                    <p className="text-sm text-white">
                      {syncStatus?.sync?.last_sync_at
                        ? new Date(syncStatus.sync.last_sync_at).toLocaleString('de-DE')
                        : '—'}
                    </p>
                  </div>
                  <div className="p-3 bg-zinc-800/50 rounded" data-testid="sync-status-count">
                    <p className="text-xs text-zinc-400 mb-1">{t('lic_sync_count') || 'Sync-Anzahl'}</p>
                    <p className="text-sm text-white">{syncStatus?.sync?.sync_count || 0}</p>
                  </div>
                </div>
                {syncStatus?.sync?.last_error && (
                  <div className="p-3 bg-red-500/5 border border-red-500/20 rounded" data-testid="sync-status-error">
                    <p className="text-xs text-red-400 flex items-center gap-1">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      {syncStatus.sync.last_error}
                    </p>
                  </div>
                )}
                {/* Source info */}
                {syncStatus?.checker?.last_check_source && (
                  <div className="flex items-center gap-2 text-xs text-zinc-400">
                    <Activity className="w-3.5 h-3.5" />
                    {t('lic_sync_source') || 'Letzte Quelle'}: <span className="text-white">{syncStatus.checker.last_check_source}</span>
                    {syncStatus.checker.last_check_status && (
                      <StatusBadge status={syncStatus.checker.last_check_status} t={t} />
                    )}
                  </div>
                )}
                <Button size="sm" onClick={triggerSyncNow} className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="sync-trigger-btn">
                  <RefreshCw className="w-4 h-4 mr-1" /> {t('lic_sync_now') || 'Jetzt synchronisieren'}
                </Button>
              </CardContent>
            </Card>

            {/* Sync Configuration Card */}
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader className="pb-3">
                <CardTitle className="text-white text-base flex items-center gap-2">
                  <Settings2 className="w-5 h-5 text-amber-500" />
                  {t('lic_sync_config') || 'Sync-Konfiguration'}
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-3">
                  <label className="text-sm text-zinc-300">{t('lic_sync_enabled') || 'Remote-Sync aktiviert'}</label>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={syncForm.enabled}
                    onClick={() => setSyncForm(f => ({ ...f, enabled: !f.enabled }))}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${syncForm.enabled ? 'bg-emerald-500' : 'bg-zinc-700'}`}
                    data-testid="sync-config-enabled-toggle"
                  >
                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${syncForm.enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                  </button>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-zinc-400">{t('lic_sync_server_url') || 'Server-URL'}</label>
                    <input
                      type="url"
                      className="bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-white"
                      placeholder="https://central.example.com"
                      value={syncForm.server_url}
                      onChange={e => setSyncForm(f => ({ ...f, server_url: e.target.value }))}
                      data-testid="sync-config-server-url"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-zinc-400">
                      API-Key {syncConfig.api_key_set && <span className="text-emerald-400 ml-1">(gesetzt: {syncConfig.api_key_masked})</span>}
                    </label>
                    <input
                      type="password"
                      className="bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-white"
                      placeholder={syncConfig.api_key_set ? 'Leer lassen um beizubehalten' : 'dk_...'}
                      value={syncForm.api_key}
                      onChange={e => setSyncForm(f => ({ ...f, api_key: e.target.value }))}
                      data-testid="sync-config-api-key"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-zinc-400">{t('lic_sync_interval') || 'Sync-Intervall (Stunden)'}</label>
                    <input
                      type="number"
                      min={1}
                      max={24}
                      className="bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-white"
                      value={syncForm.interval_hours}
                      onChange={e => setSyncForm(f => ({ ...f, interval_hours: parseInt(e.target.value) || 6 }))}
                      data-testid="sync-config-interval"
                    />
                  </div>
                  <div className="flex flex-col gap-1">
                    <label className="text-xs text-zinc-400">{t('lic_sync_device_name') || 'Gerätename'}</label>
                    <input
                      type="text"
                      className="bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-sm text-white"
                      placeholder="Kiosk 1"
                      value={syncForm.device_name}
                      onChange={e => setSyncForm(f => ({ ...f, device_name: e.target.value }))}
                      data-testid="sync-config-device-name"
                    />
                  </div>
                </div>

                <Button onClick={saveSyncConfig} className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="sync-config-save-btn">
                  <Save className="w-4 h-4 mr-1" /> {t('lic_sync_save') || 'Konfiguration speichern'}
                </Button>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Registration Tokens (v3.5.1) */}
        <TabsContent value="tokens">
          <div className="space-y-4">
            {/* Registration Status */}
            {regStatus && (
              <Card className="bg-zinc-900 border-zinc-800">
                <CardContent className="py-3 flex items-center gap-3">
                  <Monitor className="w-4 h-4 text-zinc-400" />
                  <span className="text-sm text-zinc-300">{t('lic_reg_this_device') || 'Dieses Geraet'}:</span>
                  <span className={`text-sm font-medium ${regStatus.status === 'registered' ? 'text-emerald-400' : 'text-amber-400'}`} data-testid="reg-device-status">
                    {regStatus.status === 'registered' ? (t('lic_reg_registered') || 'Registriert') : (t('lic_reg_unregistered') || 'Nicht registriert')}
                  </span>
                  {regStatus.device_name && <span className="text-xs text-zinc-500">({regStatus.device_name})</span>}
                  {regStatus.customer_name && <span className="text-xs text-zinc-500">Kunde: {regStatus.customer_name}</span>}
                </CardContent>
              </Card>
            )}

            {/* New Token Created Banner */}
            {newRawToken && (
              <Card className="bg-emerald-500/10 border-emerald-500/30">
                <CardContent className="py-4">
                  <div className="flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-emerald-400 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-sm text-emerald-300 font-medium mb-2">{t('lic_reg_token_created') || 'Neuer Token erstellt — Nur jetzt sichtbar!'}</p>
                      <div className="flex items-center gap-2 p-2 bg-black/30 rounded font-mono text-sm text-white break-all" data-testid="reg-new-raw-token">
                        <span className="flex-1">{newRawToken}</span>
                        <button onClick={() => { navigator.clipboard?.writeText(newRawToken); toast.success('Kopiert'); }} className="text-emerald-400 hover:text-white flex-shrink-0">
                          <Copy className="w-4 h-4" />
                        </button>
                      </div>
                      <p className="text-xs text-zinc-500 mt-2">{t('lic_reg_token_warning') || 'Diesen Code sicher aufbewahren. Er wird nicht erneut angezeigt.'}</p>
                      <Button size="sm" onClick={() => setNewRawToken(null)} className="mt-2 bg-zinc-700 hover:bg-zinc-600 text-white text-xs">
                        {t('lic_reg_dismiss') || 'Verstanden'}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Token Management */}
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader className="pb-3 flex flex-row items-center justify-between">
                <CardTitle className="text-white text-base flex items-center gap-2">
                  <Ticket className="w-5 h-5 text-amber-500" />
                  {t('lic_reg_tokens') || 'Registration Tokens'}
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Button size="sm" onClick={fetchRegTokens} className="bg-zinc-700 hover:bg-zinc-600 text-white" data-testid="reg-refresh-btn">
                    <RefreshCw className="w-4 h-4" />
                  </Button>
                  <Button size="sm" onClick={() => setShowTokenForm(!showTokenForm)} className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="reg-create-btn">
                    <Plus className="w-4 h-4 mr-1" /> {t('lic_reg_create') || 'Token erstellen'}
                  </Button>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Create Token Form */}
                {showTokenForm && (
                  <div className="p-4 bg-zinc-800/50 rounded-lg space-y-3 border border-zinc-700" data-testid="reg-token-form">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                      <div className="flex flex-col gap-1">
                        <label className="text-xs text-zinc-400">{t('lic_customer') || 'Kunde'}</label>
                        <select className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white" value={tokenForm.customer_id} onChange={e => setTokenForm(f => ({...f, customer_id: e.target.value}))} data-testid="reg-form-customer">
                          <option value="">-- Optional --</option>
                          {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                      </div>
                      <div className="flex flex-col gap-1">
                        <label className="text-xs text-zinc-400">{t('lic_location') || 'Standort'}</label>
                        <select className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white" value={tokenForm.location_id} onChange={e => setTokenForm(f => ({...f, location_id: e.target.value}))} data-testid="reg-form-location">
                          <option value="">-- Optional --</option>
                          {locations.filter(l => !tokenForm.customer_id || l.customer_id === tokenForm.customer_id).map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                        </select>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      <div className="flex flex-col gap-1">
                        <label className="text-xs text-zinc-400">{t('lic_reg_expires') || 'Gueltig (Stunden)'}</label>
                        <input type="number" min={1} max={720} className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white" value={tokenForm.expires_in_hours} onChange={e => setTokenForm(f => ({...f, expires_in_hours: parseInt(e.target.value) || 72}))} data-testid="reg-form-expires" />
                      </div>
                      <div className="flex flex-col gap-1">
                        <label className="text-xs text-zinc-400">{t('lic_reg_device_template') || 'Geraetename-Vorlage'}</label>
                        <input type="text" className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white" placeholder="Kiosk Board 1" value={tokenForm.device_name_template} onChange={e => setTokenForm(f => ({...f, device_name_template: e.target.value}))} data-testid="reg-form-device-template" />
                      </div>
                      <div className="flex flex-col gap-1">
                        <label className="text-xs text-zinc-400">{t('lic_reg_note') || 'Notiz'}</label>
                        <input type="text" className="bg-zinc-900 border border-zinc-700 rounded px-3 py-2 text-sm text-white" placeholder="Fuer neuen Standort..." value={tokenForm.note} onChange={e => setTokenForm(f => ({...f, note: e.target.value}))} data-testid="reg-form-note" />
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <Button onClick={createRegToken} className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="reg-form-submit">
                        <Ticket className="w-4 h-4 mr-1" /> {t('lic_reg_generate') || 'Token generieren'}
                      </Button>
                      <Button onClick={() => setShowTokenForm(false)} className="bg-zinc-700 hover:bg-zinc-600 text-white">
                        {t('cancel') || 'Abbrechen'}
                      </Button>
                    </div>
                  </div>
                )}

                {/* Token List */}
                {regTokens.length === 0 && !showTokenForm && (
                  <p className="text-sm text-zinc-500">{t('lic_reg_no_tokens') || 'Keine Registration Tokens vorhanden. Erstellen Sie einen Token, um ein neues Geraet zu registrieren.'}</p>
                )}
                {regTokens.length > 0 && (
                  <div className="space-y-2 max-h-[500px] overflow-y-auto">
                    {regTokens.map(tk => (
                      <div key={tk.id} className="p-3 bg-zinc-800/50 rounded-lg flex items-center gap-3" data-testid={`reg-token-${tk.id}`}>
                        <div className="flex-shrink-0">
                          <TokenStatusBadge status={tk.status} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-white font-mono">{tk.token_preview}</span>
                            {tk.note && <span className="text-xs text-zinc-500 truncate">— {tk.note}</span>}
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
                            {tk.expires_at && <span>Ablauf: {new Date(tk.expires_at).toLocaleString('de-DE')}</span>}
                            {tk.created_by && <span>Von: {tk.created_by}</span>}
                            {tk.used_by_install_id && <span className="text-emerald-400">Benutzt von: {tk.used_by_install_id.substring(0, 12)}...</span>}
                          </div>
                        </div>
                        {tk.status === 'active' && (
                          <Button size="sm" onClick={() => revokeRegToken(tk.id)} className="bg-red-500/20 hover:bg-red-500/30 text-red-400 text-xs" data-testid={`reg-revoke-${tk.id}`}>
                            <XCircle className="w-3.5 h-3.5 mr-1" /> {t('lic_reg_revoke') || 'Widerrufen'}
                          </Button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
