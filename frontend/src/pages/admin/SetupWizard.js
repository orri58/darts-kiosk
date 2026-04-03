import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { Shield, Key, Store, Check, AlertTriangle, Rocket, Eye, EyeOff } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';

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
    generate_new_secrets: true
  });

  const checkStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/setup/status`);
      setStatus(response.data);
      
      // If setup is complete, redirect to admin
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
    
    // Validation
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
        generate_new_secrets: formData.generate_new_secrets
      });
      
      toast.success('Setup abgeschlossen!');
      
      if (response.data.restart_required) {
        toast.info('Server-Neustart erforderlich für neue Secrets');
      }
      
      // Redirect to login
      setTimeout(() => navigate('/admin/login'), 2000);
      
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Setup fehlgeschlagen');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <div className="w-10 h-10 border-4 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    );
  }

  if (status?.is_complete) {
    return null; // Will redirect
  }

  return (
    <div className="min-h-screen bg-zinc-950 py-12 px-4" data-testid="setup-wizard">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="w-20 h-20 rounded-full bg-amber-500/20 border-2 border-amber-500/50 flex items-center justify-center mx-auto mb-6">
            <Rocket className="w-10 h-10 text-amber-500" />
          </div>
          <h1 className="text-4xl font-heading font-bold uppercase tracking-wider text-white mb-2">
            Ersteinrichtung
          </h1>
          <p className="text-zinc-500 text-lg">
            Konfigurieren Sie sichere Zugangsdaten für Ihr Darts Kiosk System
          </p>
        </div>

        {status && (
          <div className="mb-8 grid gap-4 md:grid-cols-2">
            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-white text-base">Installations-Preflight</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {(status.preflight_checks || []).map((check) => (
                  <div key={check.key} className="flex items-start justify-between gap-3 rounded-sm bg-zinc-950/70 px-3 py-2">
                    <div>
                      <p className="text-white">{check.label}</p>
                      <p className="text-xs text-zinc-500 break-all">{check.detail}</p>
                    </div>
                    <span className={`mt-0.5 text-xs font-medium ${check.ok ? 'text-emerald-400' : 'text-amber-400'}`}>
                      {check.ok ? 'OK' : 'Pruefen'}
                    </span>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card className="bg-zinc-900 border-zinc-800">
              <CardHeader>
                <CardTitle className="text-white text-base">Lokale Operator-URLs</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                {Object.entries(status.local_urls || {}).map(([key, value]) => (
                  <div key={key} className="rounded-sm bg-zinc-950/70 px-3 py-2">
                    <p className="text-xs uppercase tracking-wider text-zinc-500">{key}</p>
                    <p className="mt-1 break-all font-mono text-zinc-200">{value}</p>
                  </div>
                ))}
                <div className="rounded-sm border border-zinc-800 px-3 py-2 text-xs text-zinc-500">
                  Datenbank: <span className="font-mono text-zinc-300 break-all">{status.database_path || '-'}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Security Warning */}
        <div className="mb-8 p-4 bg-amber-500/10 border border-amber-500/30 rounded-sm flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-amber-400 font-medium">Wichtiger Sicherheitshinweis</p>
            <p className="text-zinc-400 text-sm mt-1">
              Die Standard-Zugangsdaten (admin/admin123) werden durch Ihre neuen sicheren Passwörter ersetzt.
              Notieren Sie sich die neuen Zugangsdaten an einem sicheren Ort.
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Admin Password */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Shield className="w-5 h-5 text-amber-500" />
                Admin-Passwort
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Neues Passwort</label>
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
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>
              
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Passwort bestätigen</label>
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
              
              {formData.admin_password && formData.admin_password_confirm && (
                <div className={`flex items-center gap-2 text-sm ${formData.admin_password === formData.admin_password_confirm ? 'text-emerald-400' : 'text-red-400'}`}>
                  {formData.admin_password === formData.admin_password_confirm ? (
                    <><Check className="w-4 h-4" /> Passwörter stimmen überein</>
                  ) : (
                    <><AlertTriangle className="w-4 h-4" /> Passwörter stimmen nicht überein</>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Staff PIN */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Key className="w-5 h-5 text-amber-500" />
                Staff Quick-PIN
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-zinc-500">
                Der 4-stellige PIN wird fuer vorhandene Admin- und Staff-Konten als Quick-PIN gesetzt,
                damit kein Standard-PIN aktiv bleibt.
              </p>
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Neuer PIN (4 Ziffern)</label>
                <Input
                  type="text"
                  maxLength={4}
                  value={formData.staff_pin}
                  onChange={(e) => setFormData({ ...formData, staff_pin: e.target.value.replace(/\D/g, '') })}
                  placeholder="1234"
                  data-testid="setup-staff-pin"
                  className="input-industrial font-mono tracking-widest max-w-xs"
                  required
                  pattern="\d{4}"
                />
              </div>
            </CardContent>
          </Card>

          {/* Cafe Name */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Store className="w-5 h-5 text-amber-500" />
                Cafe-Name
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <label className="text-sm text-zinc-500 uppercase tracking-wider">Name Ihres Cafes</label>
                <Input
                  type="text"
                  value={formData.cafe_name}
                  onChange={(e) => setFormData({ ...formData, cafe_name: e.target.value })}
                  placeholder="Dart Zone"
                  data-testid="setup-cafe-name"
                  className="input-industrial"
                />
              </div>
            </CardContent>
          </Card>

          {/* Security Secrets */}
          <Card className="bg-zinc-900 border-zinc-800">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <Shield className="w-5 h-5 text-amber-500" />
                Sicherheits-Secrets
              </CardTitle>
            </CardHeader>
            <CardContent>
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.generate_new_secrets}
                  onChange={(e) => setFormData({ ...formData, generate_new_secrets: e.target.checked })}
                  className="w-5 h-5 rounded border-zinc-600 bg-zinc-800 text-amber-500 focus:ring-amber-500"
                />
                <div>
                  <p className="text-white">Neue JWT/Agent Secrets generieren</p>
                  <p className="text-sm text-zinc-500">
                    Empfohlen für die Ersteinrichtung. Server-Neustart erforderlich.
                  </p>
                </div>
              </label>
            </CardContent>
          </Card>

          {/* Submit */}
          <Button
            type="submit"
            disabled={submitting}
            data-testid="setup-submit-btn"
            className="w-full h-16 text-xl bg-amber-500 hover:bg-amber-400 text-black uppercase font-heading tracking-wider"
          >
            {submitting ? 'Wird eingerichtet...' : 'Setup abschließen'}
          </Button>
        </form>
      </div>
    </div>
  );
}
