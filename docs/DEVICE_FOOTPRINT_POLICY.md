# Device Footprint Policy

## Ziel

Produktive lokale Geräte sollen nur die Dateien enthalten, die für den Betrieb, Support und kontrollierte Updates wirklich nötig sind.

Das Gerät ist **kein Entwicklungs-Checkout** und **kein allgemeiner Dateiablageort**.

## Erlaubte Hauptbereiche

```text
/app
/data
/config
```

## Ziel-Verzeichnislayout

```text
/app
  /backend_runtime
  /frontend_build
  /agent_runtime
  /bin
/data
  /db
  /logs
  /backups
  /cache
  /support
/config
  app.env
  device.json
```

## Erlaubt auf produktiven Geräten

- gebaute Backend-Runtime
- gebaute Frontend-Artefakte
- notwendige Agent-/Host-Runtime
- Start-/Service-Skripte
- lokale Datenbank / Runtime-Daten
- rotierte Logs
- definierte Kurzzeit-Backups
- Retry-/Outbox-Cache
- temporäre Support-Bundles
- minimale produktive Konfiguration

## Nicht erlaubt auf produktiven Geräten

- `.git`
- Quellcode, der nur für Entwicklung gedacht ist
- Testdateien, Fixtures, Snapshots, Coverage-Dateien
- `test_reports/`, `.pytest_cache`, `__pycache__` außerhalb notwendiger Runtime
- rohe Release-Build-Zwischenartefakte
- alte Update-ZIPs ohne aktiven Rollback-Zweck
- Projektdokumentation für Entwicklung/Strategie
- Notizen, Analysen, lokale Hilfsskripte
- vollständige Repo-Struktur, wenn ein Runtime-Paket genügt

## Packaging-Regeln

1. Geräte erhalten ein **eigenes Runtime-Artefakt**, nicht einfach den Repo-Inhalt.
2. Das Runtime-Artefakt basiert auf einer **Allowlist**.
3. Alles Nicht-Explizit-Erlaubte gilt als ausgeschlossen.
4. Updates ersetzen kontrolliert `app/` und lassen `data/`/`config/` unangetastet, außer definierte Migrationsschritte greifen.
5. Rollback-Artefakte dürfen begrenzt vorgehalten werden, aber mit klarer Retention.

## Schreibregeln

- `app/` ist update-kontrolliert und möglichst read-only.
- `data/` ist der normale Schreibbereich.
- `config/` ist klein, stabil und enthält keine unnötige Historie.

## Retention / Cleanup

- Logs: rotieren und begrenzen (z. B. Größe + Tage)
- Support-Bundles: automatisch nach definierter Frist löschen
- Download-/Update-Artefakte: nur aktuelles + letztes Rollback-Artefakt behalten
- temporäre Caches regelmäßig bereinigen
- verwaiste Dateien bei Start oder per Wartungsjob melden/bereinigen

## Release-Gate

Ein Device-Build ist nur release-fähig, wenn:
- die Allowlist eingehalten wird
- kein Dev-/Test-/Repo-Müll enthalten ist
- das Ziel-Verzeichnislayout stimmt
- Cleanup-/Retention-Regeln aktiv sind
- ein Packaging-Audit bestanden wurde
