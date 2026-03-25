import {
  createUserWithEmailAndPassword,
  sendEmailVerification,
  signInWithEmailAndPassword,
  signInWithPopup,
  updateProfile,
} from 'firebase/auth';
import api from '../api';
import { getFirebaseAuthClient, getFirebaseGoogleProvider, isFirebaseAuthEnabled, logAnalyticsEvent } from './firebaseClient';

interface FirebaseSessionResponse {
  access_token: string;
  token_type: string;
  user: {
    email: string;
    name?: string | null;
    is_verified?: boolean;
    google_linked?: boolean;
  };
}

const exchangeFirebaseSession = async (idToken: string) => {
  console.log('Exchanging Firebase session with token:', idToken.substring(0, 20) + '...');
  const response = await api.post<FirebaseSessionResponse>('/auth/firebase/session', {
    id_token: idToken,
  });
  console.log('Firebase session exchange response:', response);
  await logAnalyticsEvent('login', { method: 'firebase' });
  return response.data;
};

export const firebaseAuthAvailable = (): boolean => isFirebaseAuthEnabled();

const extractFirebaseErrorCode = (err: unknown): string => {
  const maybeCode = (err as { code?: unknown } | null)?.code;
  return typeof maybeCode === 'string' ? maybeCode.toLowerCase() : '';
};

export const isFirebaseUnauthorizedDomainError = (err: unknown): boolean => {
  const code = extractFirebaseErrorCode(err);
  if (code === 'auth/unauthorized-domain') {
    return true;
  }
  const message = err instanceof Error ? err.message.toLowerCase() : '';
  return message.includes('auth/unauthorized-domain') || message.includes('unauthorized-domain');
};

export const signInWithFirebasePassword = async (email: string, password: string) => {
  console.log('Firebase password sign-in attempt:', email);
  const auth = await getFirebaseAuthClient();
  if (!auth) {
    throw new Error('Firebase Authentication is not configured.');
  }
  const credential = await signInWithEmailAndPassword(auth, email, password);
  console.log('Firebase credential received:', credential.user.email);
  const idToken = await credential.user.getIdToken(true);
  console.log('Firebase ID token generated');
  return exchangeFirebaseSession(idToken);
};

export const registerWithFirebasePassword = async (email: string, password: string, name?: string) => {
  const auth = await getFirebaseAuthClient();
  if (!auth) {
    throw new Error('Firebase Authentication is not configured.');
  }
  const credential = await createUserWithEmailAndPassword(auth, email, password);
  if (name) {
    await updateProfile(credential.user, { displayName: name });
  }
  if (!credential.user.emailVerified) {
    try {
      await sendEmailVerification(credential.user);
    } catch {
      // Do not block sign-up on verification email delivery.
    }
  }
  const idToken = await credential.user.getIdToken(true);
  return exchangeFirebaseSession(idToken);
};

export const signInWithFirebaseGoogle = async (): Promise<FirebaseSessionResponse> => {
  const auth = await getFirebaseAuthClient();
  const provider = getFirebaseGoogleProvider();
  if (!auth || !provider) {
    throw new Error('Firebase Google sign-in is not configured.');
  }
  // Use popup so the result is available immediately — no redirect-state
  // management or session-storage dependency required.
  const result = await signInWithPopup(auth, provider);
  const idToken = await result.user.getIdToken(true);
  return exchangeFirebaseSession(idToken);
};

// Kept for backwards compatibility — handles the case where a user was
// mid-flight on the old redirect flow (e.g., during an app upgrade).
// With the popup flow this will almost always return null immediately.
export const handleFirebaseRedirectResult = async (): Promise<FirebaseSessionResponse | null> => {
  const auth = await getFirebaseAuthClient();
  if (!auth) {
    return null;
  }
  // Check if there is a currently signed-in user (from popup flow on this session)
  if (auth.currentUser) {
    try {
      const idToken = await auth.currentUser.getIdToken(true);
      return await exchangeFirebaseSession(idToken);
    } catch {
      // Not a hard error — fall through and let the app check cookies normally.
      return null;
    }
  }
  return null;
};
