# Darts Kiosk — Release Notes v4.4.16

## Premium UI polish across kiosk and admin

Darts Kiosk 4.4.16 is a quality release focused on finish.
Instead of adding one isolated feature, this version carries a more modern, professional design language through the product so kiosk and admin finally feel like one cohesive system.

## What changed

### 1. Shared UI foundations were upgraded
The frontend’s base design primitives were refined so the whole product benefits from the same stronger visual language:
- better dark-surface depth
- cleaner shadows and layering
- more consistent corners and spacing
- improved focus states
- more polished buttons, inputs, and tabs

This is the layer that makes everything else feel less improvised.

### 2. The kiosk now feels more premium during the full customer journey
Several of the most visible kiosk screens were reworked so they feel intentional and release-grade instead of merely functional:
- Locked screen
- Setup flow
- In-game screen
- Match result screen
- Credit-blocked state
- Error / recovery state

Highlights include:
- stronger hero and status panels
- clearer hierarchy and guidance text
- better player / tariff / credit context
- a more credible premium feel during both happy-path and edge-case flows
- much clearer communication when credits are missing or a match has ended

### 3. The admin panel is now substantially more consistent
The upgraded admin language now runs through the most important remaining holdout pages.
This version continues the shell/settings work and extends the same design standards to:
- Users
- Licensing
- Logs
- Leaderboard
- Setup Wizard

That means better section structure, calmer operator-facing copy, stronger metrics and empty states, cleaner status treatment, and less “old tool vs new tool” inconsistency.

### 4. High-friction operational states got clearer
This release also improves the quality of the product in stressful or high-attention moments:
- insufficient-credit states are easier to understand
- end-of-match flow looks more deliberate and polished
- recovery/error actions are grouped more clearly
- first-run and security-sensitive setup flows feel more trustworthy
- role/status visibility in admin is easier to scan quickly

## Why this matters

A professional product is not only about features.
It is also about whether every important screen feels deliberate, trustworthy, and consistent.
Version 4.4.16 closes several of the remaining visual and UX gaps that made parts of the product feel older than the rest.

## Validation performed for this release

Executed successfully:

```bash
cd frontend && npm run build
bash release/build_release.sh
```

Observed result:
- frontend production build passed cleanly
- release artifacts were rebuilt for `v4.4.16`
- release packages are ready for Windows, Linux, and Source distribution
