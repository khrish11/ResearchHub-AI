import { getFirebaseAuthClient } from './firebaseClient';

export const BACKEND_TOKEN_KEY = 'token';

// Legacy in-memory token support for transitional flows.
let legacyBackendToken: string | null = null;

const getApiBaseUrl = (): string =>
  String(import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8010')
    .trim()
    .replace(/\/+$/, '');

export const getBackendToken = (): string | null => {
  // First check in-memory token (for current session)
  if (legacyBackendToken) {
    return legacyBackendToken;
  }
  // Fall back to localStorage for session persistence
  return localStorage.getItem(BACKEND_TOKEN_KEY);
};

export const setBackendToken = (token: string | null) => {
  legacyBackendToken = token || null;
  // Persist token to localStorage for session persistence
  if (token) {
    localStorage.setItem(BACKEND_TOKEN_KEY, token);
  } else {
    localStorage.removeItem(BACKEND_TOKEN_KEY);
  }
};

const notifyAuthSessionChanged = () => {
  window.dispatchEvent(new Event('auth-session-changed'));
};

export const clearAuthSession = async (notify = true) => {
  setBackendToken(null);
  try {
    await fetch(`${getApiBaseUrl()}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
      headers: { Accept: 'application/json' },
    });
  } catch {
    // Best-effort logout; local browser state is still cleared.
  }
  try {
    const auth = await getFirebaseAuthClient();
    if (auth?.currentUser) {
      await auth.signOut();
    }
  } catch {
    // Best-effort sign out.
  }
  // Clear local storage and redirect
  localStorage.removeItem(BACKEND_TOKEN_KEY);
  if (notify) {
    notifyAuthSessionChanged();
  }
  // Navigate to login page using React Router instead of window.location
  window.location.href = window.location.origin + '/login';
};

export const notifyAuthLogin = () => {
  notifyAuthSessionChanged();
};
