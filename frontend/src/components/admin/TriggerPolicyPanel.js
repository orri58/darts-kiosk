import { useMemo, useState } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Lock,
  RadioTower,
  ShieldCheck,
  ShieldAlert,
  Siren,
  Sparkles,
} from 'lucide-react';
import { Button } from '../ui/button';
import { Switch } from '../ui/switch';
import { AdminSection, AdminStatusPill } from './AdminShell';
import { cn } from '../../lib/utils';

const GROUP_META = {
  authoritative_start: {
    title: 'Startsignale',
    description: 'Mindestens ein verlässliches Match-Startsignal muss aktiv bleiben.',
    tone: 'emerald',
    roleLabel: 'Authoritative',
  },
  authoritative_finish: {
    title: 'Finishsignale',
    description: 'Bestätigte Match-Enden. Diese dürfen Billing und Session-Abschluss auslösen.',
    tone: 'emerald',
    roleLabel: 'Authoritative',
  },
  authoritative_abort: {
    title: 'Abbruchsignale',
    description: 'Nur qualifizierte Delete-Events dürfen als echter Match-Abbruch gelten.',
    tone: 'amber',
    roleLabel: 'Authoritative',
  },
  assistive_finish: {
    title: 'Assistive Hinweise',
    description: 'Nur als Hinweis nutzen. Diese Signale dürfen keine Credits abbuchen.',
    tone: 'blue',
    roleLabel: 'Assistive',
  },
  diagnostic_interpretations: {
    title: 'Diagnostik',
    description: 'Hilft beim Debugging und bei Support-Fällen. Keine Billing-Wirkung.',
    tone: 'neutral',
    roleLabel: 'Diagnostic',
  },
};

function normalizeList(value) {
  return Array.isArray(value) ? [...value].sort() : [];
}

function sameList(a = [], b = []) {
  return normalizeList(a).join('|') === normalizeList(b).join('|');
}

function SignalToggleCard({ signal, checked, onToggle }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={cn(
        'rounded-2xl border p-4 text-left transition',
        checked
          ? 'border-amber-500/40 bg-amber-500/10 shadow-[0_12px_36px_rgba(245,158,11,0.12)]'
          : 'border-zinc-800 bg-zinc-900/70 hover:border-zinc-700 hover:bg-zinc-900'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium text-white">{signal.label}</p>
            <AdminStatusPill tone={signal.role === 'authoritative' ? 'emerald' : signal.role === 'assistive' ? 'blue' : 'neutral'}>
              {signal.role}
            </AdminStatusPill>
          </div>
          <p className="mt-2 text-sm leading-6 text-zinc-400">{signal.description}</p>
          <div className="mt-3 flex flex-wrap gap-2 text-[11px] uppercase tracking-[0.2em] text-zinc-500">
            <span className="rounded-full border border-zinc-800 px-2 py-1">{signal.source}</span>
            <span className="rounded-full border border-zinc-800 px-2 py-1 font-mono tracking-[0.12em] lowercase text-zinc-400">
              {signal.interpretation}
            </span>
          </div>
        </div>
        <div className={cn('mt-1 flex h-6 w-6 items-center justify-center rounded-full border', checked ? 'border-amber-500 bg-amber-500 text-black' : 'border-zinc-700 text-zinc-700')}>
          <CheckCircle2 className="h-4 w-4" />
        </div>
      </div>
    </button>
  );
}

export default function TriggerPolicyPanel({ policy, metadata, loading, saving, onChange, onSave }) {
  const [advancedUnlocked, setAdvancedUnlocked] = useState(false);

  const presets = useMemo(() => metadata?.presets || [], [metadata]);
  const catalog = useMemo(() => metadata?.signal_catalog || [], [metadata]);
  const lockedFields = metadata?.locked_fields || {};

  const currentPresetId = useMemo(() => {
    const match = presets.find((preset) => {
      const config = preset.config || {};
      return [
        'authoritative_start',
        'authoritative_finish',
        'authoritative_abort',
        'assistive_finish',
        'diagnostic_interpretations',
      ].every((key) => sameList(policy?.[key], config?.[key]))
        && Boolean(policy?.require_prior_active_for_finish) === Boolean(config?.require_prior_active_for_finish)
        && Boolean(policy?.require_prior_active_for_abort) === Boolean(config?.require_prior_active_for_abort)
        && Boolean(policy?.allow_console_finish_authority) === Boolean(config?.allow_console_finish_authority)
        && Boolean(policy?.allow_dom_finish_authority) === Boolean(config?.allow_dom_finish_authority);
    });

    return match?.id || null;
  }, [policy, presets]);

  const groupedSignals = useMemo(() => {
    return Object.keys(GROUP_META).reduce((acc, key) => {
      acc[key] = catalog.filter((item) => item.group === key);
      return acc;
    }, {});
  }, [catalog]);

  const toggleSignal = (groupKey, interpretation) => {
    const current = Array.isArray(policy?.[groupKey]) ? policy[groupKey] : [];
    const next = current.includes(interpretation)
      ? current.filter((item) => item !== interpretation)
      : [...current, interpretation];

    onChange({
      ...policy,
      [groupKey]: next,
    });
  };

  const applyPreset = (preset) => {
    onChange({
      ...policy,
      version: 1,
      ...preset.config,
    });
  };

  const updateFlag = (key, value) => {
    onChange({
      ...policy,
      [key]: value,
    });
  };

  if (loading || !policy) {
    return (
      <AdminSection title="Trigger-Policy" description="Lädt aktuelle Observer-Konfiguration…">
        <div className="flex min-h-[220px] items-center justify-center text-zinc-500">
          <RadioTower className="mr-3 h-5 w-5 animate-pulse text-amber-500" />
          Observer-Konfiguration wird geladen…
        </div>
      </AdminSection>
    );
  }

  return (
    <div className="space-y-6" data-testid="trigger-policy-panel">
      <AdminSection
        title="Observer-Trigger-Policy"
        description="Lokale Trigger steuern, welche Autodarts-Signale eine Session starten, abschließen oder nur diagnostisch markieren dürfen. Die UI bleibt absichtlich eingeschränkt: keine freien Channel-Regexe, kein Roh-JSON."
        actions={
          <Button
            type="button"
            onClick={onSave}
            disabled={saving}
            className="bg-amber-500 text-black hover:bg-amber-400"
            data-testid="save-trigger-policy-btn"
          >
            <ShieldCheck className="mr-2 h-4 w-4" />
            {saving ? 'Speichert…' : 'Trigger speichern'}
          </Button>
        }
      >
        <div className="grid gap-4 lg:grid-cols-[1.3fr,0.7fr]">
          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <Sparkles className="h-4 w-4 text-amber-400" />
              Guarded presets
            </div>
            <p className="mt-2 text-sm leading-6 text-zinc-500">
              Presets verändern nur bekannte, getestete Signalgruppen und Recovery-Flags. So bleibt Billing lokal reproduzierbar.
            </p>
            <div className="mt-4 grid gap-3 lg:grid-cols-3">
              {presets.map((preset) => {
                const selected = preset.id === currentPresetId;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => applyPreset(preset)}
                    className={cn(
                      'rounded-2xl border p-4 text-left transition',
                      selected
                        ? 'border-amber-500/40 bg-amber-500/10'
                        : 'border-zinc-800 bg-zinc-950/80 hover:border-zinc-700 hover:bg-zinc-900'
                    )}
                    data-testid={`trigger-preset-${preset.id}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-medium text-white">{preset.label}</p>
                      {preset.recommended ? <AdminStatusPill tone="emerald">Empfohlen</AdminStatusPill> : <AdminStatusPill tone={preset.risk === 'high' ? 'red' : 'amber'}>{preset.risk_label || 'Fallback'}</AdminStatusPill>}
                    </div>
                    <p className="mt-2 text-sm leading-6 text-zinc-400">{preset.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5">
            <div className="flex items-center gap-2 text-sm font-medium text-white">
              <Lock className="h-4 w-4 text-blue-400" />
              Geschützte Leitplanken
            </div>
            <div className="mt-4 space-y-4 text-sm text-zinc-400">
              <div>
                <p className="font-medium text-zinc-200">Delete-Kanäle bleiben serverseitig fixiert</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(lockedFields.delete_channel_prefixes || []).map((item) => (
                    <span key={item} className="rounded-full border border-zinc-800 bg-zinc-950 px-2 py-1 font-mono text-xs text-zinc-500">{item}</span>
                  ))}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(lockedFields.delete_channel_suffixes || []).map((item) => (
                    <span key={item} className="rounded-full border border-zinc-800 bg-zinc-950 px-2 py-1 font-mono text-xs text-zinc-500">{item}</span>
                  ))}
                </div>
              </div>
              <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-amber-100">
                <div className="flex items-start gap-3">
                  <ShieldAlert className="mt-0.5 h-4 w-4 text-amber-400" />
                  <div>
                    <p className="font-medium">Why this is locked down</p>
                    <p className="mt-1 text-sm leading-6 text-amber-100/80">
                      Freie Channel-Muster oder beliebige Interpretationsnamen würden Session-Abbruch und Finish-Authority schwer nachvollziehbar machen.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </AdminSection>

      <div className="grid gap-6 xl:grid-cols-2">
        {Object.entries(GROUP_META).map(([groupKey, meta]) => (
          <AdminSection
            key={groupKey}
            title={meta.title}
            description={meta.description}
            actions={<AdminStatusPill tone={meta.tone}>{meta.roleLabel}</AdminStatusPill>}
          >
            <div className="space-y-3">
              {(groupedSignals[groupKey] || []).map((signal) => (
                <SignalToggleCard
                  key={signal.interpretation}
                  signal={signal}
                  checked={(policy[groupKey] || []).includes(signal.interpretation)}
                  onToggle={() => toggleSignal(groupKey, signal.interpretation)}
                />
              ))}
            </div>
          </AdminSection>
        ))}
      </div>

      <AdminSection
        title="Recovery-Guards"
        description="Standardmäßig gilt: Finish/Abort nur nach aktivem Match. Recovery-Overrides bleiben hinter einer zusätzlichen Freigabe."
      >
        <div className="grid gap-4 lg:grid-cols-[1fr,1fr]">
          <div className="space-y-4 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium text-white">Prior active match required</p>
                <p className="mt-1 text-sm leading-6 text-zinc-500">
                  Verhindert, dass isolierte Finish- oder Delete-Hinweise ohne aktive Session Billing auslösen.
                </p>
              </div>
              <div className="space-y-3">
                <div className="flex items-center gap-3 text-sm text-zinc-300">
                  <Switch
                    checked={Boolean(policy.require_prior_active_for_finish)}
                    onCheckedChange={(value) => updateFlag('require_prior_active_for_finish', value)}
                    data-testid="trigger-require-active-finish"
                  />
                  Finish
                </div>
                <div className="flex items-center gap-3 text-sm text-zinc-300">
                  <Switch
                    checked={Boolean(policy.require_prior_active_for_abort)}
                    onCheckedChange={(value) => updateFlag('require_prior_active_for_abort', value)}
                    data-testid="trigger-require-active-abort"
                  />
                  Abort
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-4 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="font-medium text-white">Expert recovery overrides</p>
                <p className="mt-1 text-sm leading-6 text-zinc-500">
                  Nur für instabile Venue-Setups. Keine freie Signalbearbeitung, nur klar benannte Fallbacks.
                </p>
              </div>
              <Switch
                checked={advancedUnlocked}
                onCheckedChange={setAdvancedUnlocked}
                data-testid="trigger-advanced-unlock"
              />
            </div>

            {!advancedUnlocked ? (
              <div className="rounded-2xl border border-dashed border-zinc-800 bg-zinc-950/80 p-4 text-sm text-zinc-500">
                Erweiterte Recovery-Schalter sind standardmäßig gesperrt.
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-950/80 p-4">
                  <div>
                    <p className="font-medium text-white">Console finish authority</p>
                    <p className="mt-1 text-sm leading-6 text-zinc-500">
                      Erlaubt Konsole als bestätigendes Finish-Signal, falls WS-Endzustände in der Venue unzuverlässig sind.
                    </p>
                  </div>
                  <Switch
                    checked={Boolean(policy.allow_console_finish_authority)}
                    onCheckedChange={(value) => updateFlag('allow_console_finish_authority', value)}
                    data-testid="trigger-console-authority"
                  />
                </div>
                <div className="flex items-center justify-between rounded-2xl border border-zinc-800 bg-zinc-950/80 p-4">
                  <div>
                    <p className="font-medium text-white">DOM finish authority</p>
                    <p className="mt-1 text-sm leading-6 text-zinc-500">
                      Letzter Fallback. Nur aktivieren, wenn WS und Konsole reproduzierbar keine sauberen Finishs liefern.
                    </p>
                  </div>
                  <Switch
                    checked={Boolean(policy.allow_dom_finish_authority)}
                    onCheckedChange={(value) => updateFlag('allow_dom_finish_authority', value)}
                    data-testid="trigger-dom-authority"
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-100">
          <div className="flex items-start gap-3">
            <Siren className="mt-0.5 h-4 w-4 text-red-400" />
            <div>
              <p className="font-medium">Billing safety note</p>
              <p className="mt-1 leading-6 text-red-100/80">
                Recovery-Overrides ändern nie die Signal-Namen oder Delete-Muster. Sie erweitern nur die Authority-Ebene bereits bekannter Quellen.
              </p>
            </div>
          </div>
        </div>
      </AdminSection>

      <div className="rounded-2xl border border-zinc-800 bg-zinc-950/60 p-4 text-sm text-zinc-500">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-4 w-4 text-amber-400" />
          <p>
            Für lokale Operatoren ist das bewusst ein begrenzter Policy-Editor. Wenn später ein echter Superadmin-Layer dazukommt, kann dort zusätzlich ein weitergehender Review-/Diff-Flow ergänzt werden — nicht direkt am Kiosk-PC.
          </p>
        </div>
      </div>
    </div>
  );
}
