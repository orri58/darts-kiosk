import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Save, RefreshCw, DollarSign, Palette, Paintbrush, Monitor,
  Type, Languages, Volume2, QrCode, Code, Layers, ChevronDown,
  Globe, Building2, MapPin, ToggleLeft, ToggleRight, Eye, History, Undo2
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { useCentralAuth } from '../../context/CentralAuthContext';

// ─── Helpers ────────────────────────────────────────────────
function getN(obj, path) {
  return path.split('.').reduce((o, k) => (o && o[k] !== undefined ? o[k] : undefined), obj || {});
}
function setN(obj, path, value) {
  const c = JSON.parse(JSON.stringify(obj || {}));
  const k = path.split('.');
  let cur = c;
  for (let i = 0; i < k.length - 1; i++) { if (!(k[i] in cur)) cur[k[i]] = {}; cur = cur[k[i]]; }
  cur[k[k.length - 1]] = value;
  return c;
}

// ─── Scope ──────────────────────────────────────────────────
const SCOPE_META = [
  { key: 'global', icon: Globe, label: 'Alle (Globale Vorgabe)' },
  { key: 'customer', icon: Building2, label: 'Fuer Kunde' },
  { key: 'location', icon: MapPin, label: 'Fuer Standort' },
  { key: 'device', icon: Monitor, label: 'Fuer Geraet' },
];

// ─── Field component ────────────────────────────────────────
function Field({ label, hint, children }) {
  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-1.5 sm:gap-4 py-3 border-b border-zinc-800/40 last:border-0">
      <div className="sm:w-52 flex-shrink-0">
        <p className="text-sm text-zinc-300">{label}</p>
        {hint && <p className="text-[11px] text-zinc-600 mt-0.5">{hint}</p>}
      </div>
      <div className="flex-1">{children}</div>
    </div>
  );
}

function TextInput({ value, onChange, placeholder, disabled, testId, mono }) {
  return (
    <input type="text" value={value ?? ''} onChange={e => onChange(e.target.value)}
      placeholder={placeholder} disabled={disabled} data-testid={testId}
      className={`w-full bg-zinc-900 border border-zinc-800 rounded-lg px-3.5 py-2 text-sm text-white placeholder:text-zinc-700 focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 outline-none transition-colors disabled:opacity-40 ${mono ? 'font-mono' : ''}`} />
  );
}

function NumberInput({ value, onChange, step, min, max, disabled, testId, suffix }) {
  return (
    <div className="flex items-center gap-2">
      <input type="number" value={value ?? ''} onChange={e => onChange(parseFloat(e.target.value) || 0)}
        step={step} min={min} max={max} disabled={disabled} data-testid={testId}
        className="w-32 bg-zinc-900 border border-zinc-800 rounded-lg px-3.5 py-2 text-sm text-white font-mono focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 outline-none transition-colors disabled:opacity-40" />
      {suffix && <span className="text-xs text-zinc-600">{suffix}</span>}
    </div>
  );
}

function SelectInput({ value, onChange, options, disabled, testId }) {
  return (
    <select value={value ?? ''} onChange={e => onChange(e.target.value)} disabled={disabled} data-testid={testId}
      className="bg-zinc-900 border border-zinc-800 rounded-lg px-3.5 py-2 text-sm text-white focus:border-indigo-500/50 outline-none transition-colors disabled:opacity-40 cursor-pointer">
      {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

function ColorInput({ value, onChange, disabled, testId }) {
  return (
    <div className="flex items-center gap-3">
      <div className="relative">
        <input type="color" value={value || '#f59e0b'} onChange={e => onChange(e.target.value)}
          disabled={disabled} data-testid={testId}
          className="w-10 h-10 rounded-lg cursor-pointer border-2 border-zinc-700 bg-transparent" />
      </div>
      <input type="text" value={value || ''} onChange={e => onChange(e.target.value)}
        disabled={disabled}
        className="w-28 bg-zinc-900 border border-zinc-800 rounded-lg px-3 py-2 text-sm text-white font-mono focus:border-indigo-500/50 outline-none" />
      {value && <div className="w-20 h-8 rounded-md border border-zinc-700" style={{ backgroundColor: value }} />}
    </div>
  );
}

function ToggleSwitch({ value, onChange, disabled, testId, labelOn, labelOff }) {
  return (
    <button onClick={() => !disabled && onChange(!value)} disabled={disabled} data-testid={testId}
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-sm transition-colors ${
        value ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' : 'bg-zinc-900 border-zinc-800 text-zinc-500'
      } disabled:opacity-40`}>
      {value ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}
      {value ? (labelOn || 'An') : (labelOff || 'Aus')}
    </button>
  );
}

// ─── Tab definitions ────────────────────────────────────────
const TABS = [
  { key: 'pricing', label: 'Preise', icon: DollarSign },
  { key: 'branding', label: 'Branding', icon: Palette },
  { key: 'colors', label: 'Farben', icon: Paintbrush },
  { key: 'kiosk', label: 'Kiosk', icon: Monitor },
  { key: 'texts', label: 'Texte', icon: Type },
  { key: 'language', label: 'Sprache', icon: Languages },
  { key: 'sound', label: 'Sound', icon: Volume2 },
  { key: 'sharing', label: 'QR / Sharing', icon: QrCode },
];

// ─── Tab Content Renderers ──────────────────────────────────
function PricingTab({ data, set, disabled }) {
  const mode = getN(data, 'pricing.mode') || 'per_game';
  return (
    <div data-testid="config-section-pricing">
      <Field label="Preismodell" hint="Wie wird abgerechnet?">
        <SelectInput value={mode} onChange={v => set('pricing.mode', v)} disabled={disabled} testId="cfg-pricing-mode"
          options={[
            { value: 'per_game', label: 'Pro Spiel' },
            { value: 'per_time', label: 'Pro Zeit' },
            { value: 'per_credit', label: 'Pro Credit' },
          ]} />
      </Field>
      <Field label="Preis pro Credit" hint="Einzelpreis in EUR">
        <NumberInput value={getN(data, 'pricing.per_game.price_per_credit')} onChange={v => set('pricing.per_game.price_per_credit', v)}
          step={0.5} min={0} disabled={disabled} testId="cfg-pricing-price" suffix="EUR" />
      </Field>
      <Field label="Standard-Credits" hint="Anzahl Credits beim Start">
        <NumberInput value={getN(data, 'pricing.per_game.default_credits')} onChange={v => set('pricing.per_game.default_credits', v)}
          step={1} min={1} disabled={disabled} testId="cfg-pricing-credits" />
      </Field>
      <Field label="Mindestbetrag" hint="Minimaler Einwurf">
        <NumberInput value={getN(data, 'pricing.min_amount')} onChange={v => set('pricing.min_amount', v)}
          step={0.5} min={0} disabled={disabled} testId="cfg-pricing-min" suffix="EUR" />
      </Field>
    </div>
  );
}

function BrandingTab({ data, set, disabled }) {
  return (
    <div data-testid="config-section-branding">
      <Field label="Name" hint="Name des Standorts / Geschaefts">
        <TextInput value={getN(data, 'branding.cafe_name')} onChange={v => set('branding.cafe_name', v)}
          placeholder="z.B. DartZone Berlin" disabled={disabled} testId="cfg-branding-name" />
      </Field>
      <Field label="Untertitel" hint="Wird unter dem Namen angezeigt">
        <TextInput value={getN(data, 'branding.subtitle')} onChange={v => set('branding.subtitle', v)}
          placeholder="z.B. Dein Dart-Erlebnis" disabled={disabled} testId="cfg-branding-subtitle" />
      </Field>
      <Field label="Logo URL" hint="URL zum Logo (PNG/SVG empfohlen)">
        <TextInput value={getN(data, 'branding.logo_url')} onChange={v => set('branding.logo_url', v)}
          placeholder="https://..." disabled={disabled} testId="cfg-branding-logo" />
      </Field>
    </div>
  );
}

function ColorsTab({ data, set, disabled }) {
  const primary = getN(data, 'branding.primary_color') || '#f59e0b';
  const secondary = getN(data, 'branding.secondary_color') || '#6366f1';
  const accent = getN(data, 'branding.accent_color') || '#10b981';
  return (
    <div data-testid="config-section-colors">
      <Field label="Primaerfarbe" hint="Hauptfarbe fuer Buttons und Akzente">
        <ColorInput value={primary} onChange={v => set('branding.primary_color', v)} disabled={disabled} testId="cfg-color-primary" />
      </Field>
      <Field label="Sekundaerfarbe" hint="Hintergruende, Navigation">
        <ColorInput value={secondary} onChange={v => set('branding.secondary_color', v)} disabled={disabled} testId="cfg-color-secondary" />
      </Field>
      <Field label="Akzentfarbe" hint="Erfolg, Bestaetigungen">
        <ColorInput value={accent} onChange={v => set('branding.accent_color', v)} disabled={disabled} testId="cfg-color-accent" />
      </Field>
      {/* Preview */}
      <div className="mt-4 p-4 rounded-xl border border-zinc-800 bg-zinc-950">
        <p className="text-xs text-zinc-600 mb-3">Vorschau</p>
        <div className="flex items-center gap-3">
          <div className="h-10 px-5 rounded-lg flex items-center text-sm font-medium text-white" style={{ backgroundColor: primary }}>Primaer</div>
          <div className="h-10 px-5 rounded-lg flex items-center text-sm font-medium text-white" style={{ backgroundColor: secondary }}>Sekundaer</div>
          <div className="h-10 px-5 rounded-lg flex items-center text-sm font-medium text-white" style={{ backgroundColor: accent }}>Akzent</div>
        </div>
      </div>
    </div>
  );
}

function KioskTab({ data, set, disabled }) {
  return (
    <div data-testid="config-section-kiosk">
      <Field label="Auto-Lock" hint="Bildschirm automatisch sperren nach Inaktivitaet">
        <NumberInput value={getN(data, 'kiosk.auto_lock_timeout_min')} onChange={v => set('kiosk.auto_lock_timeout_min', v)}
          step={1} min={1} disabled={disabled} testId="cfg-kiosk-autolock" suffix="Minuten" />
      </Field>
      <Field label="Idle Timeout" hint="Session beenden nach Inaktivitaet">
        <NumberInput value={getN(data, 'kiosk.idle_timeout_min')} onChange={v => set('kiosk.idle_timeout_min', v)}
          step={1} min={1} disabled={disabled} testId="cfg-kiosk-idle" suffix="Minuten" />
      </Field>
      <Field label="Auto-Start" hint="Spiel automatisch starten nach Freigabe">
        <ToggleSwitch value={!!getN(data, 'kiosk.auto_start')} onChange={v => set('kiosk.auto_start', v)}
          disabled={disabled} testId="cfg-kiosk-autostart" />
      </Field>
      <Field label="Vollbild-Modus" hint="Browser im Vollbild starten">
        <ToggleSwitch value={!!getN(data, 'kiosk.fullscreen')} onChange={v => set('kiosk.fullscreen', v)}
          disabled={disabled} testId="cfg-kiosk-fullscreen" />
      </Field>
    </div>
  );
}

function TextsTab({ data, set, disabled }) {
  return (
    <div data-testid="config-section-texts">
      <Field label="Willkommen Titel" hint="Haupttext auf dem Sperrbildschirm">
        <TextInput value={getN(data, 'texts.welcome_title')} onChange={v => set('texts.welcome_title', v)}
          placeholder="Willkommen!" disabled={disabled} testId="cfg-texts-welcome" />
      </Field>
      <Field label="Willkommen Untertitel" hint="Zusatztext unter dem Titel">
        <TextInput value={getN(data, 'texts.welcome_subtitle')} onChange={v => set('texts.welcome_subtitle', v)}
          placeholder="Frage an der Theke nach einer Freigabe" disabled={disabled} testId="cfg-texts-welcome-sub" />
      </Field>
      <Field label="Gesperrt Nachricht" hint="Text wenn Board gesperrt ist">
        <TextInput value={getN(data, 'texts.locked_message')} onChange={v => set('texts.locked_message', v)}
          placeholder="Board gesperrt" disabled={disabled} testId="cfg-texts-locked" />
      </Field>
      <Field label="Game-Over Text" hint="Text nach Spielende">
        <TextInput value={getN(data, 'texts.game_over')} onChange={v => set('texts.game_over', v)}
          placeholder="Spiel beendet!" disabled={disabled} testId="cfg-texts-gameover" />
      </Field>
    </div>
  );
}

function LanguageTab({ data, set, disabled }) {
  return (
    <div data-testid="config-section-language">
      <Field label="Standard-Sprache" hint="Sprache beim Start">
        <SelectInput value={getN(data, 'language.default') || 'de'} onChange={v => set('language.default', v)} disabled={disabled} testId="cfg-lang-default"
          options={[{ value: 'de', label: 'Deutsch' }, { value: 'en', label: 'English' }]} />
      </Field>
      <Field label="Sprachwechsel erlauben" hint="Nutzer kann Sprache im Kiosk wechseln">
        <ToggleSwitch value={getN(data, 'language.allow_switch') !== false} onChange={v => set('language.allow_switch', v)}
          disabled={disabled} testId="cfg-lang-switch" />
      </Field>
    </div>
  );
}

function SoundTab({ data, set, disabled }) {
  return (
    <div data-testid="config-section-sound">
      <Field label="Sound aktiviert" hint="Soundeffekte fuer Spiel-Events">
        <ToggleSwitch value={getN(data, 'sound.enabled') !== false} onChange={v => set('sound.enabled', v)}
          disabled={disabled} testId="cfg-sound-enabled" />
      </Field>
      <Field label="Lautstaerke" hint="0 = stumm, 100 = voll">
        <div className="flex items-center gap-3">
          <input type="range" min={0} max={100} value={getN(data, 'sound.volume') ?? 70}
            onChange={e => set('sound.volume', parseInt(e.target.value))} disabled={disabled}
            data-testid="cfg-sound-volume"
            className="flex-1 accent-indigo-500" />
          <span className="text-sm text-zinc-400 font-mono w-8 text-right">{getN(data, 'sound.volume') ?? 70}</span>
        </div>
      </Field>
      <Field label="Ruhezeiten Start" hint="Ab wann kein Sound (z.B. 22:00)">
        <TextInput value={getN(data, 'sound.quiet_hours_start')} onChange={v => set('sound.quiet_hours_start', v)}
          placeholder="22:00" disabled={disabled} testId="cfg-sound-quiet-start" mono />
      </Field>
      <Field label="Ruhezeiten Ende" hint="">
        <TextInput value={getN(data, 'sound.quiet_hours_end')} onChange={v => set('sound.quiet_hours_end', v)}
          placeholder="08:00" disabled={disabled} testId="cfg-sound-quiet-end" mono />
      </Field>
    </div>
  );
}

function SharingTab({ data, set, disabled }) {
  return (
    <div data-testid="config-section-sharing">
      <Field label="QR-Code anzeigen" hint="QR-Code nach Spielende fuer Ergebnisse">
        <ToggleSwitch value={getN(data, 'sharing.qr_enabled') !== false} onChange={v => set('sharing.qr_enabled', v)}
          disabled={disabled} testId="cfg-sharing-qr" />
      </Field>
      <Field label="Oeffentliche Ergebnisse" hint="Match-Ergebnisse per Link teilbar">
        <ToggleSwitch value={getN(data, 'sharing.public_results') !== false} onChange={v => set('sharing.public_results', v)}
          disabled={disabled} testId="cfg-sharing-results" />
      </Field>
      <Field label="Oeffentliches Leaderboard" hint="Bestenliste oeffentlich zugaenglich">
        <ToggleSwitch value={!!getN(data, 'sharing.leaderboard_public')} onChange={v => set('sharing.leaderboard_public', v)}
          disabled={disabled} testId="cfg-sharing-leaderboard" />
      </Field>
    </div>
  );
}

const TAB_RENDERERS = {
  pricing: PricingTab, branding: BrandingTab, colors: ColorsTab, kiosk: KioskTab,
  texts: TextsTab, language: LanguageTab, sound: SoundTab, sharing: SharingTab,
};

// ─── Effective Config (pretty) ──────────────────────────────
function EffectiveSummary({ config }) {
  if (!config) return null;
  const c = config;
  const sections = [
    { label: 'Preise', items: [
      { k: 'Modell', v: c.pricing?.mode === 'per_game' ? 'Pro Spiel' : c.pricing?.mode === 'per_time' ? 'Pro Zeit' : c.pricing?.mode || '—' },
      { k: 'Preis/Credit', v: c.pricing?.per_game?.price_per_credit != null ? `${c.pricing.per_game.price_per_credit} EUR` : '—' },
      { k: 'Credits', v: c.pricing?.per_game?.default_credits ?? '—' },
    ]},
    { label: 'Branding', items: [
      { k: 'Name', v: c.branding?.cafe_name || '—' },
      { k: 'Untertitel', v: c.branding?.subtitle || '—' },
    ]},
    { label: 'Farben', items: [
      { k: 'Primaer', v: c.branding?.primary_color, color: true },
      { k: 'Sekundaer', v: c.branding?.secondary_color, color: true },
    ]},
    { label: 'Kiosk', items: [
      { k: 'Auto-Lock', v: c.kiosk?.auto_lock_timeout_min != null ? `${c.kiosk.auto_lock_timeout_min} min` : '—' },
      { k: 'Idle Timeout', v: c.kiosk?.idle_timeout_min != null ? `${c.kiosk.idle_timeout_min} min` : '—' },
    ]},
    { label: 'Sound', items: [
      { k: 'Aktiviert', v: c.sound?.enabled !== false ? 'Ja' : 'Nein' },
      { k: 'Lautstaerke', v: c.sound?.volume != null ? `${c.sound.volume}%` : '—' },
    ]},
    { label: 'Sprache', items: [
      { k: 'Standard', v: c.language?.default === 'en' ? 'English' : 'Deutsch' },
    ]},
  ].filter(s => s.items.some(i => i.v && i.v !== '—'));

  return (
    <div className="space-y-3" data-testid="effective-summary">
      {sections.map(s => (
        <div key={s.label}>
          <p className="text-[10px] text-zinc-600 uppercase tracking-wider mb-1.5">{s.label}</p>
          {s.items.map(i => (
            <div key={i.k} className="flex items-center justify-between py-1">
              <span className="text-xs text-zinc-500">{i.k}</span>
              {i.color && i.v ? (
                <div className="flex items-center gap-2">
                  <div className="w-4 h-4 rounded-sm border border-zinc-700" style={{ backgroundColor: i.v }} />
                  <span className="text-xs text-zinc-300 font-mono">{i.v}</span>
                </div>
              ) : (
                <span className="text-xs text-zinc-300">{i.v}</span>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════
export default function PortalConfig() {
  const { apiBase, authHeaders, scope, isSuperadmin } = useCentralAuth();
  const [profiles, setProfiles] = useState([]);
  const [effective, setEffective] = useState(null);
  const [editScope, setEditScope] = useState('global');
  const [editData, setEditData] = useState({});
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('pricing');
  const [advancedMode, setAdvancedMode] = useState(false);
  const [scopeOpen, setScopeOpen] = useState(false);
  const [history, setHistory] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [rollbackTarget, setRollbackTarget] = useState(null); // version to confirm
  const [rollbackLoading, setRollbackLoading] = useState(false);

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

  const currentScopeId = editScope === 'global' ? 'global'
    : editScope === 'customer' ? scope.customerId
    : editScope === 'location' ? scope.locationId
    : scope.deviceId;

  const canEdit = editScope === 'global' ? isSuperadmin : !!currentScopeId;

  const fetchHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      const sid = editScope === 'global' ? 'global' : currentScopeId;
      const res = await axios.get(`${apiBase}/config/history/${editScope}/${sid}`, { headers: authHeaders });
      setHistory(res.data);
    } catch {
      setHistory(null);
    } finally {
      setHistoryLoading(false);
    }
  }, [apiBase, authHeaders, editScope, currentScopeId]);

  const handleRollback = async (version) => {
    setRollbackLoading(true);
    try {
      const sid = editScope === 'global' ? 'global' : currentScopeId;
      await axios.post(`${apiBase}/config/rollback/${editScope}/${sid}/${version}`, {}, {
        headers: { ...authHeaders, 'Content-Type': 'application/json' },
      });
      toast.success(`Rollback auf Version ${version} erfolgreich`);
      setRollbackTarget(null);
      fetchData();
      fetchHistory();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Rollback fehlgeschlagen');
    } finally {
      setRollbackLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, [fetchData]);
  useEffect(() => { if (advancedMode) fetchHistory(); }, [advancedMode, fetchHistory]);

  useEffect(() => {
    const scopeId = editScope === 'global' ? null
      : editScope === 'customer' ? scope.customerId
      : editScope === 'location' ? scope.locationId
      : scope.deviceId;
    const prof = profiles.find(p => p.scope_type === editScope && (editScope === 'global' ? !p.scope_id : p.scope_id === scopeId));
    setEditData(prof?.config_data || {});
  }, [editScope, profiles, scope]);

  const handleSet = (path, value) => {
    setEditData(prev => setN(prev, path, value));
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
      toast.success('Einstellungen gespeichert');
      fetchData();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (detail && typeof detail === 'object' && detail.validation_errors) {
        // Schema validation errors — show each one
        detail.validation_errors.forEach(e => toast.error(e, { duration: 6000 }));
      } else {
        toast.error(typeof detail === 'string' ? detail : 'Speichern fehlgeschlagen');
      }
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const CurrentTabRenderer = TAB_RENDERERS[activeTab];
  const activeScopeMeta = SCOPE_META.find(s => s.key === editScope);

  return (
    <div data-testid="portal-config-page">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-semibold text-white">Einstellungen</h1>
          <p className="text-sm text-zinc-500">
            {editScope === 'global' ? 'Globale Vorgaben fuer alle Geraete' :
             editScope === 'customer' ? 'Einstellungen fuer diesen Kunden' :
             editScope === 'location' ? 'Einstellungen fuer diesen Standort' :
             'Einstellungen fuer dieses Geraet'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Advanced Mode Toggle */}
          <button
            onClick={() => setAdvancedMode(!advancedMode)}
            data-testid="config-advanced-toggle"
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs transition-colors ${
              advancedMode
                ? 'bg-indigo-500/10 border-indigo-500/30 text-indigo-400'
                : 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:text-zinc-300'
            }`}
          >
            <Code className="w-3.5 h-3.5" />
            Erweiterter Modus
          </button>
          <Button onClick={fetchData} variant="outline" className="border-zinc-700 text-zinc-400 hover:text-white" data-testid="config-refresh-btn">
            <RefreshCw className="w-4 h-4" />
          </Button>
          <Button onClick={handleSave} disabled={saving || !canEdit} className="bg-indigo-600 hover:bg-indigo-500" data-testid="config-save-btn">
            <Save className="w-4 h-4 mr-2" />
            {saving ? 'Speichere...' : 'Speichern'}
          </Button>
        </div>
      </div>

      {/* Scope Selector — clean dropdown style */}
      <div className="relative mb-5" data-testid="config-scope-selector">
        <button
          onClick={() => setScopeOpen(!scopeOpen)}
          className="flex items-center gap-2.5 px-4 py-2.5 bg-zinc-900 border border-zinc-800 rounded-lg text-sm text-white hover:border-zinc-700 transition-colors w-full sm:w-auto"
          data-testid="config-scope-trigger"
        >
          {activeScopeMeta && <activeScopeMeta.icon className="w-4 h-4 text-indigo-400" />}
          <span>Einstellungen fuer: <strong>{activeScopeMeta?.label}</strong></span>
          <ChevronDown className={`w-4 h-4 text-zinc-500 ml-auto transition-transform ${scopeOpen ? 'rotate-180' : ''}`} />
        </button>
        {scopeOpen && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setScopeOpen(false)} />
            <div className="absolute top-full mt-1 left-0 bg-zinc-900 border border-zinc-800 rounded-lg shadow-xl z-20 py-1 min-w-[260px]">
              {SCOPE_META.map(s => {
                const disabled = s.key !== 'global' && (
                  (s.key === 'customer' && !scope.customerId) ||
                  (s.key === 'location' && !scope.locationId) ||
                  (s.key === 'device' && !scope.deviceId)
                );
                return (
                  <button key={s.key}
                    onClick={() => { if (!disabled) { setEditScope(s.key); setScopeOpen(false); } }}
                    disabled={disabled}
                    data-testid={`config-scope-${s.key}`}
                    className={`flex items-center gap-2.5 px-4 py-2.5 w-full text-left text-sm transition-colors ${
                      editScope === s.key ? 'bg-indigo-500/10 text-indigo-400' :
                      disabled ? 'text-zinc-700 cursor-not-allowed' : 'text-zinc-300 hover:bg-zinc-800'
                    }`}
                  >
                    <s.icon className="w-4 h-4 flex-shrink-0" />
                    <span>{s.label}</span>
                    {disabled && <span className="text-[10px] text-zinc-700 ml-auto">Scope waehlen</span>}
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Form */}
        <div className="lg:col-span-2">
          <Card className="bg-zinc-900 border-zinc-800 overflow-hidden">
            {/* Tab Bar */}
            <div className="flex overflow-x-auto border-b border-zinc-800 bg-zinc-950/50" data-testid="config-tabs">
              {TABS.map(tab => {
                const Icon = tab.icon;
                const active = activeTab === tab.key;
                return (
                  <button key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    data-testid={`config-tab-${tab.key}`}
                    className={`flex items-center gap-1.5 px-4 py-3 text-sm whitespace-nowrap border-b-2 transition-colors flex-shrink-0 ${
                      active
                        ? 'border-indigo-500 text-indigo-400 bg-indigo-500/5'
                        : 'border-transparent text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/30'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Tab Content */}
            <CardContent className="p-5">
              {CurrentTabRenderer && <CurrentTabRenderer data={editData} set={handleSet} disabled={!canEdit} />}
            </CardContent>
          </Card>

          {/* Advanced: JSON Editor */}
          {advancedMode && (
            <Card className="bg-zinc-900 border-zinc-800 mt-4" data-testid="config-advanced-section">
              <CardContent className="p-5">
                <div className="flex items-center gap-2 mb-3">
                  <Code className="w-4 h-4 text-indigo-400" />
                  <p className="text-sm text-zinc-400 font-medium">JSON Editor — Override auf Ebene: <span className="text-indigo-400">{activeScopeMeta?.label}</span></p>
                </div>
                <textarea
                  value={JSON.stringify(editData, null, 2)}
                  onChange={(e) => { try { setEditData(JSON.parse(e.target.value)); } catch {} }}
                  disabled={!canEdit}
                  rows={14}
                  data-testid="config-json-editor"
                  className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-4 py-3 text-xs font-mono text-zinc-400 focus:border-indigo-500/50 outline-none resize-y"
                />
                {/* Layer Badges */}
                {effective && (
                  <div className="flex items-center gap-2 mt-3">
                    <Layers className="w-3.5 h-3.5 text-zinc-600" />
                    <span className="text-[10px] text-zinc-600">Aktive Layer:</span>
                    {effective.layers_applied?.map(l => (
                      <span key={l} className="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 rounded text-[10px] font-medium">
                        {SCOPE_META.find(s => s.key === l)?.label || l}
                      </span>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right: Effective Config Summary */}
        <div className="space-y-4">
          <Card className="bg-zinc-900 border-zinc-800">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Eye className="w-4 h-4 text-zinc-500" />
                <p className="text-sm text-zinc-400 font-medium">Aktive Einstellungen</p>
              </div>
              {effective && (
                <>
                  {/* Layer badges */}
                  <div className="flex flex-wrap gap-1.5 mb-3 pb-3 border-b border-zinc-800">
                    {effective.layers_applied?.map(l => (
                      <span key={l} className="px-2 py-0.5 bg-indigo-500/10 text-indigo-400 rounded text-[10px] font-medium">
                        {SCOPE_META.find(s => s.key === l)?.label || l}
                      </span>
                    ))}
                    <span className="text-[10px] text-zinc-600 self-center ml-1">v{effective.version}</span>
                  </div>
                  <EffectiveSummary config={effective.config} />

                  {advancedMode && (
                    <details className="mt-4">
                      <summary className="text-[10px] text-zinc-600 cursor-pointer hover:text-zinc-400">Raw JSON</summary>
                      <pre className="text-[10px] font-mono text-zinc-500 bg-zinc-950 rounded p-2 mt-2 overflow-auto max-h-40" data-testid="effective-config-display">
                        {JSON.stringify(effective.config, null, 2)}
                      </pre>
                    </details>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* Profile List — only in advanced mode */}
          {advancedMode && profiles.length > 0 && (
            <Card className="bg-zinc-900 border-zinc-800">
              <CardContent className="p-4">
                <p className="text-xs text-zinc-500 mb-2 font-medium">Config-Profile ({profiles.length})</p>
                <div className="space-y-1.5">
                  {profiles.map(p => {
                    const meta = SCOPE_META.find(s => s.key === p.scope_type);
                    const Icon = meta?.icon || Globe;
                    return (
                      <div key={p.id} className="flex items-center gap-2 py-1.5">
                        <Icon className="w-3.5 h-3.5 text-zinc-600 flex-shrink-0" />
                        <span className="text-xs text-zinc-400 flex-1">{meta?.label || p.scope_type}</span>
                        <span className="text-[10px] text-zinc-600 font-mono">v{p.version}</span>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Config History & Rollback — in advanced mode */}
          {advancedMode && history && (
            <Card className="bg-zinc-900 border-zinc-800" data-testid="config-history-card">
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <History className="w-4 h-4 text-zinc-500" />
                    <p className="text-xs text-zinc-400 font-medium">Versions-Historie</p>
                  </div>
                  <button onClick={fetchHistory} className="text-zinc-600 hover:text-zinc-400" data-testid="history-refresh-btn">
                    <RefreshCw className="w-3.5 h-3.5" />
                  </button>
                </div>

                {/* Active version */}
                {history.active_version && (
                  <div className="flex items-center gap-2 py-2 mb-2 border-b border-zinc-800">
                    <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 rounded text-[10px] font-medium border border-emerald-500/20">AKTIV</span>
                    <span className="text-xs text-white font-mono">v{history.active_version}</span>
                    <span className="text-[10px] text-zinc-600 ml-auto">{history.active_updated_by}</span>
                  </div>
                )}

                {history.history?.length > 0 ? (
                  <div className="space-y-1 max-h-[300px] overflow-y-auto">
                    {history.history.map(h => (
                      <div key={h.id} className="flex items-center gap-2 py-1.5 border-b border-zinc-800/30 last:border-0" data-testid={`history-entry-v${h.version}`}>
                        <span className="text-xs text-zinc-400 font-mono w-8">v{h.version}</span>
                        <span className="text-[10px] text-zinc-600 flex-1 truncate">{h.updated_by || '—'}</span>
                        <span className="text-[10px] text-zinc-600">
                          {h.saved_at ? new Date(h.saved_at).toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : ''}
                        </span>
                        {h.version !== history.active_version && (
                          rollbackTarget === h.version ? (
                            <div className="flex items-center gap-1">
                              <button onClick={() => handleRollback(h.version)} disabled={rollbackLoading}
                                className="px-2 py-0.5 bg-amber-500/10 text-amber-400 rounded text-[10px] font-medium hover:bg-amber-500/20 disabled:opacity-50"
                                data-testid={`rollback-confirm-v${h.version}`}>
                                {rollbackLoading ? '...' : 'Ja'}
                              </button>
                              <button onClick={() => setRollbackTarget(null)}
                                className="px-2 py-0.5 text-zinc-600 rounded text-[10px] hover:text-zinc-400">
                                Nein
                              </button>
                            </div>
                          ) : (
                            <button onClick={() => setRollbackTarget(h.version)}
                              className="text-zinc-600 hover:text-amber-400 transition-colors"
                              title="Auf diese Version zuruecksetzen"
                              data-testid={`rollback-btn-v${h.version}`}>
                              <Undo2 className="w-3.5 h-3.5" />
                            </button>
                          )
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-[10px] text-zinc-600">Keine frueheren Versionen vorhanden</p>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
