import { getFirebaseAuthClient } from './firebaseClient';

export const BACKEND_TOKEN_KEY = 'token';

// Legacy in-memory token support for transitional flows.
let legacyBackendToken: string | null = null;

const getApiBaseUrl = (): string =>
  String(import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE || 'http://localhost:8010')
    .trim()
    .replace(/\/+$/, '');

export const getBackendToken = (): string | null => legacyBackendToken;

export const setBackendToken = (token: string | null) => {
  legacyBackendToken = token || null;
  // Always clear old persistent token storage.
  localStorage.removeItem(BACKEND_TOKEN_KEY);
};

const notifyAuthSessionChanged = () => {
  window.dispatchEvent(new Event('auth-session-changed'));
};

export const clearAuthSession = async () => {
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
  notifyAuthSessionChanged();
};

export const notifyAuthLogin = () => {
  notifyAuthSessionChanged();
};
