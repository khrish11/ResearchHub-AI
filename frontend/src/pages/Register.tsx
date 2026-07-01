import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import PasswordStrengthIndicator from '../components/PasswordStrengthIndicator';
import { Atom, Microscope, Sparkles } from 'lucide-react';
import api, { API_URL, getGoogleLoginUrl } from '../api';
import {
  firebaseAuthAvailable,
  isFirebaseUnauthorizedDomainError,
  registerWithFirebasePassword,
  signInWithFirebaseGoogle,
} from '../utils/firebaseAuth';
import { getRemoteBoolean } from '../utils/firebaseClient';

interface RegisterProps {
  setToken?: (token: string) => void;
}

interface FirebaseStatusResponse {
  configured: boolean;
}

const buildGoogleAuthUrl = (targetPath = '/dashboard') => {
  const baseUrl = getGoogleLoginUrl();
  const url = new URL(baseUrl);
  url.searchParams.set('frontend_redirect', `${window.location.origin}${targetPath}`);
  return url.toString();
};

const Register: React.FC<RegisterProps> = ({ setToken }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [googleConfigured, setGoogleConfigured] = useState(true);
  const [firebaseEnabled, setFirebaseEnabled] = useState(false);
  const [googleRedirecting, setGoogleRedirecting] = useState(false);
  const [googleLoginUrl, setGoogleLoginUrl] = useState(buildGoogleAuthUrl());
  const navigate = useNavigate();
  const isFirebaseNotConfiguredError = (err: unknown) => {
    const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    const message = err instanceof Error ? err.message : '';
    const merged = `${detail || ''} ${message}`.toLowerCase();
    return merged.includes('firebase authentication is not configured');
  };

  useEffect(() => {
    const localFirebaseAvailability = firebaseAuthAvailable();
    setFirebaseEnabled(false);
    void Promise.allSettled([
      getRemoteBoolean('feature_firebase_auth', localFirebaseAvailability),
      api.get<FirebaseStatusResponse>('/auth/firebase/status'),
    ]).then(([flagResult, firebaseStatusResult]) => {
      const remoteFlagEnabled =
        flagResult.status === 'fulfilled' ? !!flagResult.value : localFirebaseAvailability;
      const backendFirebaseConfigured =
        firebaseStatusResult.status === 'fulfilled'
          ? !!firebaseStatusResult.value?.data?.configured
          : false;
      setFirebaseEnabled(localFirebaseAvailability && remoteFlagEnabled && backendFirebaseConfigured);
    });
    setGoogleLoginUrl(buildGoogleAuthUrl());
    api
      .get('/auth/google/status')
      .then((res) => setGoogleConfigured(!!res.data?.configured))
      .catch(() => setGoogleConfigured(false));

    const params = new URLSearchParams(window.location.search);
    const oauthError = params.get('error');
    if (oauthError) {
      setError(oauthError);
      params.delete('error');
      const next = params.toString();
      const nextUrl = `${window.location.pathname}${next ? `?${next}` : ''}`;
      window.history.replaceState({}, document.title, nextUrl);
    }
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    try {
      let response: { access_token?: string };
      if (firebaseEnabled) {
        try {
          response = await registerWithFirebasePassword(email, password);
        } catch (firebaseErr) {
          if (isFirebaseNotConfiguredError(firebaseErr)) {
            setFirebaseEnabled(false);
            response = await api.post('/auth/register', { email, password }).then((res) => res.data);
          } else {
            throw firebaseErr;
          }
        }
      } else {
        response = await api.post('/auth/register', { email, password }).then((res) => res.data);
      }
      const accessToken = response.access_token;
      if (accessToken && setToken) {
        setToken(accessToken);
        navigate('/dashboard');
      } else {
        navigate('/login');
      }
    } catch (err: unknown) {
      const axErr = err as { response?: { status: number; data?: { detail?: string } }; message?: string };
      if (firebaseEnabled && err instanceof Error && !axErr.response) {
        setError(err.message || 'Firebase sign-up failed. Please try again.');
        return;
      }
      if (axErr.response?.status === 400) {
        setError(axErr.response?.data?.detail || 'Email already registered.');
      } else if (axErr.message?.includes('Network') || !axErr.response) {
        setError(`Cannot reach server. Ensure the backend is running on ${API_URL}`);
      } else {
        setError(axErr.response?.data?.detail || 'Registration failed. Please try again.');
      }
    }
  };

  const handleGoogleSignUp = () => {
    setError('');
    setGoogleRedirecting(true);
    if (firebaseEnabled) {
      void signInWithFirebaseGoogle()
        .then((response) => {
          const accessToken = response.access_token;
          if (setToken && accessToken) {
            setToken(accessToken);
          }
          navigate('/dashboard');
        })
        .catch((err: unknown) => {
          if (isFirebaseNotConfiguredError(err) && googleConfigured) {
            setFirebaseEnabled(false);
            window.location.href = googleLoginUrl;
            return;
          }
          if (isFirebaseUnauthorizedDomainError(err) && googleConfigured) {
            window.location.href = googleLoginUrl;
            return;
          }
          const axDetail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
          const raw = err instanceof Error ? err.message : '';
          const msg =
            axDetail ||
            (raw.toLowerCase().includes('popup-closed') || raw.toLowerCase().includes('popup_closed')
              ? 'Google sign-up was cancelled. Please try again.'
              : raw.toLowerCase().includes('popup-blocked') || raw.toLowerCase().includes('popup_blocked')
              ? 'Popups are blocked. Please allow popups for this site and try again.'
              : raw || 'Google sign-up failed. Please try again.');
          setError(msg);
          setGoogleRedirecting(false);
        });
      return;
    }
    window.location.href = googleLoginUrl;
  };

  return (
    <div className="auth-shell">
      <div className="auth-bg">
        <div className="auth-nebula auth-nebula-a" />
        <div className="auth-nebula auth-nebula-b" />
        <div className="auth-nebula auth-nebula-c" />
      </div>

      <div className="auth-grid">
        <section className="auth-visual">
          <div className="auth-brand">
            <div className="auth-brand-chip">
              <Microscope className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1>Soyog AI</h1>
              <p>Intelligence for research workflows</p>
            </div>
          </div>

          <h2 className="auth-headline">Create your research command center in under a minute.</h2>
          <p className="auth-sub">
            Get your workspace online, connect your sources, and start collecting high-impact papers faster.
          </p>

          <div className="auth-visual-badges">
            <span>
              <Sparkles className="h-3.5 w-3.5" /> Personalized workspace
            </span>
            <span>
              <Atom className="h-3.5 w-3.5" /> Google sign-in ready
            </span>
          </div>

          <div className="auth-metric-grid">
            <div className="auth-metric">
              <h4>Fast setup</h4>
              <p>1-minute onboarding</p>
            </div>
            <div className="auth-metric">
              <h4>28+</h4>
              <p>Search indices</p>
            </div>
            <div className="auth-metric">
              <h4>AI-native</h4>
              <p>Research workflows</p>
            </div>
          </div>

          <div className="auth-orbit" aria-hidden="true">
            <div className="auth-core" />
            <div className="auth-ring auth-ring-a" />
            <div className="auth-ring auth-ring-b" />
            <div className="auth-ring auth-ring-c" />
          </div>
        </section>

        <section className="auth-card-wrap">
          <div className="auth-card">
            <div className="mb-6">
              <p className="auth-eyebrow">Get started</p>
              <h3 className="auth-title">Create your account</h3>
              <p className="auth-copy">Start building your research workflow.</p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
              {error && <div className="auth-error">{error}</div>}

              <div>
                <label htmlFor="register-email" className="auth-label">Email</label>
                <input
                  id="register-email"
                  type="email"
                  required
                  className="auth-input"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div>
                <label htmlFor="register-password" className="auth-label">Password</label>
                <input
                  id="register-password"
                  type="password"
                  required
                  className="auth-input"
                  placeholder="Create a secure password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <div className="mt-2">
                  <PasswordStrengthIndicator password={password} />
                </div>
              </div>

              <button type="submit" className="auth-primary-btn">
                Sign Up
              </button>

              <div className="auth-divider">
                <span>Or continue with</span>
              </div>

              {(firebaseEnabled || googleConfigured) ? (
                <button
                  type="button"
                  onClick={handleGoogleSignUp}
                  disabled={googleRedirecting}
                  className="auth-google-btn disabled:opacity-70 disabled:cursor-not-allowed"
                >
                  <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                  {googleRedirecting
                    ? (firebaseEnabled ? 'Opening Google sign-up...' : 'Redirecting to Google...')
                    : 'Sign up with Google'}
                </button>
              ) : (
                <button type="button" disabled className="auth-google-btn auth-google-disabled">
                  Google sign-up not configured
                </button>
              )}

              <p className="auth-footer">
                Already have an account?{' '}
                <Link to="/login" className="auth-link">
                  Sign in
                </Link>
              </p>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
};

export default Register;
