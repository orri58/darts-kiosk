import { useState, useEffect } from 'react';
import { useCentralAuth } from '../../context/CentralAuthContext';
import { useCentralData } from '../../hooks/useCentralData';
import { Building2, MapPin, Monitor, ChevronDown, X } from 'lucide-react';

export default function ScopeSwitcher() {
  const { scope, updateScope, authHeaders, apiBase } = useCentralAuth();
  const { data: customers } = useCentralData('scope/customers', { skipScope: true });
  const [locations, setLocations] = useState([]);
  const [devices, setDevices] = useState([]);

  // Fetch locations when customer changes
  useEffect(() => {
    if (!scope.customerId) { setLocations([]); return; }
    const fetchLocs = async () => {
      try {
        const res = await fetch(`${apiBase}/scope/locations?customer_id=${scope.customerId}`, { headers: authHeaders });
        if (res.ok) setLocations(await res.json());
      } catch { setLocations([]); }
    };
    fetchLocs();
  }, [scope.customerId, apiBase, authHeaders]);

  // Fetch devices when location changes
  useEffect(() => {
    if (!scope.locationId) { setDevices([]); return; }
    const fetchDevs = async () => {
      try {
        const res = await fetch(`${apiBase}/scope/devices?location_id=${scope.locationId}`, { headers: authHeaders });
        if (res.ok) setDevices(await res.json());
      } catch { setDevices([]); }
    };
    fetchDevs();
  }, [scope.locationId, apiBase, authHeaders]);

  const handleCustomerChange = (cid) => {
    updateScope(cid ? { customerId: cid } : {});
  };

  const handleLocationChange = (lid) => {
    updateScope(lid ? { ...scope, locationId: lid, deviceId: undefined } : { customerId: scope.customerId });
  };

  const handleDeviceChange = (did) => {
    updateScope(did ? { ...scope, deviceId: did } : { ...scope, deviceId: undefined });
  };

  const clearAll = () => updateScope({});

  const hasScope = scope.customerId || scope.locationId || scope.deviceId;

  return (
    <div className="flex items-center gap-2 flex-wrap" data-testid="scope-switcher">
      {/* Customer Select */}
      <ScopeSelect
        icon={Building2}
        placeholder="Alle Kunden"
        value={scope.customerId || ''}
        options={(customers || []).map(c => ({ value: c.id, label: c.name }))}
        onChange={handleCustomerChange}
        testId="scope-customer"
      />

      {/* Location Select — only if customer selected */}
      {scope.customerId && (
        <ScopeSelect
          icon={MapPin}
          placeholder="Alle Standorte"
          value={scope.locationId || ''}
          options={locations.map(l => ({ value: l.id, label: l.name }))}
          onChange={handleLocationChange}
          testId="scope-location"
        />
      )}

      {/* Device Select — only if location selected */}
      {scope.locationId && (
        <ScopeSelect
          icon={Monitor}
          placeholder="Alle Geräte"
          value={scope.deviceId || ''}
          options={devices.map(d => ({ value: d.id, label: d.device_name || d.id.slice(0, 8) }))}
          onChange={handleDeviceChange}
          testId="scope-device"
        />
      )}

      {/* Clear all */}
      {hasScope && (
        <button
          onClick={clearAll}
          className="p-1.5 rounded-md text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
          title="Filter zurücksetzen"
          data-testid="scope-clear"
        >
          <X className="w-4 h-4" />
        </button>
      )}
    </div>
  );
}

function ScopeSelect({ icon: Icon, placeholder, value, options, onChange, testId }) {
  return (
    <div className="relative">
      <div className="absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none">
        <Icon className="w-3.5 h-3.5 text-zinc-500" />
      </div>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value || undefined)}
        data-testid={testId}
        className="appearance-none bg-zinc-900 border border-zinc-700/50 rounded-lg pl-8 pr-7 py-1.5 text-sm text-zinc-300 focus:outline-none focus:border-indigo-500/50 transition-colors cursor-pointer min-w-[140px]"
      >
        <option value="">{placeholder}</option>
        {options.map(opt => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
      <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
        <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
      </div>
    </div>
  );
}
