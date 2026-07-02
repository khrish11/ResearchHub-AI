import axios from 'axios';
import { toAppPath } from './utils/routing';
import { getAppCheckTokenValue } from './utils/firebaseClient';
import { clearAuthSession, getBackendToken, setBackendToken } from './utils/authSession';
import { apiErrorMessage, apiErrorMessageFromPayload } from './utils/apiError';

const resolveApiUrl = (): string => {
    const raw =
        import.meta.env.VITE_API_URL ||
        import.meta.env.VITE_API_BASE ||
        'http://localhost:8010';
    return String(raw).trim().replace(/\/+$/, '');
};

export const API_URL = resolveApiUrl();
export const GOOGLE_LOGIN_URL = `${API_URL}/auth/google/login`;
const resolveApiTimeoutMs = (): number => {
    const raw = Number(import.meta.env.VITE_API_TIMEOUT_MS || 120000);
    if (!Number.isFinite(raw) || raw <= 0) {
        return 120000;
    }
    return Math.max(15000, Math.min(300000, Math.trunc(raw)));
};

const DEFAULT_API_TIMEOUT_MS = resolveApiTimeoutMs();

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
    const error = await res.json().catch(() => null);
    throw new Error(apiErrorMessageFromPayload(error, `API request failed (${res.status})`));
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
    timeout: DEFAULT_API_TIMEOUT_MS,
});

// Single combined request interceptor — merges auth token + Firebase App Check.
api.interceptors.request.use(async (config) => {
    const url = String(config.url || '');
    // Long-running routes can legitimately exceed the default timeout.
    if (
        url.includes('/research/full-pipeline') ||
        url.includes('/research/multi-agent-analysis') ||
        url.includes('/research/paper-draft')
    ) {
        config.timeout = Math.max(DEFAULT_API_TIMEOUT_MS, 180000);
    } else if (
        url.includes('/workspace-insights/') ||
        url.includes('/workspace-feed/')
    ) {
        config.timeout = Math.max(DEFAULT_API_TIMEOUT_MS, 90000);
    }

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
    path.includes('/auth/logout');

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
                    .then((response) => {
                        const newToken = response.data?.access_token;
                        if (newToken) {
                            setBackendToken(newToken);
                        }
                    })
                    .finally(() => {
                        refreshInFlight = null;
                    });
            }
            try {
                await refreshInFlight;
                return api(originalConfig);
            } catch (err) {
                await clearAuthSession();
                const pathName = window.location.pathname;
                const publicPaths = [
                    '/',
                    '/login',
                    '/register',
                    '/privacy',
                    '/terms',
                    '/cookies',
                    '/data-rights',
                    '/verify-email',
                    '/forgot-password',
                    '/reset-password',
                ];
                const cleanPathName = pathName.replace(/\/+$/, '');
                const isPublic = publicPaths.some((p) => {
                    const cleanAppPath = toAppPath(p).replace(/\/+$/, '');
                    return cleanPathName === cleanAppPath;
                });
                if (!isPublic && !pathName.endsWith('/login')) {
                    window.location.href = toAppPath('/login');
                }
                return Promise.reject(err);
            }
        }

        try {
            const normalized = apiErrorMessage(error, error?.message || 'Request failed');
            if (normalized && typeof normalized === 'string') {
                error.message = normalized;
            }
        } catch {
            // never block error propagation on normalization failures
        }
        return Promise.reject(error);
    }
);

export default api;
