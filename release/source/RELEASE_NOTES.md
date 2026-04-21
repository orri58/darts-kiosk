# Darts Kiosk — Release Notes v4.4.11

## More control over lock-screen texts and branding layout

Darts Kiosk 4.4.11 adds direct control over the lock-screen information cards and gives the kiosk logo more flexible sizing and placement options.

## What changed

### 1. Lock-screen info cards are now configurable
The three cards shown on the locked screen can now be customized in Admin settings:

- Credits
- Matchstart
- Freischaltung

For each card you can now:
- change the card title
- override the large value text
- override the smaller hint text
- disable the card entirely

This makes it possible to adapt the wording to the venue, simplify the screen, or hide cards that are not useful in a specific setup.

### 2. Bigger logo options and centered screen layouts
Kiosk branding controls now include:

- larger logo size options (`xl`, `2xl`)
- centered lock-screen content
- a new hero-logo mode that places the venue logo prominently in the main screen area instead of only inside the top header
- separate hero-logo sizing for the locked screen

This makes it much easier to build layouts where the brand sits visually in the middle of the screen and can be made much larger when needed.

### 3. Defaults still come from pricing — unless you override them
If you do not enter custom card values, the lock screen still derives sensible defaults from pricing settings.
Examples:
- credit price from the configured credit price
- unlock card value from the default credit bundle
- matchstart wording from the active billing mode

If you do enter your own text, that custom text is used instead.

## Validation performed for this release

Executed successfully:

```bash
source .venv/bin/activate
python -m compileall backend agent
cd frontend && npm run build
bash release/build_release.sh
```

Observed result:
- backend compile sanity passed
- frontend production build passed
- release artifacts were rebuilt for `v4.4.11`
