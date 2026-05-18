# Darts Kiosk — Release Notes v4.5.4

## Mobile shell / responsive fix

This release fixes the mobile admin shell so the sidebar behaves like a real professional app instead of staying visually stuck open on small screens.

## What changed

Version `v4.5.4` improves the shell and responsive behavior:

- fixed the mobile sidebar state so closed really means closed
- removed the CSS override that kept the menu visually open
- added proper overlay dismissal and body-scroll locking while the menu is open
- auto-closes the sidebar on route changes
- resets the mobile sidebar state when returning to desktop width
- positions the mobile sidebar below the sticky top header for a cleaner iPhone/mobile layout

## Why this release matters

The previous build worked functionally, but the shell behavior on mobile looked half-finished. This release closes that gap and makes the navigation behavior feel much more deliberate and production-ready.

## Validation performed

Executed successfully:

```bash
cd frontend && npm run build
```

Observed result:
- frontend production build passed
- release artifacts were rebuilt for `v4.5.4`
- release assets were published for automatic system update discovery
