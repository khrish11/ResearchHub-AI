import axios from 'axios';
import { toAppPath } from './utils/routing';

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
export const GOOGLE_LOGIN_URL = `${API_URL}/auth/google/login`;

const getFrontendRedirectBase = () => {
    const origin = window.location.origin;
    const pathname = window.location.pathname || '/';
    const trimmed =
        pathname.includes('/login')
            ? pathname.split('/login')[0]
            : pathname.includes('/register')
                ? pathname.split('/register')[0]
                : '';
    return `${origin}${trimmed}`;
};

export const getGoogleLoginUrl = () => {
    const frontendRedirect = encodeURIComponent(getFrontendRedirectBase());
    return `${GOOGLE_LOGIN_URL}?frontend_redirect=${frontendRedirect}`;
};

const api = axios.create({
    baseURL: API_URL,
});

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

api.interceptors.response.use(
    (response) => response,
    (error) => {
        const status = error?.response?.status;
        const path = String(error?.config?.url || '');
        const skipAuthRedirect = path.includes('/auth/token') || path.includes('/auth/register');

        if (status === 401 && !skipAuthRedirect) {
            localStorage.removeItem('token');
            if (!window.location.pathname.endsWith('/login')) {
                window.location.href = toAppPath('/login');
            }
        }

        return Promise.reject(error);
    }
);

export default api;
