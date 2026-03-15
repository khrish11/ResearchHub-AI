export const COOKIE_CONSENT_KEY = 'researchhub.cookie_consent.v1';
export const COOKIE_CONSENT_EVENT = 'soyog:cookie-consent-changed';

export type CookieConsentState = 'accepted' | 'rejected' | null;

export const getCookieConsent = (): CookieConsentState => {
  const value = localStorage.getItem(COOKIE_CONSENT_KEY);
  if (value === 'accepted' || value === 'rejected') {
    return value;
  }
  return null;
};

export const hasOptionalTelemetryConsent = (): boolean => getCookieConsent() === 'accepted';

export const setCookieConsent = (value: Exclude<CookieConsentState, null>) => {
  localStorage.setItem(COOKIE_CONSENT_KEY, value);
  window.dispatchEvent(new CustomEvent(COOKIE_CONSENT_EVENT, { detail: { consent: value } }));
};
