import { AlertTriangle, Lock, Phone, RefreshCw, ShieldAlert } from 'lucide-react';
import { Button } from '../../components/ui/button';

export default function ErrorScreen({ message, onRetry, onLock, onCallStaff }) {
  return (
    <div className="relative h-full w-full overflow-hidden bg-[var(--color-bg)]" data-testid="error-screen">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(239,68,68,0.18),transparent_28%),linear-gradient(180deg,rgb(var(--color-bg-rgb)/0.98),var(--color-bg))]" />

      <div className="relative z-10 flex h-full flex-col px-6 py-6 lg:px-10 lg:py-8">
        <div className="mx-auto flex w-full max-w-6xl flex-1 items-center">
          <div className="grid w-full gap-6 lg:grid-cols-[1.05fr,0.95fr] lg:items-center">
            <div className="space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--color-accent-rgb)/0.3)] bg-[rgb(var(--color-accent-rgb)/0.12)] px-4 py-2 text-sm text-[var(--color-accent)]">
                <ShieldAlert className="h-4 w-4" /> Systemhinweis
              </div>

              <div>
                <div className="flex items-center gap-4">
                  <div className="flex h-20 w-20 items-center justify-center rounded-[2rem] border border-[rgb(var(--color-accent-rgb)/0.3)] bg-[rgb(var(--color-accent-rgb)/0.12)] text-[var(--color-accent)] shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
                    <AlertTriangle className="h-10 w-10" strokeWidth={2.2} />
                  </div>
                  <div>
                    <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Kiosk Exception</p>
                    <h1 className="text-4xl font-heading uppercase tracking-[0.08em] text-[var(--color-text)] md:text-5xl lg:text-6xl">
                      Fehler am Board
                    </h1>
                  </div>
                </div>
                <p className="mt-5 max-w-2xl text-base leading-7 text-[var(--color-text-secondary)] lg:text-lg lg:leading-8">
                  Die Oberfläche bleibt bewusst kontrolliert: kein kaputter Zwischenzustand, keine stillen Halbsachen. Entweder neu laden oder sauber zurück in den Sperrmodus.
                </p>
              </div>

              <div className="rounded-[2rem] border border-[rgb(var(--color-accent-rgb)/0.24)] bg-[rgb(var(--color-bg-rgb)/0.58)] p-5 shadow-[0_18px_48px_rgba(0,0,0,0.22)]">
                <p className="text-[11px] uppercase tracking-[0.24em] text-[var(--color-accent)]">Fehlermeldung</p>
                <p className="mt-3 text-lg leading-8 text-[var(--color-text)]">
                  {message || 'Ein unerwarteter Fehler ist aufgetreten. Bitte Personal rufen.'}
                </p>
              </div>
            </div>

            <div className="rounded-[2rem] border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-surface-rgb)/0.62)] p-6 shadow-[0_24px_60px_rgba(0,0,0,0.28)]">
              <p className="text-[11px] uppercase tracking-[0.28em] text-[var(--color-text-muted)]">Sichere Aktionen</p>
              <div className="mt-5 space-y-3">
                {onCallStaff && (
                  <Button
                    onClick={onCallStaff}
                    data-testid="error-call-staff-btn"
                    className="h-16 w-full rounded-3xl bg-[var(--color-primary)] text-base text-[hsl(var(--primary-foreground))] hover:opacity-90"
                  >
                    <Phone className="mr-3 h-5 w-5" /> Personal rufen
                  </Button>
                )}

                <Button
                  onClick={onLock}
                  data-testid="error-back-to-locked-btn"
                  variant="outline"
                  className="h-16 w-full rounded-3xl border-[rgb(var(--color-border-rgb)/0.82)] text-base text-[var(--color-text)] hover:border-[rgb(var(--color-primary-rgb)/0.28)]"
                >
                  <Lock className="mr-3 h-5 w-5" /> Zurück zu Gesperrt
                </Button>

                {onRetry && (
                  <Button
                    onClick={onRetry}
                    variant="outline"
                    className="h-16 w-full rounded-3xl border-[rgb(var(--color-accent-rgb)/0.26)] bg-[rgb(var(--color-accent-rgb)/0.1)] text-base text-[var(--color-text)] hover:bg-[rgb(var(--color-accent-rgb)/0.16)]"
                  >
                    <RefreshCw className="mr-3 h-5 w-5" /> Erneut versuchen
                  </Button>
                )}
              </div>

              <div className="mt-5 rounded-3xl border border-[rgb(var(--color-border-rgb)/0.76)] bg-[rgb(var(--color-bg-rgb)/0.38)] px-4 py-4 text-sm leading-7 text-[var(--color-text-secondary)]">
                Empfehlung für den Betrieb: zuerst Retry, dann Lock-Screen. Nur wenn der Fehler wiederkommt, Personal oder System-Neustart.
              </div>
            </div>
          </div>
        </div>

        <div className="mx-auto w-full max-w-6xl rounded-3xl border border-[rgb(var(--color-border-rgb)/0.82)] bg-[rgb(var(--color-bg-rgb)/0.5)] px-5 py-3 text-sm text-[var(--color-text-secondary)] backdrop-blur">
          Falls das Problem bestehen bleibt, bitte den Board-PC oder den Observer-Flow im Adminbereich prüfen.
        </div>
      </div>
    </div>
  );
}
