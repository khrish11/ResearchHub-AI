import React, { useState } from 'react';
import api from '../api';
import { useNavigate, Link } from 'react-router-dom';

interface LoginProps {
    setToken: (token: string) => void;
}

const Login: React.FC<LoginProps> = ({ setToken }) => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const navigate = useNavigate();

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
                setError('Cannot reach server. Ensure the backend is running on http://localhost:8000');
            } else {
                setError(axErr.response?.data?.detail || 'Login failed. Please try again.');
            }
        }
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex">
            {/* Left side - decorative background */}
            <div className="hidden lg:flex lg:w-1/2 items-center justify-center relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-br from-purple-600/20 to-indigo-600/20"></div>
                <div className="relative z-10 w-96 h-96 rounded-full bg-gradient-to-br from-purple-500/30 to-indigo-500/30 blur-3xl"></div>
            </div>
            
            {/* Right side - login form */}
            <div className="flex-1 flex items-center justify-center px-4 py-12 sm:px-6 lg:px-8">
                <div className="w-full max-w-md space-y-8">
                    <div>
                        <h2 className="text-3xl font-bold text-white">Welcome Back</h2>
                        <p className="mt-2 text-purple-200">Sign in to continue to ResearchHub AI</p>
                    </div>
                    <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                        {error && (
                            <div className="rounded-md bg-red-500/20 border border-red-500/50 px-4 py-3 text-sm text-red-200">
                                {error}
                            </div>
                        )}
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-purple-200 mb-2">Email</label>
                                <input
                                    type="email"
                                    required
                                    className="w-full rounded-lg bg-slate-800/50 border border-slate-700 py-3 px-4 text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                    placeholder="you@example.com"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-purple-200 mb-2">Password</label>
                                <input
                                    type="password"
                                    required
                                    className="w-full rounded-lg bg-slate-800/50 border border-slate-700 py-3 px-4 text-white placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                                    placeholder="••••••••"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                />
                            </div>
                        </div>
                        <div>
                            <button
                                type="submit"
                                className="w-full rounded-lg bg-purple-600 py-3 px-4 text-sm font-semibold text-white hover:bg-purple-700 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:ring-offset-2 focus:ring-offset-slate-900 transition-colors"
                            >
                                Sign In
                            </button>
                        </div>
                        <div className="text-center">
                            <Link to="/register" className="text-sm text-purple-300 hover:text-purple-200">
                                Don't have an account? Sign up
                            </Link>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    );
};

export default Login;
