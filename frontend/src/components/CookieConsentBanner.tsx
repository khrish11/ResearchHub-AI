import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { COOKIE_CONSENT_KEY, type CookieConsentState, setCookieConsent } from '../utils/consent';

const CookieConsentBanner: React.FC = () => {
  const [consent, setConsent] = useState<CookieConsentState>(null);

  useEffect(() => {
    const existing = localStorage.getItem(COOKIE_CONSENT_KEY);
    if (existing === 'accepted' || existing === 'rejected') {
      setConsent(existing);
      return;
    }
    setConsent(null);
  }, []);

  if (consent !== null) return null;

  return (
    <div className="fixed bottom-4 left-1/2 z-50 w-[calc(100%-1.5rem)] max-w-2xl -translate-x-1/2 rounded-2xl border border-slate-200 bg-white p-4 shadow-xl">
      <p className="text-sm text-slate-700">
        We use essential cookies for login and security. Optional analytics can be controlled via consent preferences.
        Read our{' '}
        <Link to="/cookies" className="font-semibold text-indigo-700 hover:text-indigo-800">
          Cookie Policy
        </Link>
        .
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => {
            setCookieConsent('accepted');
            setConsent('accepted');
          }}
          className="rounded-xl bg-indigo-600 px-3 py-2 text-sm font-semibold text-white hover:bg-indigo-700 shadow-sm"
        >
          Accept
        </button>
        <button
          type="button"
          onClick={() => {
            setCookieConsent('rejected');
            setConsent('rejected');
          }}
          className="rounded-xl border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          Reject Optional
        </button>
      </div>
    </div>
  );
};

export default CookieConsentBanner;
