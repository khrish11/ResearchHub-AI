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
  const response = await api.post<FirebaseSessionResponse>('/auth/firebase/session', {
    id_token: idToken,
  });
  await logAnalyticsEvent('login', { method: 'firebase' });
  return response.data;
};

export const firebaseAuthAvailable = (): boolean => isFirebaseAuthEnabled();

export const signInWithFirebasePassword = async (email: string, password: string) => {
  const auth = await getFirebaseAuthClient();
  if (!auth) {
    throw new Error('Firebase Authentication is not configured.');
  }
  const credential = await signInWithEmailAndPassword(auth, email, password);
  const idToken = await credential.user.getIdToken(true);
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

export const signInWithFirebaseGoogle = async () => {
  const auth = await getFirebaseAuthClient();
  const provider = getFirebaseGoogleProvider();
  if (!auth || !provider) {
    throw new Error('Firebase Google sign-in is not configured.');
  }
  const credential = await signInWithPopup(auth, provider);
  const idToken = await credential.user.getIdToken(true);
  return exchangeFirebaseSession(idToken);
};
