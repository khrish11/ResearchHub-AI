import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeft, KeyRound } from 'lucide-react';
import api from '../api';

const ResetPassword = () => {
  const [token, setToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const t = params.get('token') || '';
    if (!t) {
      setError('No reset token found in the URL. Please request a new password reset link.');
    }
    setToken(t);
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    setLoading(true);
    try {
      await api.post('/auth/reset-password', { token, new_password: newPassword });
      setSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Failed to reset password. The link may have expired — please request a new one.');
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
              <KeyRound className="h-5 w-5 text-white" />
            </div>
            <h1 className="text-2xl font-semibold text-white">Reset your password</h1>
            <p className="mt-2 text-sm text-slate-400">
              Enter a new password for your account. It must be at least 8 characters and include a letter and a number.
            </p>
          </div>

          {success ? (
            <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-4 text-sm text-emerald-300">
              <p className="font-semibold">Password reset successfully!</p>
              <p className="mt-1 text-emerald-400">Redirecting you to sign in...</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="rounded-xl border border-red-400/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
                  {error}
                </div>
              )}
              <div>
                <label htmlFor="rp-password" className="block text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">
                  New password
                </label>
                <input
                  id="rp-password"
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
              <div>
                <label htmlFor="rp-confirm" className="block text-xs font-semibold uppercase tracking-[0.2em] text-slate-400 mb-2">
                  Confirm new password
                </label>
                <input
                  id="rp-confirm"
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Repeat your new password"
                  className="w-full rounded-xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 focus:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !token}
                className="w-full rounded-xl bg-gradient-to-r from-primary to-accent px-4 py-3 text-sm font-semibold text-white shadow-lg transition hover:shadow-2xl disabled:opacity-60"
              >
                {loading ? 'Resetting password...' : 'Reset password'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default ResetPassword;
