import { Clock3, ExternalLink, KeyRound, Monitor } from 'lucide-react';
import { Button } from '../ui/button';
import { ProductDataTable, ProductPageState, ProductStatusBadge, ProductSummaryRows } from './ProductDataDisplay';
import { ProductDetailCard } from './ProductDetail';

export function formatFleetTimestamp(isoStr) {
  if (!isoStr) return '—';
  try {
    return new Date(isoStr).toLocaleString('de-DE', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return isoStr;
  }
}

export function ProductFleetEmptyState({ scopeLabel = 'Geräte', readOnly = false, compact = false, testId }) {
  return (
    <ProductPageState
      kind="empty"
      compact={compact}
      title={`Keine ${scopeLabel} registriert`}
      description={readOnly ? 'Geräte erscheinen hier, sobald sie sich beim Central Server registrieren.' : 'Sobald Geräte im aktuellen Scope auftauchen, landen sie hier mit Binding-, Sync- und Lizenzstatus.'}
      data-testid={testId}
    />
  );
}

export function ProductFleetCardGrid({ devices, onOpenDevice, onOpenLicense, cardActionLabel = 'Gerät öffnen' }) {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {devices.map((d) => {
        const connectivity = d.connectivity || (d.is_online ? 'online' : 'offline');
        return (
          <div key={d.id} className="rounded-[1.35rem] border border-zinc-800 bg-zinc-950/40 p-4 transition-colors hover:border-zinc-700" data-testid={`fleet-card-${d.id}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <button onClick={() => onOpenDevice(d)} className="flex items-center gap-2 text-left text-sm font-medium text-zinc-100 hover:text-white hover:underline">
                  <Monitor size={15} className="text-zinc-500" />
                  <span className="truncate">{d.device_name || d.id?.slice(0, 8)}</span>
                </button>
                <p className="mt-1 truncate text-xs text-zinc-500">{d.reported_version || 'Keine Versionsmeldung'}</p>
              </div>
              <div className="flex flex-col items-end gap-2">
                <ProductStatusBadge kind="connectivity" value={connectivity} />
                <ProductStatusBadge kind="device" value={d.status === 'inactive' ? 'disabled' : (d.status || 'disabled')} />
              </div>
            </div>

            <div className="mt-4 space-y-3">
              <div className="flex flex-wrap gap-2">
                <ProductStatusBadge kind="binding" value={d.binding_status || 'unbound'} />
                {d.license_id ? <ProductStatusBadge kind="license" value="active" label="Lizenz verknüpft" /> : null}
              </div>
              <ProductSummaryRows
                columns={1}
                rows={[
                  { label: 'Heartbeat', value: formatFleetTimestamp(d.last_heartbeat_at), hint: 'Letzte gemeldete Präsenz' },
                  { label: 'Letzter Sync', value: formatFleetTimestamp(d.last_sync_at), hint: `${d.sync_count ?? 0} gemeldete Synchronisationen` },
                  { label: 'Install-ID', value: d.install_id ? `${d.install_id.slice(0, 12)}...` : '—', hint: 'Runtime-Identität' },
                ]}
              />
              <div className="flex items-center justify-between gap-3 rounded-2xl border border-zinc-800 bg-zinc-950/30 px-4 py-3 text-xs">
                <span className="text-zinc-500">Lizenz</span>
                {d.license_id ? (
                  <button onClick={() => onOpenLicense(d)} className="inline-flex items-center gap-1 text-zinc-200 hover:text-white">
                    <KeyRound size={12} /> {d.license_id.slice(0, 8)}...
                  </button>
                ) : (
                  <span className="text-zinc-500">—</span>
                )}
              </div>
              <Button variant="outline" size="sm" onClick={() => onOpenDevice(d)} className="w-full border-zinc-700 text-zinc-200 hover:bg-zinc-800">
                {cardActionLabel}
              </Button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function ProductFleetTable({ devices, canManage = false, onOpenDevice, onOpenLicense, onOpenRemoteActions, onToggleDevice }) {
  return (
    <ProductDataTable
      data-testid="devices-table"
      columns={[
        { key: 'connectivity', label: 'Konnektivität' },
        { key: 'device', label: 'Gerät' },
        { key: 'install', label: 'Install-ID' },
        { key: 'binding', label: 'Binding' },
        { key: 'license', label: 'Lizenz' },
        { key: 'last_sync', label: 'Letzter Sync' },
        { key: 'syncs', label: 'Syncs' },
        { key: 'status', label: 'Geräte-Status' },
        { key: 'remote', label: 'Remote Actions' },
        ...(canManage ? [{ key: 'actions', label: 'Aktionen', className: 'text-right' }] : []),
      ]}
    >
      {devices.map((d) => {
        const connectivity = d.connectivity || (d.is_online ? 'online' : 'offline');
        return (
          <tr key={d.id} className="text-zinc-300 hover:bg-zinc-900/30">
            <td className="px-4 py-3"><ProductStatusBadge kind="connectivity" value={connectivity} /></td>
            <td className="px-4 py-3 font-medium">
              <button onClick={() => onOpenDevice(d)} className="hover:text-white hover:underline">{d.device_name || d.id.slice(0, 8)}</button>
            </td>
            <td className="px-4 py-3 text-xs font-mono text-zinc-400">{d.install_id ? d.install_id.slice(0, 12) + '...' : '—'}</td>
            <td className="px-4 py-3"><ProductStatusBadge kind="binding" value={d.binding_status || 'unbound'} /></td>
            <td className="px-4 py-3">
              {d.license_id ? (
                <button onClick={() => onOpenLicense(d)} className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800">
                  <KeyRound className="h-3.5 w-3.5" /> {d.license_id.slice(0, 8)}...
                </button>
              ) : <span className="text-xs text-zinc-500">—</span>}
            </td>
            <td className="px-4 py-3 text-xs text-zinc-400">{formatFleetTimestamp(d.last_sync_at)}</td>
            <td className="px-4 py-3 text-zinc-400">{d.sync_count || 0}</td>
            <td className="px-4 py-3"><ProductStatusBadge kind="device" value={d.status === 'inactive' ? 'disabled' : (d.status || 'disabled')} /></td>
            <td className="px-4 py-3">
              <button onClick={() => onOpenRemoteActions(d)} className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-indigo-300 hover:bg-indigo-500/10">
                Öffnen <ExternalLink className="h-3.5 w-3.5" />
              </button>
            </td>
            {canManage ? (
              <td className="px-4 py-3 text-right">
                <button onClick={() => onToggleDevice(d)} className="rounded-md border border-zinc-800 px-2.5 py-1.5 text-xs text-zinc-300 hover:border-zinc-700 hover:bg-zinc-800">
                  {d.status === 'active' ? 'Deaktivieren' : 'Aktivieren'}
                </button>
              </td>
            ) : null}
          </tr>
        );
      })}
    </ProductDataTable>
  );
}

export function ProductOpsRail({ title, eyebrow, description, rows = [], callout, empty = 'Keine Daten verfügbar', testId }) {
  const visibleRows = rows.filter((row) => row && (row.value != null || row.detail || row.badge));
  return (
    <ProductDetailCard title={title} eyebrow={eyebrow} description={description} data-testid={testId}>
      <div className="space-y-3">
        {callout ? (
          <div className={`rounded-2xl border px-3.5 py-3 text-sm ${callout.tone || 'border-zinc-800 bg-zinc-950/40 text-zinc-300'}`}>
            <div className="flex items-start gap-2.5">
              {callout.icon ? <callout.icon className="mt-0.5 h-4 w-4" /> : null}
              <div>
                <p className="font-medium text-white">{callout.title}</p>
                {callout.description ? <p className="mt-1 text-current/80">{callout.description}</p> : null}
              </div>
            </div>
          </div>
        ) : null}
        {visibleRows.length ? visibleRows.map((row) => (
          <div key={row.label} className="flex items-start justify-between gap-4 rounded-2xl border border-zinc-800 bg-zinc-950/30 px-4 py-3">
            <div className="min-w-0">
              <p className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">{row.label}</p>
              {row.detail ? <p className="mt-1 text-xs text-zinc-500">{row.detail}</p> : null}
            </div>
            <div className="min-w-0 text-right">
              {row.badge || <p className="text-sm font-medium text-white">{row.value || '—'}</p>}
              {row.meta ? <p className="mt-1 text-xs text-zinc-500">{row.meta}</p> : null}
            </div>
          </div>
        )) : <div className="rounded-2xl border border-dashed border-zinc-800 px-4 py-5 text-sm text-zinc-500">{empty}</div>}
      </div>
    </ProductDetailCard>
  );
}

export function ProductTimelinePanel({ title, eyebrow, description, items = [], empty = 'Keine Einträge vorhanden', renderMeta, renderTitle, renderBody, testId }) {
  return (
    <ProductDetailCard title={title} eyebrow={eyebrow} description={description} data-testid={testId}>
      {items.length ? (
        <div className="space-y-3">
          {items.map((item, index) => (
            <div key={item.id || item.timestamp || index} className="rounded-2xl border border-zinc-800 bg-zinc-950/30 px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-white">{renderTitle(item)}</p>
                  {renderBody ? <div className="mt-1 text-xs leading-5 text-zinc-400">{renderBody(item)}</div> : null}
                </div>
                {renderMeta ? <div className="shrink-0">{renderMeta(item)}</div> : null}
              </div>
            </div>
          ))}
        </div>
      ) : <div className="rounded-2xl border border-dashed border-zinc-800 px-4 py-5 text-sm text-zinc-500">{empty}</div>}
    </ProductDetailCard>
  );
}

export function ProductLogPanel({ logs = [], logFilter, onChangeFilter, levelClasses = {}, testId = 'product-log-panel' }) {
  const filtered = logs.filter((entry) => logFilter === 'all' || entry.level === logFilter);
  return (
    <ProductDetailCard
      title="Geräte-Logs"
      eyebrow="Operational stream"
      description="Letzte Runtime-Einträge mit Level-Filter und Quellbezug."
      data-testid={testId}
      actions={(
        <div className="flex items-center gap-1" data-testid="log-filter">
          {['all', 'info', 'warn', 'error'].map((f) => (
            <button
              key={f}
              onClick={() => onChangeFilter(f)}
              className={`rounded-full px-2.5 py-1 text-[10px] font-medium transition-colors ${logFilter === f ? 'bg-zinc-200 text-zinc-900' : 'text-zinc-500 hover:text-zinc-300'}`}
            >
              {f === 'all' ? 'Alle' : f.toUpperCase()}
            </button>
          ))}
        </div>
      )}
    >
      {filtered.length ? (
        <div className="space-y-2" data-testid="device-logs">
          {filtered.slice().reverse().map((entry, index) => (
            <div key={`${entry.ts || index}-${entry.msg || index}`} className="rounded-2xl border border-zinc-800 bg-zinc-950/40 px-4 py-3" data-testid={`log-entry-${index}`}>
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-zinc-500">
                <span className="inline-flex items-center gap-1"><Clock3 className="h-3 w-3" /> {entry.ts ? entry.ts.slice(11, 19) : '—'}</span>
                <span className={`${levelClasses[entry.level] || 'text-zinc-400'} font-semibold`}>{(entry.level || '').toUpperCase() || 'LOG'}</span>
                {entry.src ? <span className="rounded-full border border-zinc-800 px-2 py-0.5 text-zinc-400">{entry.src}</span> : null}
              </div>
              <p className="mt-2 break-all font-mono text-xs text-zinc-200">{entry.msg || '—'}</p>
            </div>
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-zinc-800 px-4 py-5 text-sm text-zinc-500">
          Keine Logs verfügbar {logFilter !== 'all' ? `(Filter: ${logFilter})` : ''}
        </div>
      )}
    </ProductDetailCard>
  );
}
