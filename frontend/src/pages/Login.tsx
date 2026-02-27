import React, { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Atom, Microscope, Sparkles } from 'lucide-react';
import api, { API_URL, getGoogleLoginUrl } from '../api';

interface LoginProps {
  setToken: (token: string) => void;
}

interface GoogleStatusResponse {
  configured: boolean;
}

const Login: React.FC<LoginProps> = ({ setToken }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [googleConfigured, setGoogleConfigured] = useState(true);
  const [googleLoginUrl, setGoogleLoginUrl] = useState(getGoogleLoginUrl());
  const [googleRedirecting, setGoogleRedirecting] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    setGoogleLoginUrl(getGoogleLoginUrl());
    api
      .get<GoogleStatusResponse>('/auth/google/status')
      .then((res) => {
        const status = res.data || { configured: false };
        setGoogleConfigured(!!status.configured);
      })
      .catch(() => {
        setGoogleConfigured(false);
      });

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
      const params = new URLSearchParams();
      params.append('username', email);
      params.append('password', password);

      const response = await api.post('/auth/token', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });

      setToken(response.data.access_token);
      navigate('/home');
    } catch (err: unknown) {
      const axErr = err as { response?: { status: number; data?: { detail?: string } }; message?: string };
      if (axErr.response?.status === 401) {
        setError('Incorrect email or password. Try again or register a new account.');
      } else if (axErr.message?.includes('Network') || !axErr.response) {
        setError(`Cannot reach server. Ensure the backend is running on ${API_URL}`);
      } else {
        setError(axErr.response?.data?.detail || 'Login failed. Please try again.');
      }
    }
  };

  const handleGoogleSignIn = () => {
    setError('');
    setGoogleRedirecting(true);
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
              <h1>ResearchHub AI</h1>
              <p>Intelligence for research workflows</p>
            </div>
          </div>

          <h2 className="auth-headline">Build high-signal research pipelines with an AI-native workspace.</h2>
          <p className="auth-sub">
            Search, import, synthesize, and write from one environment designed for deep research execution.
          </p>

          <div className="auth-visual-badges">
            <span>
              <Sparkles className="h-3.5 w-3.5" /> Multi-source discovery
            </span>
            <span>
              <Atom className="h-3.5 w-3.5" /> Context-aware AI
            </span>
          </div>

          <div className="auth-metric-grid">
            <div className="auth-metric">
              <h4>14+</h4>
              <p>Paper sources</p>
            </div>
            <div className="auth-metric">
              <h4>PDF + DOCX</h4>
              <p>Mindmap exports</p>
            </div>
            <div className="auth-metric">
              <h4>Secure</h4>
              <p>JWT sessions</p>
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
              <p className="auth-eyebrow">Welcome back</p>
              <h3 className="auth-title">Sign in to your account</h3>
              <p className="auth-copy">Continue your research session securely.</p>
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
              {error && (
                <div className="auth-error">
                  <div>{error}</div>
                </div>
              )}

              <div>
                <label className="auth-label">Email</label>
                <input
                  type="email"
                  required
                  className="auth-input"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div>
                <label className="auth-label">Password</label>
                <input
                  type="password"
                  required
                  className="auth-input"
                  placeholder="********"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              <button type="submit" className="auth-primary-btn">
                Sign In
              </button>

              <div className="auth-divider">
                <span>Or continue with</span>
              </div>

              {googleConfigured ? (
                <button
                  type="button"
                  onClick={handleGoogleSignIn}
                  disabled={googleRedirecting}
                  className="auth-google-btn disabled:opacity-70 disabled:cursor-not-allowed"
                >
                  <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24">
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                  {googleRedirecting ? 'Redirecting to Google...' : 'Sign in with Google'}
                </button>
              ) : (
                <button type="button" disabled className="auth-google-btn auth-google-disabled">
                  Google sign-in not configured
                </button>
              )}

              <p className="auth-footer">
                Do not have an account?{' '}
                <Link to="/register" className="auth-link">
                  Create one
                </Link>
              </p>
            </form>
          </div>
        </section>
      </div>
    </div>
  );
};

export default Login;
