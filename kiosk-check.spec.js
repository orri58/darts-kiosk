const { test, expect } = require('@playwright/test');

test('kiosk board1 should leave loading state', async ({ page }) => {
  await page.goto('http://127.0.0.1:3000/kiosk/BOARD-1', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(5000);
  const loading = page.getByTestId('kiosk-loading');
  const locked = page.getByTestId('locked-screen');
  const container = page.getByTestId('kiosk-container');

  const loadingVisible = await loading.isVisible().catch(() => false);
  const lockedVisible = await locked.isVisible().catch(() => false);
  const containerVisible = await container.isVisible().catch(() => false);
  const body = (await page.locator('body').innerText()).slice(0, 1000).replace(/\s+/g, ' ').trim();
  console.log('loadingVisible=' + loadingVisible);
  console.log('lockedVisible=' + lockedVisible);
  console.log('containerVisible=' + containerVisible);
  console.log('body=' + body);
  await page.screenshot({ path: '/root/.openclaw/workspace/.tmp/browser-shots/kiosk-dom-check.png', fullPage: true });

  expect(loadingVisible).toBeFalsy();
  expect(containerVisible || lockedVisible).toBeTruthy();
});
