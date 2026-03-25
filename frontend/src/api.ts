import axios from 'axios';
import { toAppPath } from './utils/routing';
import { getAppCheckTokenValue } from './utils/firebaseClient';
import { clearAuthSession, getBackendToken } from './utils/authSession';

const resolveApiUrl = (): string => {
    const raw =
        import.meta.env.VITE_API_URL ||
        import.meta.env.VITE_API_BASE ||
        'http://localhost:8010';
    return String(raw).trim().replace(/\/+$/, '');
};

export const API_URL = resolveApiUrl();
export const GOOGLE_LOGIN_URL = `${API_URL}/auth/google/login`;

export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getBackendToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> || {})
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    credentials: "include", // IMPORTANT for cookies
    headers,
    ...options
  });

  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || "API request failed");
  }

  return res.json();
}

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
    withCredentials: true,
    timeout: 10000,
});

// Single combined request interceptor — merges auth token + Firebase App Check.
api.interceptors.request.use(async (config) => {
    const token = getBackendToken();
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    try {
        const appCheckToken = await getAppCheckTokenValue();
        if (appCheckToken) {
            config.headers['X-Firebase-AppCheck'] = appCheckToken;
        }
    } catch {
        // App Check token failure must never block the request.
    }
    return config;
});

let refreshInFlight: Promise<void> | null = null;

const shouldSkipAutoAuthHandling = (path: string) =>
    path.includes('/auth/token') ||
    path.includes('/auth/register') ||
    path.includes('/auth/oauth/exchange') ||
    path.includes('/auth/firebase/session') ||  // never auto-refresh during session exchange
    path.includes('/auth/forgot-password') ||
    path.includes('/auth/reset-password') ||
    path.includes('/auth/refresh') ||
    path.includes('/auth/logout') ||
    path.includes('/auth/me');

api.interceptors.response.use(
    (response) => response,
    async (error) => {
        const status = error?.response?.status;
        const path = String(error?.config?.url || '');
        const originalConfig = error?.config || {};
        const alreadyRetried = Boolean((originalConfig as { _retry?: boolean })._retry);

        if (status === 401 && !shouldSkipAutoAuthHandling(path) && !alreadyRetried) {
            (originalConfig as { _retry?: boolean })._retry = true;
            if (!refreshInFlight) {
                refreshInFlight = api
                    .post('/auth/refresh')
                    .then(() => undefined)
                    .finally(() => {
                        refreshInFlight = null;
                    });
            }
            try {
                await refreshInFlight;
                return api(originalConfig);
            } catch {
                await clearAuthSession();
                if (!window.location.pathname.endsWith('/login')) {
                    window.location.href = toAppPath('/login');
                }
            }
        }

        return Promise.reject(error);
    }
);

export default api;
