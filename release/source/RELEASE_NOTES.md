# Darts Kiosk — Release Notes v4.5.2

## Admin-panel free unlock hotfix

This release fixes the missing admin-panel path for unlocking a board without credits.

## What changed

Version `v4.5.2` adds a real panel option for free/manual unlocks:

- locked boards now expose `Anpassen / Gratis`
- the unlock dialog now includes `Kostenlos freischalten`
- the backend now accepts `manual_unlock`
- manual unlocks book `0 € / 0 Credits`
- manual unlock sessions stay exempt from later credit deductions until staff lock the board again

## Why this release matters

The previous release line already carried the underlying manual-unlock pricing logic, but the actual admin-panel control was missing. This release closes that gap so the feature is usable from the shipped Windows package.

## Validation performed

Executed successfully:

```bash
PYTHONPATH=. .venv/bin/pytest backend/tests/test_manual_unlock_pricing.py -q
cd frontend && node - <<'JS'
const fs=require('fs');
const parser=require('@babel/parser');
const src=fs.readFileSync('src/pages/admin/Dashboard.js','utf8');
parser.parse(src,{sourceType:'module',plugins:['jsx']});
console.log('dashboard-parse-ok');
JS
bash release/build_release.sh
```

Observed result:
- manual-unlock backend regression suite passed
- admin dashboard JSX parse sanity passed
- release artifacts rebuilt for `v4.5.2`
- release assets published for automatic system update discovery
