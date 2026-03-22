import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Mail } from 'lucide-react';
import api from '../api';

const ForgotPassword = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.post('/auth/forgot-password', { email: email.trim().toLowerCase() });
      setSubmitted(true);
    } catch {
      setError('Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#0b101c] px-4">
      <div className="w-full max-w-md">
        <div className="rounded-3xl border border-white/10 bg-[#111829]/90 p-8 shadow-2xl backdrop-blur">
          <Link
            to="/login"
            className="mb-6 inline-flex items-center gap-2 text-xs font-semibold text-slate-300 hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" /> Back to sign in
          </Link>

          <div className="mb-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-accent mb-4">
              <Mail className="h-5 w-5 text-white" />
            </div>
            <h1 className="text-2xl font-semibold text-white">Forgot your password?</h1>
            <p className="mt-2 text-sm text-slate-400">
              Enter the email address linked to your account and we will send you a reset link.
            </p>
          </div>

          {submitted ? (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-4 text-sm text-emerald-300">
              <p className="font-semibold">Check your inbox</p>
              <p className="mt-1 text-emerald-400">
                If an account with <strong>{email}</strong> exists, a password reset link has been sent. Check your spam folder too.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                  {error}
                </div>
              )}
              <div>
                <label htmlFor="fp-email" className="block text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">
                  Email address
                </label>
                <input
                  id="fp-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl bg-gradient-to-r from-primary to-accent px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:shadow-2xl disabled:opacity-60"
              >
                {loading ? 'Sending reset link...' : 'Send reset link'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default ForgotPassword;
