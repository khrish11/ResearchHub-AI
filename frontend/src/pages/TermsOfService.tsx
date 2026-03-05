import React from 'react';

const TermsOfService: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto max-w-3xl rounded-3xl border border-slate-200 bg-white p-6 sm:p-8 shadow-sm">
        <h1 className="text-3xl font-bold text-slate-900">Terms of Service</h1>
        <p className="mt-2 text-sm text-slate-500">Effective date: March 4, 2026</p>

        <div className="mt-6 space-y-5 text-sm leading-7 text-slate-700">
          <section>
            <h2 className="text-base font-semibold text-slate-900">1. Acceptable Use</h2>
            <p>
              You agree not to abuse the service, bypass security controls, or perform unlawful activity through the
              platform.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900">2. Account Responsibility</h2>
            <p>
              You are responsible for securing your credentials and all activity under your account.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900">3. Data and Content</h2>
            <p>
              You retain ownership of your uploaded and authored content. You grant the service permission to process
              it to deliver features.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900">4. Service Changes</h2>
            <p>
              Features may evolve for reliability, security, and compliance. Material policy changes will be reflected
              in updated legal pages.
            </p>
          </section>

          <section>
            <h2 className="text-base font-semibold text-slate-900">5. Limitation</h2>
            <p>
              The platform is provided on an as-is basis. Research outputs should be independently validated before
              high-stakes use.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default TermsOfService;
