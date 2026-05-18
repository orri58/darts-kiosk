# Darts Kiosk — Release Notes v4.5.1

## Canonical updater release

This release exists to make the broader current product state available as a single clean latest version for automatic update discovery and installation.

## Why this release matters

Recent work had already produced the broader central/control-plane, operator/portal product-system, field-readiness, and manual-unlock changes, but the published release line had become confusing for auto-update purposes.

Version `v4.5.1` is the clean canonical release line that should now be used for update checks.

## Included
- central/control-plane refactor work already landed in the current tree
- operator/portal/admin product-system and shell/data/detail unification work already landed in the current tree
- board-PC preflight/postflight/certification evidence lane
- manual unlock without credits / manual relock support

## Validation performed

Executed successfully:

```bash
cd frontend && npm run build
bash release/build_release.sh
```

Observed result:
- frontend production build passed
- release artifacts were rebuilt for `v4.5.1`
- release assets were published for automatic system update discovery
