import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { useState } from 'react';
import Landing from './pages/Landing';
import Login from './pages/Login';
import Register from './pages/Register';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import SearchPapers from './pages/SearchPapers';
import Workspace from './pages/Workspace';
import AITools from './pages/AITools';
import UploadPDF from './pages/UploadPDF';
import DocSpace from './pages/DocSpace';

function App() {
  const [token, setToken] = useState<string | null>(localStorage.getItem('token'));

  const setAuthToken = (newToken: string | null) => {
    if (newToken) {
      localStorage.setItem('token', newToken);
    } else {
      localStorage.removeItem('token');
    }
    setToken(newToken);
  };

  return (
    <Router>
      <div className="min-h-screen bg-gray-50 text-gray-900 font-sans">
        <Routes>
          <Route path="/login" element={<Login setToken={setAuthToken} />} />
          <Route path="/register" element={<Register setToken={setAuthToken} />} />
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
            path="/ai-tools"
            element={token ? <AITools /> : <Navigate to="/login" />}
          />
          <Route
            path="/upload"
            element={token ? <UploadPDF /> : <Navigate to="/login" />}
          />
          <Route
            path="/docs"
            element={token ? <DocSpace /> : <Navigate to="/login" />}
          />
          <Route path="/" element={token ? <Navigate to="/home" /> : <Landing />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
