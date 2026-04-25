import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Shield, Key, Store, Check, AlertTriangle, Rocket, Eye, EyeOff, Link2, Database, RefreshCw } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { AdminPage, AdminSection, AdminStatCard, AdminStatsGrid, AdminStatusPill } from '../../components/admin/AdminShell';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function SetupWizard() {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const [formData, setFormData] = useState({
    admin_password: '',
    admin_password_confirm: '',
    staff_pin: '',
    cafe_name: 'Dart Zone',
    generate_new_secrets: true,
  });

  const checkStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/setup/status`);
      setStatus(response.data);
      if (response.data.is_complete) {
        navigate('/admin/login');
      }
    } catch (error) {
      console.error('Failed to check setup status:', error);
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    checkStatus();
  }, [checkStatus]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (formData.admin_password.length < 8) {
      toast.error('Admin-Passwort muss mindestens 8 Zeichen haben');
      return;
    }

    if (formData.admin_password !== formData.admin_password_confirm) {
      toast.error('Passwörter stimmen nicht überein');
      return;
    }

    if (formData.staff_pin.length !== 4 || !/^\d{4}$/.test(formData.staff_pin)) {
      toast.error('Staff-PIN muss genau 4 Ziffern sein');
      return;
    }

    setSubmitting(true);

    try {
      const response = await axios.post(`${API}/setup/complete`, {
        admin_password: formData.admin_password,
        staff_pin: formData.staff_pin,
        cafe_name: formData.cafe_name,
        generate_new_secrets: formData.generate_new_secrets,
      });

      toast.success('Setup abgeschlossen!');

      if (response.data.restart_required) {
        toast.info('Server-Neustart erforderlich für neue Secrets');
      }

      setTimeout(() => navigate('/admin/login'), 2000);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Setup fehlgeschlagen');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--color-bg)] flex items-center justify-center">
        <RefreshCw className="h-10 w-10 animate-spin text-amber-500" />
      </div>
    );
  }

  if (status?.is_complete) {
    return null;
  }

  const preflightChecks = status?.preflight_checks || [];
  const okChecks = preflightChecks.filter((check) => check.ok).length;
  const passwordMatches = formData.admin_password && formData.admin_password_confirm && formData.admin_password === formData.admin_password_confirm;

  return (
    <div className="min-h-screen bg-[var(--color-bg)] px-4 py-8 md:px-6 md:py-10" data-testid="setup-wizard">
      <div className="mx-auto max-w-6xl">
        <AdminPage
          eyebrow="First-run setup"
          title="Ersteinrichtung"
          description="Einmal sauber absichern, dann ist Ruhe: Admin-Zugang, Quick-PIN, Venue-Name und optionale Secret-Rotation in einer konsistenten ersten Inbetriebnahme."
          actions={
            <AdminStatusPill tone="amber">
              <Rocket className="h-3 w-3" /> Initialisierung
            </AdminStatusPill>
          }
        >
          <AdminStatsGrid>
            <AdminStatCard icon={Shield} label="Preflight" value={`${okChecks}/${preflightChecks.length || 0}`} hint="erfolgreiche Checks vor Abschluss" tone={okChecks === preflightChecks.length && preflightChecks.length > 0 ? 'emerald' : 'amber'} />
            <AdminStatCard icon={Link2} label="Lokale URLs" value={Object.keys(status?.local_urls || {}).length} hint="sichtbare Operator-Endpunkte" tone="blue" />
            <AdminStatCard icon={Database} label="Datenbank" value={status?.database_path ? 'Erkannt' : 'Unbekannt'} hint={status?.database_path || 'Pfad nicht gemeldet'} tone="violet" />
            <AdminStatCard icon={Key} label="Secret-Rotation" value={formData.generate_new_secrets ? 'Aktiv' : 'Aus'} hint="neue JWT-/Agent-Secrets beim Abschluss" tone={formData.generate_new_secrets ? 'emerald' : 'neutral'} />
          </AdminStatsGrid>

          <div className="grid gap-6 xl:grid-cols-[0.82fr,1.18fr]">
            <div className="space-y-6">
              <AdminSection title="Installations-Preflight" description="Kurzer Realitätscheck, bevor die Standard-Credentials verschwinden.">
                <div className="space-y-3">
                  {preflightChecks.map((check) => (
                    <div key={check.key} className="flex items-start justify-between gap-3 rounded-2xl border border-[rgb(var(--color-border-rgb)/0.76)] bg-[rgb(var(--color-surface-rgb)/0.52)] px-4 py-3">
                      <div className="min-w-0">
                        <p className="font-medium text-[var(--color-text)]">{check.label}</p>
                        <p className="mt-1 break-all text-sm text-[var(--color-text-secondary)]">{check.detail}</p>
                      </div>
                      <AdminStatusPill tone={check.ok ? 'emerald' : 'amber'}>{check.ok ? 'OK' : 'prüfen'}</AdminStatusPill>
                    </div>
                  ))}
                </div>
              </AdminSection>

              <AdminSection title="Lokale Operator-URLs" description="Praktisch für den ersten Gerätezugriff oder Remote-Support im gleichen Netz.">
                <div className="space-y-3">
                  {Object.entries(status?.local_urls || {}).map(([key, value]) => (
                    <div key={key} className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.76)] bg-[rgb(var(--color-surface-rgb)/0.52)] px-4 py-3">
                      <p className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">{key}</p>
                      <p className="mt-2 break-all font-mono text-sm text-[var(--color-text)]">{value}</p>
                    </div>
                  ))}
                  <div className="rounded-2xl border border-[rgb(var(--color-border-rgb)/0.76)] bg-[rgb(var(--color-bg-rgb)/0.34)] px-4 py-3 text-sm text-[var(--color-text-secondary)]">
                    Datenbank: <span className="break-all font-mono text-[var(--color-text)]">{status?.database_path || '-'}</span>
                  </div>
                </div>
              </AdminSection>

              <AdminSection title="Sicherheitshinweis" description="Die Standard-Zugangsdaten verschwinden nach diesem Schritt endgültig.">
                <div className="flex items-start gap-3 rounded-2xl border border-[rgb(var(--color-primary-rgb)/0.22)] bg-[rgb(var(--color-primary-rgb)/0.1)] p-4">
                  <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0 text-[var(--color-primary)]" />
                  <div>
                    <p className="font-medium text-[var(--color-text)]">Neue Zugangsdaten sicher notieren</p>
                    <p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">
                      Die Defaults (admin/admin123) werden ersetzt. Wer diese Werte nachher nicht mehr weiß, schenkt sich selbst unnötigen Supportaufwand.
                    </p>
                  </div>
                </div>
              </AdminSection>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <AdminSection title="Admin-Passwort" description="Stark genug für den echten Betrieb, nicht nur für die erste Demo.">
                <div className="space-y-4">
                  <div className="space-y-2">
                    <label className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Neues Passwort</label>
                    <div className="relative">
                      <Input
                        type={showPassword ? 'text' : 'password'}
                        value={formData.admin_password}
                        onChange={(e) => setFormData({ ...formData, admin_password: e.target.value })}
                        placeholder="Mindestens 8 Zeichen"
                        data-testid="setup-admin-password"
                        className="input-industrial pr-12"
                        required
                        minLength={8}
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-4 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white"
                      >
                        {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                      </button>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Passwort bestätigen</label>
                    <Input
                      type={showPassword ? 'text' : 'password'}
                      value={formData.admin_password_confirm}
                      onChange={(e) => setFormData({ ...formData, admin_password_confirm: e.target.value })}
                      placeholder="Passwort wiederholen"
                      data-testid="setup-admin-password-confirm"
                      className="input-industrial"
                      required
                    />
                  </div>

                  {formData.admin_password && formData.admin_password_confirm ? (
                    <div className={`flex items-center gap-2 text-sm ${passwordMatches ? 'text-emerald-400' : 'text-red-400'}`}>
                      {passwordMatches ? (
                        <><Check className="h-4 w-4" /> Passwörter stimmen überein</>
                      ) : (
                        <><AlertTriangle className="h-4 w-4" /> Passwörter stimmen nicht überein</>
                      )}
                    </div>
                  ) : null}
                </div>
              </AdminSection>

              <AdminSection title="Staff Quick-PIN" description="Vier Ziffern für schnelle Operator-Aktionen, damit keine Standard-PIN aktiv bleibt.">
                <div className="space-y-3">
                  <p className="text-sm text-[var(--color-text-secondary)]">
                    Der PIN wird für vorhandene Admin- und Staff-Konten als Quick-PIN gesetzt und ersetzt unsichere Startwerte.
                  </p>
                  <div className="space-y-2">
                    <label className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Neuer PIN (4 Ziffern)</label>
                    <Input
                      type="text"
                      maxLength={4}
                      value={formData.staff_pin}
                      onChange={(e) => setFormData({ ...formData, staff_pin: e.target.value.replace(/\D/g, '') })}
                      placeholder="1234"
                      data-testid="setup-staff-pin"
                      className="input-industrial max-w-xs font-mono tracking-widest"
                      required
                      pattern="\d{4}"
                    />
                  </div>
                </div>
              </AdminSection>

              <AdminSection title="Venue-Name" description="Wird für lokale Beschriftung, Branding und den ersten professionellen Eindruck verwendet.">
                <div className="space-y-2">
                  <label className="text-[11px] uppercase tracking-[0.22em] text-[var(--color-text-muted)]">Name Ihres Cafés / Venues</label>
                  <Input
                    type="text"
                    value={formData.cafe_name}
                    onChange={(e) => setFormData({ ...formData, cafe_name: e.target.value })}
                    placeholder="Dart Zone"
                    data-testid="setup-cafe-name"
                    className="input-industrial"
                  />
                </div>
              </AdminSection>

              <AdminSection title="Sicherheits-Secrets" description="Optional, aber für echte Neuinstallationen die bessere Idee.">
                <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-[rgb(var(--color-border-rgb)/0.76)] bg-[rgb(var(--color-surface-rgb)/0.52)] p-4">
                  <input
                    type="checkbox"
                    checked={formData.generate_new_secrets}
                    onChange={(e) => setFormData({ ...formData, generate_new_secrets: e.target.checked })}
                    className="mt-1 h-5 w-5 rounded border-zinc-600 bg-zinc-800 text-amber-500 focus:ring-amber-500"
                  />
                  <div>
                    <p className="font-medium text-[var(--color-text)]">Neue JWT-/Agent-Secrets generieren</p>
                    <p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">
                      Für eine frische Installation empfohlen. Danach ist ein Server-Neustart erforderlich, damit alle neuen Secrets aktiv werden.
                    </p>
                  </div>
                </label>
              </AdminSection>

              <Button
                type="submit"
                disabled={submitting}
                data-testid="setup-submit-btn"
                className="h-16 w-full bg-amber-500 text-xl text-black hover:bg-amber-400"
              >
                {submitting ? 'Wird eingerichtet...' : 'Setup abschließen'}
              </Button>
            </form>
          </div>
        </AdminPage>
      </div>
    </div>
  );
}
