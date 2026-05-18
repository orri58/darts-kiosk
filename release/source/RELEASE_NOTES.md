# Darts Kiosk — Release Notes v4.5.3

## Updater re-roll for free unlock fix

This release exists to push the free/manual unlock fix through the built-in Windows updater one more time under a newer version number.

## Why this release matters

Some machines ended up in a mixed state where the new admin UI was visible, but the old backend validation was still running. That causes the free-unlock button to appear while the API still rejects it with `Credits must be greater than zero`.

Version `v4.5.3` forces a fresh updater pass so the complete backend + frontend fix set is downloaded and applied again.

## Included
- admin-panel option `Kostenlos freischalten`
- backend support for `manual_unlock`
- free/manual unlock sessions book `0 € / 0 Credits`
- manual unlock sessions stay exempt from later credit deductions until staff lock the board again

## Validation performed

Executed successfully:

```bash
bash release/build_release.sh
```

Observed result:
- release artifacts were rebuilt for `v4.5.3`
- release assets were published for automatic system update discovery
- `releases/latest` now resolves to `v4.5.3`
