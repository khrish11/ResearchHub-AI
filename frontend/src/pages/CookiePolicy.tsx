import React from 'react';

const CookiePolicy: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
        <h1 className="text-3xl font-bold text-slate-900">Cookie Policy</h1>
        <p className="mt-2 text-sm text-slate-500">Effective date: March 4, 2026</p>

        <div className="mt-6 space-y-5 text-sm leading-7 text-slate-700">
          <section>
            <h2 className="text-base font-semibold text-slate-900">1. Essential Storage</h2>
            <p>
              We use essential browser storage for authentication tokens, session state, and security controls.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900">2. Analytics Preferences</h2>
            <p>
              Optional analytics or performance preferences can be managed through the cookie consent banner.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900">3. Managing Cookies</h2>
            <p>
              You can update your preferences from the consent banner and by clearing browser storage.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default CookiePolicy;
