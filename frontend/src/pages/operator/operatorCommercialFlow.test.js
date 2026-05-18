import {
  buildLicenseDetailPath,
  getTokenStatePresentation,
  resolveLicenseBackTarget,
} from './operatorCommercialFlow';

describe('operator commercial flow helpers', () => {
  test('buildLicenseDetailPath preserves intent and return continuity', () => {
    expect(buildLicenseDetailPath('/operator', 'lic-123', {
      intent: 'activate',
      returnTo: '/operator/licenses?status=active',
      returnLabel: 'Lizenzen · Aktiv',
    })).toBe('/operator/licenses/lic-123?intent=activate&returnTo=%2Foperator%2Flicenses%3Fstatus%3Dactive&returnLabel=Lizenzen+%C2%B7+Aktiv');
  });

  test('resolveLicenseBackTarget prefers explicit deep-link continuity', () => {
    expect(resolveLicenseBackTarget({
      search: '?intent=activate&returnTo=%2Foperator%2Flicenses%3Fstatus%3Dgrace&returnLabel=Gefilterte+Liste',
      fallbackPath: '/operator/licenses',
      fallbackLabel: 'Portfolio',
    })).toEqual({
      returnTo: '/operator/licenses?status=grace',
      returnLabel: 'Gefilterte Liste',
    });
  });

  test('token presentation distinguishes ready, stale, and consumed states clearly', () => {
    expect(getTokenStatePresentation({ state: 'active', active_expires_in_days: 3 })).toMatchObject({
      label: 'Token bereit',
      detail: '3T Restlaufzeit',
      semantic: 'ready_now',
    });

    expect(getTokenStatePresentation({ state: 'expired' })).toMatchObject({
      label: 'Token abgelaufen',
      detail: 'Neu ausstellen empfohlen',
      semantic: 'stale_token',
    });

    expect(getTokenStatePresentation({ state: 'consumed' })).toMatchObject({
      label: 'Aktivierung genutzt',
      detail: 'Gerät bereits registriert',
      semantic: 'bound_device',
    });
  });
});
