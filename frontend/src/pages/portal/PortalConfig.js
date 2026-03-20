import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Settings, Globe, Building2, MapPin, Monitor, Save,
  ChevronRight, Layers, RefreshCw, Code, DollarSign,
  Palette, Gamepad2, AlertCircle
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { useCentralAuth } from '../../context/CentralAuthContext';

const SCOPE_ICONS = { global: Globe, customer: Building2, location: MapPin, device: Monitor };
const SCOPE_LABELS = { global: 'Global', customer: 'Kunde', location: 'Standort', device: 'Geraet' };

// Default config schema for form rendering
const CONFIG_SCHEMA = {
  pricing: {
    label: 'Preise',
    icon: DollarSign,
    fields: {
      mode: { type: 'select', label: 'Preismodell', options: ['per_game', 'per_time', 'per_credit'] },
      'per_game.price_per_credit': { type: 'number', label: 'Preis pro Credit (EUR)', step: 0.5 },
      'per_game.default_credits': { type: 'number', label: 'Standard-Credits', step: 1 },
    },
  },
  branding: {
    label: 'Branding',
    icon: Palette,
    fields: {
      cafe_name: { type: 'text', label: 'Standort-Name' },
      primary_color: { type: 'color', label: 'Primaerfarbe' },
    },
  },
  kiosk: {
    label: 'Kiosk-Verhalten',
    icon: Gamepad2,
    fields: {
      auto_lock_timeout_min: { type: 'number', label: 'Auto-Lock Timeout (min)', step: 1 },
      idle_timeout_min: { type: 'number', label: 'Idle Timeout (min)', step: 1 },
    },
  },
};

function getNestedValue(obj, path) {
  return path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : ''), obj || {});
}

function setNestedValue(obj, path, value) {
  const clone = JSON.parse(JSON.stringify(obj));
  const keys = path.split('.');
  let current = clone;
  for (let i = 0; i < keys.length - 1; i++) {
    if (!(keys[i] in current)) current[keys[i]] = {};
    current = current[keys[i]];
  }
  current[keys[keys.length - 1]] = value;
  return clone;
}

export default function PortalConfig() {
  const { apiBase, authHeaders, scope, isSuperadmin } = useCentralAuth();
  const [profiles, setProfiles] = useState([]);
  const [effective, setEffective] = useState(null);
  const [editScope, setEditScope] = useState('global');
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('pricing');
  const [showJson, setShowJson] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [profRes, effRes] = await Promise.all([
        axios.get(`${apiBase}/config/profiles`, { headers: authHeaders }),
        axios.get(`${apiBase}/config/effective`, {
          headers: authHeaders,
          params: {
            device_id: scope.deviceId || undefined,
            location_id: scope.locationId || undefined,
            customer_id: scope.customerId || undefined,
          },
        }),
      ]);
      setProfiles(profRes.data);
      setEffective(effRes.data);
    } catch (err) {
      console.error('Config fetch failed:', err);
    } finally {
      setLoading(false);
    }
  }, [apiBase, authHeaders, scope]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // When editScope changes, load the profile for that scope
  useEffect(() => {
    const scopeId = editScope === 'global' ? null
      : editScope === 'customer' ? scope.customerId
      : editScope === 'location' ? scope.locationId
      : scope.deviceId;

    const prof = profiles.find(p => p.scope_type === editScope && (editScope === 'global' ? !p.scope_id : p.scope_id === scopeId));
    setEditData(prof?.config_data || {});
  }, [editScope, profiles, scope]);

  const currentScopeId = editScope === 'global' ? 'global'
    : editScope === 'customer' ? scope.customerId
    : editScope === 'location' ? scope.locationId
    : scope.deviceId;

  const canEdit = editScope === 'global' ? isSuperadmin : !!currentScopeId;

  const handleFieldChange = (section, fieldPath, value) => {
    const fullPath = `${section}.${fieldPath}`;
    setEditData(prev => setNestedValue(prev, fullPath, value));
  };

  const handleSave = async () => {
    if (!canEdit) return;
    setSaving(true);
    try {
      await axios.put(
        `${apiBase}/config/profile/${editScope}/${currentScopeId}`,
        { config_data: editData },
        { headers: { ...authHeaders, 'Content-Type': 'application/json' } },
      );
      toast.success(`Config (${SCOPE_LABELS[editScope]}) gespeichert`);
      fetchData();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Speichern fehlgeschlagen');
    } finally {
      setSaving(false);
    }
  };

  const handleJsonSave = (jsonStr) => {
    try {
      const parsed = JSON.parse(jsonStr);
      setEditData(parsed);
      toast.success('JSON aktualisiert — bitte "Speichern" klicken');
    } catch {
      toast.error('Ungueltiges JSON');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div data-testid="portal-config-page">
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-semibold text-white">Konfiguration</h1>
          <p className="text-sm text-zinc-500">Hierarchisch: Global → Kunde → Standort → Geraet</p>
        </div>
        <div className="flex gap-2">
          <Button onClick={fetchData} variant="outline" className="border-zinc-700 text-zinc-400 hover:text-white" data-testid="config-refresh-btn">
            <RefreshCw className="w-4 h-4" />
          </Button>
          <Button onClick={handleSave} disabled={saving || !canEdit} className="bg-indigo-600 hover:bg-indigo-500" data-testid="config-save-btn">
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Speichere...' : 'Speichern'}
          </Button>
        </div>
      </div>

      {/* Scope Selector */}
      <div className="flex gap-1 mb-5 p-1 bg-zinc-900 rounded-lg border border-zinc-800 w-fit" data-testid="config-scope-tabs">
        {Object.entries(SCOPE_LABELS).map(([key, label]) => {
          const Icon = SCOPE_ICONS[key];
          const disabled = key !== 'global' && (
            (key === 'customer' && !scope.customerId) ||
            (key === 'location' && !scope.locationId) ||
            (key === 'device' && !scope.deviceId)
          );
          return (
            <button
              key={key}
              onClick={() => !disabled && setEditScope(key)}
              disabled={disabled}
              data-testid={`config-scope-${key}`}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors ${
                editScope === key
                  ? 'bg-indigo-500/10 text-indigo-400 font-medium'
                  : disabled
                    ? 'text-zinc-700 cursor-not-allowed'
                    : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              }`}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          );
        })}
      </div>

      {!canEdit && editScope !== 'global' && (
        <div className="flex items-center gap-2 p-3 mb-4 rounded-lg bg-amber-500/5 border border-amber-500/20 text-amber-400 text-sm" data-testid="config-scope-hint">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          Bitte waehlen Sie einen {SCOPE_LABELS[editScope]} ueber den Scope-Filter oben, um Overrides zu bearbeiten.
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Edit Form */}
        <div className="lg:col-span-2 space-y-4">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-0">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="w-full bg-zinc-950 border-b border-zinc-800 rounded-none p-1">
                  {Object.entries(CONFIG_SCHEMA).map(([key, section]) => {
                    const Icon = section.icon;
                    return (
                      <TabsTrigger
                        key={key}
                        value={key}
                        data-testid={`config-tab-${key}`}
                        className="data-[state=active]:bg-indigo-500/10 data-[state=active]:text-indigo-400 text-zinc-500 text-sm"
                      >
                        <Icon className="w-3.5 h-3.5 mr-1.5" />
                        {section.label}
                      </TabsTrigger>
                    );
                  })}
                  <TabsTrigger
                    value="json"
                    data-testid="config-tab-json"
                    className="data-[state=active]:bg-indigo-500/10 data-[state=active]:text-indigo-400 text-zinc-500 text-sm"
                  >
                    <Code className="w-3.5 h-3.5 mr-1.5" />
                    JSON
                  </TabsTrigger>
                </TabsList>

                {Object.entries(CONFIG_SCHEMA).map(([sectionKey, section]) => (
                  <TabsContent key={sectionKey} value={sectionKey} className="p-4 space-y-3">
                    <p className="text-xs text-zinc-600 mb-3">Override auf Ebene: <strong className="text-indigo-400">{SCOPE_LABELS[editScope]}</strong></p>
                    {Object.entries(section.fields).map(([fieldPath, field]) => {
                      const value = getNestedValue(editData[sectionKey], fieldPath);
                      const effectiveValue = effective ? getNestedValue(effective.config[sectionKey], fieldPath) : '';
                      return (
                        <div key={fieldPath} className="flex items-center gap-3">
                          <label className="w-48 text-sm text-zinc-400 flex-shrink-0">{field.label}</label>
                          {field.type === 'select' ? (
                            <select
                              value={value || ''}
                              onChange={(e) => handleFieldChange(sectionKey, fieldPath, e.target.value)}
                              disabled={!canEdit}
                              data-testid={`config-field-${sectionKey}-${fieldPath.replace('.', '-')}`}
                              className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-white text-sm focus:border-indigo-500 outline-none"
                            >
                              <option value="">— (von uebergeordneter Ebene)</option>
                              {field.options.map(opt => (
                                <option key={opt} value={opt}>{opt}</option>
                              ))}
                            </select>
                          ) : field.type === 'color' ? (
                            <div className="flex items-center gap-2 flex-1">
                              <input
                                type="color"
                                value={value || '#f59e0b'}
                                onChange={(e) => handleFieldChange(sectionKey, fieldPath, e.target.value)}
                                disabled={!canEdit}
                                className="w-10 h-8 rounded cursor-pointer"
                                data-testid={`config-field-${sectionKey}-${fieldPath.replace('.', '-')}`}
                              />
                              <input
                                type="text"
                                value={value || ''}
                                onChange={(e) => handleFieldChange(sectionKey, fieldPath, e.target.value)}
                                disabled={!canEdit}
                                className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-white text-sm font-mono"
                                data-testid={`config-field-${sectionKey}-${fieldPath.replace('.', '-')}-text`}
                              />
                            </div>
                          ) : (
                            <input
                              type={field.type}
                              value={value ?? ''}
                              onChange={(e) => handleFieldChange(sectionKey, fieldPath, field.type === 'number' ? parseFloat(e.target.value) || 0 : e.target.value)}
                              step={field.step}
                              disabled={!canEdit}
                              placeholder={`Effektiv: ${effectiveValue}`}
                              data-testid={`config-field-${sectionKey}-${fieldPath.replace('.', '-')}`}
                              className="flex-1 bg-zinc-800 border border-zinc-700 rounded px-3 py-2 text-white text-sm focus:border-indigo-500 outline-none placeholder:text-zinc-600"
                            />
                          )}
                        </div>
                      );
                    })}
                  </TabsContent>
                ))}

                <TabsContent value="json" className="p-4">
                  <p className="text-xs text-zinc-600 mb-3">
                    Rohe JSON-Config fuer Ebene <strong className="text-indigo-400">{SCOPE_LABELS[editScope]}</strong>.
                    Nur Overrides — leere Felder erben von uebergeordneter Ebene.
                  </p>
                  <textarea
                    value={JSON.stringify(editData, null, 2)}
                    onChange={(e) => {
                      try { setEditData(JSON.parse(e.target.value)); } catch {}
                    }}
                    disabled={!canEdit}
                    rows={16}
                    data-testid="config-json-editor"
                    className="w-full bg-zinc-950 border border-zinc-700 rounded-lg px-4 py-3 text-sm font-mono text-zinc-300 focus:border-indigo-500 outline-none resize-y"
                  />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>

        {/* Right: Effective Config + Layer Info */}
        <div className="space-y-4">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <Layers className="w-4 h-4" />
                Effektive Config (Zusammengefuehrt)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {effective && (
                <>
                  <div className="flex flex-wrap gap-1.5 mb-3">
                    {effective.layers_applied?.map(layer => (
                      <span key={layer} className="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 rounded text-xs font-medium">
                        {SCOPE_LABELS[layer] || layer}
                      </span>
                    ))}
                  </div>
                  <pre className="text-xs font-mono text-zinc-400 bg-zinc-950 rounded p-3 overflow-x-auto max-h-80 overflow-y-auto" data-testid="effective-config-display">
                    {JSON.stringify(effective.config, null, 2)}
                  </pre>
                  <p className="mt-2 text-[10px] text-zinc-600">Version: {effective.version}</p>
                </>
              )}
            </CardContent>
          </Card>

          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-zinc-400 flex items-center gap-2">
                <Settings className="w-4 h-4" />
                Alle Profile
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {profiles.map(p => {
                const Icon = SCOPE_ICONS[p.scope_type] || Globe;
                return (
                  <div key={p.id} className="flex items-center gap-2 p-2 rounded bg-zinc-800/50 text-sm">
                    <Icon className="w-3.5 h-3.5 text-zinc-500 flex-shrink-0" />
                    <span className="text-zinc-300 flex-1">{SCOPE_LABELS[p.scope_type]}</span>
                    <span className="text-xs text-zinc-600 font-mono">v{p.version}</span>
                  </div>
                );
              })}
              {profiles.length === 0 && <p className="text-xs text-zinc-600">Keine Profile vorhanden</p>}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
