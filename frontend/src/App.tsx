import { BrowserRouter as Router, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { useState, useEffect, useRef, lazy, Suspense, type ReactElement } from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';
import ErrorBoundary from './components/ErrorBoundary';
import ToastContainer from './components/ToastContainer';
import CookieConsentBanner from './components/CookieConsentBanner';
import CommandPalette from './components/CommandPalette';
import api from './api';
import { getAppBasePath, toAppPath } from './utils/routing';
import { trackRouteView } from './utils/firebaseClient';
import { notifyAuthLogin } from './utils/authSession';
import { handleFirebaseRedirectResult, firebaseAuthAvailable } from './utils/firebaseAuth';

const Landing = lazy(() => import('./pages/Landing'));
const Login = lazy(() => import('./pages/Login'));
const Register = lazy(() => import('./pages/Register'));
const EmailVerification = lazy(() => import('./pages/EmailVerification'));
const Settings = lazy(() => import('./pages/Settings'));
const AccountSettings = lazy(() => import('./pages/AccountSettings'));
const Home = lazy(() => import('./pages/Home'));
const Dashboard = lazy(() => import('./pages/Dashboard'));
const SearchPapers = lazy(() => import('./pages/SearchPapers'));
const Workspace = lazy(() => import('./pages/Workspace'));
const Mindmap = lazy(() => import('./pages/Mindmap'));
const AITools = lazy(() => import('./pages/AITools'));
const ResearchAgent = lazy(() => import('./pages/ResearchAgent'));
const UploadPDF = lazy(() => import('./pages/UploadPDF'));
const DocSpace = lazy(() => import('./pages/DocSpace'));
const WritingChat = lazy(() => import('./pages/WritingChat'));
const DeveloperConsole = lazy(() => import('./pages/DeveloperConsole'));
const AnalyticsDashboard = lazy(() => import('./pages/AnalyticsDashboard'));
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy'));
const TermsOfService = lazy(() => import('./pages/TermsOfService'));
const CookiePolicy = lazy(() => import('./pages/CookiePolicy'));
const DataRights = lazy(() => import('./pages/DataRights'));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'));
const ResetPassword = lazy(() => import('./pages/ResetPassword'));

const RouteLoader = () => (
  <div className="min-h-[42vh] flex items-center justify-center" role="status" aria-live="polite">
    <div className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-sm">
      <span className="h-2.5 w-2.5 rounded-full bg-indigo-500 animate-pulse" />
      Loading workspace...
    </div>
  </div>
);

function RouteTelemetry() {
  const location = useLocation();

  useEffect(() => {
    void trackRouteView(`${location.pathname}${location.search}`);
  }, [location.pathname, location.search]);

  return null;
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);
  const routerBasename = getAppBasePath();
  const authBootstrapStarted = useRef(false);

  const refreshAuthState = async () => {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 8000);
      await api.get('/auth/me', { signal: controller.signal });
      clearTimeout(timeoutId);
      setIsAuthenticated(true);
    } catch {
      setIsAuthenticated(false);
    } finally {
      setAuthChecked(true);
    }
  };

  const onAuthSuccess = (token: string) => {
    if (!token) {
      return;
    }
    notifyAuthLogin();
    void refreshAuthState();
  };

  // useEffect(() => {
  //   void bootstrapGoogleServices();
  // }, []);

  useEffect(() => {
    if (authBootstrapStarted.current) {
      return;
    }
    authBootstrapStarted.current = true;

    const currentUrl = new URL(window.location.href);
    const hashParams = new URLSearchParams(currentUrl.hash.startsWith('#') ? currentUrl.hash.slice(1) : currentUrl.hash);
    const oauthCode = (hashParams.get('oauth_code') || currentUrl.searchParams.get('oauth_code') || '').trim();
    const legacyToken = (currentUrl.searchParams.get('token') || '').trim();

    const clearAuthArtifacts = () => {
      const nextUrl = new URL(window.location.href);
      nextUrl.searchParams.delete('token');
      nextUrl.searchParams.delete('oauth_code');
      nextUrl.hash = '';
      const nextPath = `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`;
      window.history.replaceState({}, document.title, nextPath);
    };

    // Safety net: guarantee authChecked becomes true even if everything else hangs.
    const safetyTimeout = window.setTimeout(() => {
      setAuthChecked((prev) => {
        if (!prev) {
          void refreshAuthState();
        }
        return prev;
      });
    }, 5000);

    // Check for Firebase redirect / current-user result first.
    if (firebaseAuthAvailable()) {
      handleFirebaseRedirectResult()
        .then((response) => {
          if (response) {
            clearAuthArtifacts();
            notifyAuthLogin();
            window.location.replace(toAppPath('/home'));
            return;
          }
          // No Firebase result — fall through to OAuth / cookie check.
          checkOAuthFlow();
        })
        .catch(() => {
          // Firebase check failed — fall through anyway.
          checkOAuthFlow();
        });
    } else {
      checkOAuthFlow();
    }

    function checkOAuthFlow() {
      if (oauthCode) {
        clearAuthArtifacts();
        void api
          .post('/auth/oauth/exchange', { code: oauthCode })
          .then((response) => {
            const nextToken = String(response.data?.access_token || '');
            if (!nextToken) {
              throw new Error('Missing OAuth access token');
            }
            notifyAuthLogin();
            window.location.replace(toAppPath('/home'));
          })
          .catch(() => {
            setIsAuthenticated(false);
            setAuthChecked(true);
            window.clearTimeout(safetyTimeout);
            const error = encodeURIComponent('Google sign-in session expired. Please try again.');
            window.location.replace(toAppPath(`/login?error=${error}`));
          });
        return;
      }

      if (legacyToken) {
        clearAuthArtifacts();
      }

      void refreshAuthState().then(() => window.clearTimeout(safetyTimeout));
    }
  }, []);

  useEffect(() => {
    const onSessionChange = () => {
      void refreshAuthState();
    };
    window.addEventListener('auth-session-changed', onSessionChange);
    return () => window.removeEventListener('auth-session-changed', onSessionChange);
  }, []);

  const protectedRoute = (element: ReactElement) => {
    if (!authChecked) {
      return <RouteLoader />;
    }
    return isAuthenticated ? element : <Navigate to="/login" replace />;
  };

  return (
    <ErrorBoundary>
      <ThemeProvider>
        <ToastProvider>
          <Router basename={routerBasename || undefined}>
            <div className="min-h-screen bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100 transition-colors duration-200">
              <RouteTelemetry />
              <a
                href="#main-content"
                className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-50 focus:rounded-md focus:bg-white focus:px-3 focus:py-2 focus:text-slate-900"
              >
                Skip to main content
              </a>
              <main id="main-content" tabIndex={-1}>
                <Suspense fallback={<RouteLoader />}>
                  <Routes>
                    <Route
                      path="/login"
                      element={authChecked && isAuthenticated ? <Navigate to="/home" replace /> : <Login setToken={onAuthSuccess} />}
                    />
                    <Route
                      path="/register"
                      element={authChecked && isAuthenticated ? <Navigate to="/home" replace /> : <Register setToken={onAuthSuccess} />}
                    />
                    <Route
                      path="/home"
                      element={protectedRoute(<Home />)}
                    />
                    <Route
                      path="/dashboard"
                      element={protectedRoute(<Dashboard />)}
                    />
                    <Route
                      path="/search"
                      element={protectedRoute(<SearchPapers />)}
                    />
                    <Route
                      path="/workspace/:id"
                      element={protectedRoute(<Workspace />)}
                    />
                    <Route
                      path="/mindmap"
                      element={protectedRoute(<Mindmap />)}
                    />
                    <Route
                      path="/ai-tools"
                      element={protectedRoute(<AITools />)}
                    />
                    <Route
                      path="/research-agent"
                      element={protectedRoute(<ResearchAgent />)}
                    />
                    <Route
                      path="/upload"
                      element={protectedRoute(<UploadPDF />)}
                    />
                    <Route
                      path="/docs"
                      element={protectedRoute(<DocSpace />)}
                    />
                    <Route
                      path="/research-chat"
                      element={protectedRoute(<WritingChat />)}
                    />
                    <Route path="/writing-chat" element={<Navigate to="/research-chat" replace />} />
                    <Route
                      path="/account"
                      element={protectedRoute(<AccountSettings />)}
                    />
                    <Route
                      path="/settings"
                      element={protectedRoute(<Settings />)}
                    />
                    <Route
                      path="/developer"
                      element={protectedRoute(<DeveloperConsole />)}
                    />
                    <Route
                      path="/analytics"
                      element={protectedRoute(<AnalyticsDashboard />)}
                    />
                    <Route path="/privacy" element={<PrivacyPolicy />} />
                    <Route path="/terms" element={<TermsOfService />} />
                    <Route path="/cookies" element={<CookiePolicy />} />
                    <Route path="/data-rights" element={<DataRights />} />
                    <Route path="/verify-email" element={<EmailVerification />} />
                    <Route path="/forgot-password" element={<ForgotPassword />} />
                    <Route path="/reset-password" element={<ResetPassword />} />
                    <Route path="/" element={authChecked && isAuthenticated ? <Navigate to="/home" replace /> : <Landing />} />
                  </Routes>
                </Suspense>
              </main>
              <footer className="border-t border-slate-200/70 px-4 py-4 text-center text-xs text-slate-700 dark:border-slate-700 dark:text-slate-100">
                <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-center gap-4">
                  <Link to="/privacy" className="font-medium text-slate-700 hover:text-slate-900 dark:text-slate-100 dark:hover:text-white">
                    Privacy
                  </Link>
                  <Link to="/terms" className="font-medium text-slate-700 hover:text-slate-900 dark:text-slate-100 dark:hover:text-white">
                    Terms
                  </Link>
                  <Link to="/cookies" className="font-medium text-slate-700 hover:text-slate-900 dark:text-slate-100 dark:hover:text-white">
                    Cookies
                  </Link>
                  <Link to="/data-rights" className="font-medium text-slate-700 hover:text-slate-900 dark:text-slate-100 dark:hover:text-white">
                    Data Rights
                  </Link>
                </div>
              </footer>
              <CookieConsentBanner />
              <ToastContainer />
              {isAuthenticated && <CommandPalette />}
            </div>
          </Router>
        </ToastProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
