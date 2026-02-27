import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import EmailVerification from './pages/EmailVerification';
import Settings from './pages/Settings';
import AccountSettings from './pages/AccountSettings';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import SearchPapers from './pages/SearchPapers';
import Workspace from './pages/Workspace';
import Mindmap from './pages/Mindmap';
import AITools from './pages/AITools';
import ResearchAgent from './pages/ResearchAgent';
import UploadPDF from './pages/UploadPDF';
import DocSpace from './pages/DocSpace';
import WritingChat from './pages/WritingChat';
import DeveloperConsole from './pages/DeveloperConsole';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';
import ErrorBoundary from './components/ErrorBoundary';
import ToastContainer from './components/ToastContainer';
import { getAppBasePath } from './utils/routing';

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
                <Route path="/verify-email" element={<EmailVerification />} />
                <Route path="/" element={token ? <Navigate to="/home" /> : <Landing />} />
              </Routes>
              <ToastContainer />
            </div>
          </Router>
        </ToastProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
