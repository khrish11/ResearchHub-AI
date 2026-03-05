import React, { useState, useEffect, useCallback } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';
import { CheckCircle, AlertCircle, Mail, Loader2 } from 'lucide-react';
import type { AxiosError } from 'axios';
import api from '../api';

const EmailVerification: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const [resending, setResending] = useState(false);

  const token = searchParams.get('token');
  const email = searchParams.get('email');

  const verifyEmail = useCallback(async (verificationToken: string) => {
    try {
      await api.post('/auth/verify-email', { token: verificationToken });
      setStatus('success');
      setMessage('Your email has been successfully verified! You can now log in to your account.');

      // Redirect to login after 3 seconds
      setTimeout(() => {
        navigate('/login');
      }, 3000);
    } catch (error: unknown) {
      setStatus('error');
      setMessage(
        (error as AxiosError<{ detail?: string }>)?.response?.data?.detail ||
          'Failed to verify email. The link may be expired or invalid.'
      );
    }
  }, [navigate]);

  useEffect(() => {
    if (token) {
      void verifyEmail(token);
    } else {
      setStatus('error');
      setMessage('No verification token provided');
    }
  }, [token, verifyEmail]);

  const resendVerificationEmail = async () => {
    if (!email) return;

    setResending(true);
    try {
      await api.post('/auth/resend-verification-email', { email });
      setMessage('Verification email has been resent. Please check your inbox.');
    } catch (error: unknown) {
      setMessage(
        (error as AxiosError<{ detail?: string }>)?.response?.data?.detail ||
          'Failed to resend verification email.'
      );
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-white dark:bg-slate-800 rounded-xl shadow-2xl p-8">
        <div className="text-center">
          {status === 'loading' && (
            <>
              <Loader2 className="h-16 w-16 text-indigo-600 mx-auto mb-4 animate-spin" />
              <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-2">
                Verifying Email
              </h2>
              <p className="text-slate-600 dark:text-slate-400">
                Please wait while we verify your email address...
              </p>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircle className="h-16 w-16 text-green-600 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-2">
                Email Verified!
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mb-6">
                {message}
              </p>
              <p className="text-sm text-slate-500 dark:text-slate-500">
                Redirecting to login page...
              </p>
            </>
          )}

          {status === 'error' && (
            <>
              <AlertCircle className="h-16 w-16 text-red-600 mx-auto mb-4" />
              <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mb-2">
                Verification Failed
              </h2>
              <p className="text-slate-600 dark:text-slate-400 mb-6">
                {message}
              </p>

              {email && (
                <div className="space-y-4">
                  <button
                    onClick={resendVerificationEmail}
                    disabled={resending}
                    className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white px-4 py-3 rounded-lg font-medium transition-colors"
                  >
                    {resending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Mail className="h-4 w-4" />
                    )}
                    {resending ? 'Sending...' : 'Resend Verification Email'}
                  </button>

                  <Link
                    to="/login"
                    className="block w-full text-center bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-700 dark:text-slate-300 px-4 py-3 rounded-lg font-medium transition-colors"
                  >
                    Back to Login
                  </Link>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default EmailVerification;
