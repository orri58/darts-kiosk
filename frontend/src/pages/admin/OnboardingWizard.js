import { useState } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import {
  Building2, MapPin, KeyRound, Ticket, ChevronRight,
  CheckCircle, Copy, QrCode, AlertTriangle, Loader2,
  Monitor, Sparkles
} from 'lucide-react';
import { QRCodeSVG } from 'qrcode.react';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const CENTRAL_API = `${process.env.REACT_APP_BACKEND_URL}/api/central`;

const PLAN_OPTIONS = [
  { value: 'standard', label: 'Standard', desc: 'Normaler Betrieb' },
  { value: 'premium', label: 'Premium', desc: 'Erweiterte Funktionen' },
  { value: 'test', label: 'Test', desc: 'Zeitlich begrenzt zum Testen' },
];

const DURATION_OPTIONS = [
  { value: 30, label: '1 Monat' },
  { value: 90, label: '3 Monate' },
  { value: 180, label: '6 Monate' },
  { value: 365, label: '1 Jahr' },
  { value: 730, label: '2 Jahre' },
];

const TOKEN_VALIDITY = [
  { value: 1, label: '1 Stunde' },
  { value: 24, label: '24 Stunden' },
  { value: 168, label: '7 Tage' },
];

const STEPS = [
  { icon: Building2, label: 'Kunde' },
  { icon: MapPin, label: 'Standort' },
  { icon: KeyRound, label: 'Lizenz' },
  { icon: Ticket, label: 'Gerät' },
];

export default function OnboardingWizard({ headers, existingCustomers, existingLocations, onFinished }) {
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Created entities
  const [createdCustomer, setCreatedCustomer] = useState(null);
  const [createdLocation, setCreatedLocation] = useState(null);
  const [createdLicense, setCreatedLicense] = useState(null);
  const [generatedToken, setGeneratedToken] = useState(null);
  const [showQr, setShowQr] = useState(false);

  // Step 0: Customer
  const [useExisting, setUseExisting] = useState(false);
  const [selectedCustomerId, setSelectedCustomerId] = useState('');
  const [customerForm, setCustomerForm] = useState({ name: '', contact_email: '', contact_phone: '' });

  // Step 1: Location
  const [locationForm, setLocationForm] = useState({ name: '', address: '' });

  // Step 2: License
  const [licenseForm, setLicenseForm] = useState({
    plan_type: 'standard', max_devices: 1, duration_days: 365, grace_days: 7
  });

  // Step 3: Token
  const [tokenForm, setTokenForm] = useState({ device_name: '', token_hours: 24 });

  const clearError = () => setError('');

  const friendlyError = (err) => {
    const detail = err?.response?.data?.detail || '';
    if (err?.response?.status === 502) return 'Zentraler Server nicht erreichbar';
    if (err?.response?.status === 504) return 'Server Timeout';
    return detail || 'Ein Fehler ist aufgetreten';
  };

  // === Step 0: Create or select customer ===
  const handleCustomerNext = async () => {
    clearError();
    if (useExisting) {
      if (!selectedCustomerId) { setError('Bitte einen Kunden auswählen'); return; }
      const c = existingCustomers.find(c => c.id === selectedCustomerId);
      setCreatedCustomer(c);
      setStep(1);
      return;
    }
    if (!customerForm.name.trim()) { setError('Kundenname ist erforderlich'); return; }
    setLoading(true);
    try {
      const res = await axios.post(`${API}/licensing/customers`, customerForm, { headers });
      setCreatedCustomer(res.data);
      toast.success(`Kunde "${res.data.name}" erstellt`);
      setStep(1);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  // === Step 1: Create location ===
  const handleLocationNext = async () => {
    clearError();
    if (!locationForm.name.trim()) { setError('Standortname ist erforderlich'); return; }
    setLoading(true);
    try {
      const res = await axios.post(`${API}/licensing/locations`, {
        ...locationForm, customer_id: createdCustomer.id
      }, { headers });
      setCreatedLocation(res.data);
      toast.success(`Standort "${res.data.name}" erstellt`);
      setStep(2);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  // === Step 2: Create license ===
  const handleLicenseNext = async () => {
    clearError();
    setLoading(true);
    try {
      const ends = new Date();
      ends.setDate(ends.getDate() + licenseForm.duration_days);
      const res = await axios.post(`${API}/licensing/licenses`, {
        customer_id: createdCustomer.id,
        plan_type: licenseForm.plan_type,
        max_devices: parseInt(licenseForm.max_devices) || 1,
        grace_days: parseInt(licenseForm.grace_days) || 7,
        ends_at: ends.toISOString(),
      }, { headers });
      setCreatedLicense(res.data);
      toast.success('Lizenz erstellt');
      setStep(3);
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  // === Step 3: Generate registration token ===
  const handleGenerateToken = async () => {
    clearError();
    setLoading(true);
    try {
      const body = {
        expires_in_hours: tokenForm.token_hours,
        customer_id: createdCustomer.id,
      };
      if (createdLocation) body.location_id = createdLocation.id;
      if (createdLicense) body.license_id = createdLicense.id;
      if (tokenForm.device_name) body.device_name_template = tokenForm.device_name;

      const res = await axios.post(`${CENTRAL_API}/registration-tokens`, body, {
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
      setGeneratedToken(res.data.raw_token);
      toast.success('Registrierungscode erstellt');
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setLoading(false);
    }
  };

  const copyToken = () => {
    navigator.clipboard?.writeText(generatedToken);
    toast.success('Code kopiert');
  };

  // === Render ===
  return (
    <div className="space-y-6" data-testid="onboarding-wizard">
      {/* Step Indicator */}
      <div className="flex items-center justify-between px-2">
        {STEPS.map((s, i) => {
          const done = i < step || (i === 3 && generatedToken);
          const active = i === step && !generatedToken;
          return (
            <div key={i} className="flex items-center gap-2 flex-1">
              <div className={`flex items-center gap-2 ${i > 0 ? 'ml-auto' : ''} ${i < STEPS.length - 1 ? 'mr-auto' : 'ml-auto'}`}>
                <div className={`w-9 h-9 rounded-full flex items-center justify-center transition-all ${
                  done ? 'bg-emerald-500 text-white' :
                  active ? 'bg-amber-500 text-black ring-2 ring-amber-500/30' :
                  'bg-zinc-800 text-zinc-500'
                }`}>
                  {done ? <CheckCircle className="w-5 h-5" /> : <s.icon className="w-4 h-4" />}
                </div>
                <span className={`text-sm hidden sm:inline ${
                  done ? 'text-emerald-400 font-medium' :
                  active ? 'text-white font-medium' : 'text-zinc-500'
                }`}>{s.label}</span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-px mx-2 ${i < step ? 'bg-emerald-500' : 'bg-zinc-700'}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2" data-testid="wizard-error">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" /> {error}
        </div>
      )}

      {/* === STEP 0: KUNDE === */}
      {step === 0 && !generatedToken && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-6 space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Building2 className="w-5 h-5 text-amber-500" /> Kunde
              </h2>
              <p className="text-sm text-zinc-400 mt-1">Für wen wird das Gerät eingerichtet?</p>
            </div>

            {existingCustomers.length > 0 && (
              <div className="flex gap-2">
                <button onClick={() => { setUseExisting(false); clearError(); }}
                  className={`flex-1 py-3 rounded-lg text-sm font-medium transition-all border ${
                    !useExisting ? 'bg-amber-500/10 border-amber-500 text-amber-400' : 'bg-zinc-800 border-zinc-700 text-zinc-400'
                  }`} data-testid="onb-new-customer-btn">
                  Neuer Kunde
                </button>
                <button onClick={() => { setUseExisting(true); clearError(); }}
                  className={`flex-1 py-3 rounded-lg text-sm font-medium transition-all border ${
                    useExisting ? 'bg-amber-500/10 border-amber-500 text-amber-400' : 'bg-zinc-800 border-zinc-700 text-zinc-400'
                  }`} data-testid="onb-existing-customer-btn">
                  Bestehender Kunde
                </button>
              </div>
            )}

            {useExisting ? (
              <div>
                <label className="block text-sm text-zinc-300 mb-1.5">Kunde auswählen</label>
                <select className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white"
                  value={selectedCustomerId} onChange={e => setSelectedCustomerId(e.target.value)} data-testid="onb-customer-select">
                  <option value="">— Bitte wählen —</option>
                  {existingCustomers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="block text-sm text-zinc-300 mb-1.5">Kundenname *</label>
                  <input type="text" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500"
                    placeholder="z.B. Darts Lounge Berlin" value={customerForm.name} autoFocus
                    onChange={e => setCustomerForm(f => ({...f, name: e.target.value}))} data-testid="onb-customer-name" />
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm text-zinc-300 mb-1.5">E-Mail (optional)</label>
                    <input type="email" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500"
                      placeholder="info@dartslounge.de" value={customerForm.contact_email}
                      onChange={e => setCustomerForm(f => ({...f, contact_email: e.target.value}))} data-testid="onb-customer-email" />
                  </div>
                  <div>
                    <label className="block text-sm text-zinc-300 mb-1.5">Telefon (optional)</label>
                    <input type="text" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500"
                      placeholder="+49 30 12345" value={customerForm.contact_phone}
                      onChange={e => setCustomerForm(f => ({...f, contact_phone: e.target.value}))} data-testid="onb-customer-phone" />
                  </div>
                </div>
              </div>
            )}

            <div className="flex justify-end">
              <Button onClick={handleCustomerNext} disabled={loading}
                className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="onb-step0-next">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Weiter <ChevronRight className="w-4 h-4 ml-1" /></>}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* === STEP 1: STANDORT === */}
      {step === 1 && !generatedToken && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-6 space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <MapPin className="w-5 h-5 text-amber-500" /> Standort
              </h2>
              <p className="text-sm text-zinc-400 mt-1">
                Wo wird das Gerät aufgestellt? <span className="text-zinc-500">(Kunde: {createdCustomer?.name})</span>
              </p>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-sm text-zinc-300 mb-1.5">Standortname *</label>
                <input type="text" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500"
                  placeholder="z.B. Filiale Mitte" value={locationForm.name} autoFocus
                  onChange={e => setLocationForm(f => ({...f, name: e.target.value}))} data-testid="onb-location-name" />
              </div>
              <div>
                <label className="block text-sm text-zinc-300 mb-1.5">Adresse (optional)</label>
                <input type="text" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500"
                  placeholder="z.B. Alexanderplatz 1, 10178 Berlin" value={locationForm.address}
                  onChange={e => setLocationForm(f => ({...f, address: e.target.value}))} data-testid="onb-location-address" />
              </div>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(0)} className="border-zinc-600 text-zinc-300">Zurück</Button>
              <Button onClick={handleLocationNext} disabled={loading}
                className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="onb-step1-next">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Weiter <ChevronRight className="w-4 h-4 ml-1" /></>}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* === STEP 2: LIZENZ === */}
      {step === 2 && !generatedToken && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-6 space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <KeyRound className="w-5 h-5 text-amber-500" /> Lizenz
              </h2>
              <p className="text-sm text-zinc-400 mt-1">
                Welcher Plan und welche Laufzeit?
              </p>
            </div>

            {/* Plan Type */}
            <div>
              <label className="block text-sm text-zinc-300 mb-2">Lizenz-Plan</label>
              <div className="grid grid-cols-3 gap-3">
                {PLAN_OPTIONS.map(p => (
                  <button key={p.value} onClick={() => setLicenseForm(f => ({...f, plan_type: p.value}))}
                    className={`p-3 rounded-lg text-left transition-all border ${
                      licenseForm.plan_type === p.value
                        ? 'border-amber-500 bg-amber-500/10'
                        : 'border-zinc-700 bg-zinc-800 hover:border-zinc-500'
                    }`} data-testid={`onb-plan-${p.value}`}>
                    <p className={`text-sm font-medium ${licenseForm.plan_type === p.value ? 'text-amber-400' : 'text-white'}`}>{p.label}</p>
                    <p className="text-xs text-zinc-500 mt-0.5">{p.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Duration */}
            <div>
              <label className="block text-sm text-zinc-300 mb-2">Laufzeit</label>
              <div className="flex flex-wrap gap-2">
                {DURATION_OPTIONS.map(d => (
                  <button key={d.value} onClick={() => setLicenseForm(f => ({...f, duration_days: d.value}))}
                    className={`px-4 py-2 rounded-lg text-sm transition-all border ${
                      licenseForm.duration_days === d.value
                        ? 'border-amber-500 bg-amber-500/10 text-amber-400 font-medium'
                        : 'border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-500'
                    }`} data-testid={`onb-duration-${d.value}`}>
                    {d.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-zinc-300 mb-1.5">Max. Geräte</label>
                <input type="number" min={1} max={100}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500"
                  value={licenseForm.max_devices}
                  onChange={e => setLicenseForm(f => ({...f, max_devices: e.target.value}))} data-testid="onb-max-devices" />
              </div>
              <div>
                <label className="block text-sm text-zinc-300 mb-1.5">Toleranztage</label>
                <input type="number" min={0} max={90}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500"
                  value={licenseForm.grace_days}
                  onChange={e => setLicenseForm(f => ({...f, grace_days: e.target.value}))} data-testid="onb-grace-days" />
              </div>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(1)} className="border-zinc-600 text-zinc-300">Zurück</Button>
              <Button onClick={handleLicenseNext} disabled={loading}
                className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="onb-step2-next">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Weiter <ChevronRight className="w-4 h-4 ml-1" /></>}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* === STEP 3: TOKEN GENERIEREN === */}
      {step === 3 && !generatedToken && (
        <Card className="bg-zinc-900 border-zinc-800">
          <CardContent className="pt-6 space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <Ticket className="w-5 h-5 text-amber-500" /> Gerät vorbereiten
              </h2>
              <p className="text-sm text-zinc-400 mt-1">
                Erstellen Sie den Registrierungscode für den neuen Kiosk-PC.
              </p>
            </div>

            {/* Summary of what was created */}
            <div className="p-4 bg-zinc-800/50 rounded-xl space-y-2 text-sm">
              <p className="text-zinc-400 font-medium mb-2">Bisher eingerichtet:</p>
              <div className="grid grid-cols-2 gap-y-2 gap-x-4">
                <span className="text-zinc-500 flex items-center gap-1"><Building2 className="w-3.5 h-3.5" /> Kunde</span>
                <span className="text-white">{createdCustomer?.name}</span>
                <span className="text-zinc-500 flex items-center gap-1"><MapPin className="w-3.5 h-3.5" /> Standort</span>
                <span className="text-white">{createdLocation?.name}</span>
                <span className="text-zinc-500 flex items-center gap-1"><KeyRound className="w-3.5 h-3.5" /> Lizenz</span>
                <span className="text-white">{createdLicense?.plan_type} — {licenseForm.duration_days} Tage — Max. {createdLicense?.max_devices} Geräte</span>
              </div>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-sm text-zinc-300 mb-1.5">Gerätename (optional)</label>
                <input type="text" className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-white focus:outline-none focus:border-amber-500"
                  placeholder="z.B. Dartboard 1" value={tokenForm.device_name}
                  onChange={e => setTokenForm(f => ({...f, device_name: e.target.value}))} data-testid="onb-device-name" />
              </div>
              <div>
                <label className="block text-sm text-zinc-300 mb-2">Code gültig für</label>
                <div className="flex gap-2">
                  {TOKEN_VALIDITY.map(t => (
                    <button key={t.value} onClick={() => setTokenForm(f => ({...f, token_hours: t.value}))}
                      className={`px-4 py-2 rounded-lg text-sm transition-all border ${
                        tokenForm.token_hours === t.value
                          ? 'border-amber-500 bg-amber-500/10 text-amber-400 font-medium'
                          : 'border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-500'
                      }`} data-testid={`onb-token-validity-${t.value}`}>
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex justify-between">
              <Button variant="outline" onClick={() => setStep(2)} className="border-zinc-600 text-zinc-300">Zurück</Button>
              <Button onClick={handleGenerateToken} disabled={loading}
                className="bg-amber-500 hover:bg-amber-600 text-black" data-testid="onb-generate-token">
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>
                  <Ticket className="w-4 h-4 mr-1" /> Code erstellen
                </>}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* === RESULT: TOKEN + SUMMARY === */}
      {generatedToken && (
        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <CardContent className="pt-6 space-y-6">
            <div className="text-center">
              <div className="w-16 h-16 rounded-full bg-emerald-500/20 flex items-center justify-center mx-auto mb-3">
                <Sparkles className="w-8 h-8 text-emerald-400" />
              </div>
              <h2 className="text-xl font-bold text-white">Einrichtung abgeschlossen!</h2>
              <p className="text-sm text-zinc-400 mt-1">
                Alles bereit. Geben Sie diesen Code auf dem neuen Kiosk-PC ein.
              </p>
            </div>

            {/* Token display */}
            <div className="p-5 bg-black/40 rounded-xl border border-emerald-500/20" data-testid="onb-final-token">
              <p className="text-xs text-zinc-500 text-center mb-2">Registrierungscode</p>
              <p className="text-3xl font-mono text-white tracking-wider text-center break-all select-all">{generatedToken}</p>
            </div>

            <div className="flex items-center justify-center gap-3">
              <Button onClick={copyToken} className="bg-emerald-600 hover:bg-emerald-500 text-white" data-testid="onb-copy-token">
                <Copy className="w-4 h-4 mr-1" /> Code kopieren
              </Button>
              <Button variant="outline" onClick={() => setShowQr(!showQr)}
                className="border-zinc-600 text-zinc-300" data-testid="onb-qr-toggle">
                <QrCode className="w-4 h-4 mr-1" /> {showQr ? 'QR ausblenden' : 'QR-Code'}
              </Button>
            </div>

            {showQr && (
              <div className="flex justify-center p-5 bg-white rounded-xl" data-testid="onb-qr-code">
                <QRCodeSVG value={generatedToken} size={220} />
              </div>
            )}

            {/* Summary */}
            <div className="p-4 bg-zinc-900/80 rounded-xl">
              <p className="text-sm text-zinc-300 font-medium mb-3">Zusammenfassung</p>
              <div className="grid grid-cols-2 gap-y-2 gap-x-4 text-sm">
                <span className="text-zinc-500">Kunde</span>
                <span className="text-white">{createdCustomer?.name}</span>
                <span className="text-zinc-500">Standort</span>
                <span className="text-white">{createdLocation?.name}</span>
                <span className="text-zinc-500">Lizenz</span>
                <span className="text-white">{createdLicense?.plan_type} — {licenseForm.duration_days} Tage</span>
                <span className="text-zinc-500">Max. Geräte</span>
                <span className="text-white">{createdLicense?.max_devices}</span>
                <span className="text-zinc-500">Code gültig</span>
                <span className="text-white">{tokenForm.token_hours < 24 ? `${tokenForm.token_hours} Stunde(n)` : `${Math.round(tokenForm.token_hours / 24)} Tag(e)`}</span>
                {tokenForm.device_name && <>
                  <span className="text-zinc-500">Gerätename</span>
                  <span className="text-white">{tokenForm.device_name}</span>
                </>}
              </div>
            </div>

            {/* Technician hints */}
            <div className="p-4 bg-zinc-800/50 rounded-xl border border-zinc-700">
              <p className="text-sm font-medium text-zinc-300 mb-2 flex items-center gap-1.5">
                <Monitor className="w-4 h-4 text-amber-500" /> Hinweise für den Techniker
              </p>
              <ul className="text-sm text-zinc-400 space-y-1 list-disc list-inside">
                <li>Kiosk-PC starten und <strong>setup_windows.bat</strong> ausführen (einmalig)</li>
                <li>Danach <strong>start.bat</strong> ausführen</li>
                <li>Im Registrierungsbildschirm den Code eingeben</li>
                <li>Nach erfolgreicher Registrierung startet der Kiosk-Betrieb automatisch</li>
              </ul>
            </div>

            <div className="flex justify-center pt-2">
              <Button onClick={() => onFinished?.()} className="bg-zinc-700 hover:bg-zinc-600 text-white" data-testid="onb-finish-btn">
                Fertig — Zurück zur Übersicht
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
