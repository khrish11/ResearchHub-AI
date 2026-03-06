import { BrowserRouter as Router, Routes, Route, Navigate, Link } from 'react-router-dom';
import { useState, useEffect, lazy, Suspense } from 'react';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';
import ErrorBoundary from './components/ErrorBoundary';
import ToastContainer from './components/ToastContainer';
import CookieConsentBanner from './components/CookieConsentBanner';
import CommandPalette from './components/CommandPalette';
import { getAppBasePath } from './utils/routing';

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
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy'));
const TermsOfService = lazy(() => import('./pages/TermsOfService'));
const CookiePolicy = lazy(() => import('./pages/CookiePolicy'));
const DataRights = lazy(() => import('./pages/DataRights'));

const RouteLoader = () => (
  <div className="min-h-[42vh] flex items-center justify-center" role="status" aria-live="polite">
    <div className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-sm">
      <span className="h-2.5 w-2.5 rounded-full bg-indigo-500 animate-pulse" />
      Loading workspace...
    </div>
  </div>
);

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));
  const routerBasename = getAppBasePath();

  const setAuthToken = (newToken: string | null) => {
    if (newToken) {
      localStorage.setItem('token', newToken);
    } else {
      localStorage.removeItem('token');
    }
    setToken(newToken);
  };

  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const token = urlParams.get('token');
    if (token) {
      setAuthToken(token);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  return (
    <ErrorBoundary>
      <ThemeProvider>
        <ToastProvider>
          <Router basename={routerBasename || undefined}>
            <div className="min-h-screen bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100 transition-colors duration-200">
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
                      element={token ? <Navigate to="/home" replace /> : <Login setToken={setAuthToken} />}
                    />
                    <Route
                      path="/register"
                      element={token ? <Navigate to="/home" replace /> : <Register setToken={setAuthToken} />}
                    />
                    <Route
                      path="/home"
                      element={token ? <Home /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/dashboard"
                      element={token ? <Dashboard /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/search"
                      element={token ? <SearchPapers /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/workspace/:id"
                      element={token ? <Workspace /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/mindmap"
                      element={token ? <Mindmap /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/ai-tools"
                      element={token ? <AITools /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/research-agent"
                      element={token ? <ResearchAgent /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/upload"
                      element={token ? <UploadPDF /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/docs"
                      element={token ? <DocSpace /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/research-chat"
                      element={token ? <WritingChat /> : <Navigate to="/login" />}
                    />
                    <Route path="/writing-chat" element={<Navigate to="/research-chat" replace />} />
                    <Route
                      path="/account"
                      element={token ? <AccountSettings /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/settings"
                      element={token ? <Settings /> : <Navigate to="/login" />}
                    />
                    <Route
                      path="/developer"
                      element={token ? <DeveloperConsole /> : <Navigate to="/login" />}
                    />
                    <Route path="/privacy" element={<PrivacyPolicy />} />
                    <Route path="/terms" element={<TermsOfService />} />
                    <Route path="/cookies" element={<CookiePolicy />} />
                    <Route path="/data-rights" element={<DataRights />} />
                    <Route path="/verify-email" element={<EmailVerification />} />
                    <Route path="/" element={token ? <Navigate to="/home" /> : <Landing />} />
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
              {token && <CommandPalette />}
            </div>
          </Router>
        </ToastProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
