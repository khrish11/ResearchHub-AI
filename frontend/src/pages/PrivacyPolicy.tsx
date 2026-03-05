import React from 'react';
import { Link } from 'react-router-dom';

const PrivacyPolicy: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
        <h1 className="text-3xl font-bold text-slate-900">Privacy Policy</h1>
        <p className="mt-2 text-sm text-slate-500">Effective date: March 4, 2026</p>

        <div className="mt-6 space-y-5 text-sm leading-7 text-slate-700">
          <section>
            <h2 className="text-base font-semibold text-slate-900">1. Data We Collect</h2>
            <p>
              Account data (email, profile), workspace content (papers, notes, chats), and operational telemetry
              required for security, reliability, and performance.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900">2. Why We Process Data</h2>
            <p>
              We process your data to deliver core product features, secure accounts, prevent abuse, and maintain
              platform reliability.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900">3. Legal Rights</h2>
            <p>
              You can request access, deletion, correction, portability, and consent withdrawal through the data rights
              portal.
            </p>
            <Link to="/data-rights" className="inline-flex mt-2 text-indigo-700 hover:text-indigo-800 font-medium">
              Open Data Rights Portal
            </Link>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900">4. Retention</h2>
            <p>
              Account content is retained while your account is active. You can request deletion at any time.
              Security and audit logs are retained for operational and legal obligations.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900">5. Contact</h2>
            <p>
              For privacy concerns, submit a request via the in-app data rights workflow and include jurisdiction
              details if relevant.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
