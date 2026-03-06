import { AlertTriangle, Phone, Lock } from 'lucide-react';
import { Button } from '../../components/ui/button';

export default function ErrorScreen({ message, onRetry, onLock, onCallStaff }) {
  return (
    <div className="h-full w-full flex flex-col items-center justify-center bg-zinc-950 p-8" data-testid="error-screen">
      {/* Error Icon */}
      <div className="relative mb-8">
        <div className="w-32 h-32 rounded-full bg-red-500/20 border-4 border-red-500/50 flex items-center justify-center animate-pulse">
          <AlertTriangle className="w-16 h-16 text-red-500" strokeWidth={2.5} />
        </div>
      </div>

      {/* Error Message */}
      <div className="text-center mb-12">
        <h2 className="text-4xl font-heading font-bold uppercase tracking-wider text-red-500 mb-4">
          FEHLER
        </h2>
        <p className="text-xl text-zinc-400 max-w-lg">
          {message || 'Ein unerwarteter Fehler ist aufgetreten. Bitte Personal rufen.'}
        </p>
      </div>

      {/* Action Buttons */}
      <div className="flex flex-col sm:flex-row gap-4 w-full max-w-xl">
        {/* Call Staff - Primary */}
        <Button
          onClick={onCallStaff}
          data-testid="error-call-staff-btn"
          className="flex-1 h-20 text-xl bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading tracking-wider"
        >
          <Phone className="w-6 h-6 mr-3" />
          Personal rufen
        </Button>

        {/* Back to Locked */}
        <Button
          onClick={onLock}
          data-testid="error-back-to-locked-btn"
          variant="outline"
          className="flex-1 h-20 text-xl border-2 border-zinc-700 text-zinc-300 hover:border-zinc-600 hover:text-white uppercase font-heading tracking-wider"
        >
          <Lock className="w-6 h-6 mr-3" />
          Zurück zu Gesperrt
        </Button>
      </div>

      {/* Retry Button (smaller) */}
      {onRetry && (
        <Button
          onClick={onRetry}
          variant="ghost"
          className="mt-6 text-zinc-500 hover:text-zinc-300"
        >
          Erneut versuchen
        </Button>
      )}

      {/* Footer */}
      <div className="absolute bottom-6 left-0 right-0 text-center">
        <p className="text-zinc-600 text-sm">
          Falls das Problem weiterhin besteht, bitte das System neu starten.
        </p>
      </div>
    </div>
  );
}
