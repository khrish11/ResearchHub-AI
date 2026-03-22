import { initializeApp, getApp, getApps, type FirebaseApp } from 'firebase/app';
import {
  browserLocalPersistence,
  getAuth,
  GoogleAuthProvider,
  setPersistence,
  type Auth,
} from 'firebase/auth';
import { initializeAppCheck, ReCaptchaEnterpriseProvider, ReCaptchaV3Provider, getToken as getAppCheckToken, type AppCheck } from 'firebase/app-check';
import { getAnalytics, isSupported as analyticsSupported, logEvent as firebaseLogEvent, type Analytics } from 'firebase/analytics';
import { getPerformance } from 'firebase/performance';
import { fetchAndActivate, getBoolean, getRemoteConfig, getString, type RemoteConfig } from 'firebase/remote-config';
import { getMessaging, getToken as getMessagingToken, isSupported as messagingSupported, onMessage, type Messaging } from 'firebase/messaging';
import { COOKIE_CONSENT_EVENT, hasOptionalTelemetryConsent } from './consent';

type RemoteConfigDefaults = Record<string, string>;

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
};

const remoteDefaults: RemoteConfigDefaults = {
  feature_firebase_auth: 'true',
  feature_browser_notifications: 'false',
  ui_density_default: 'regular',
  onboarding_variant: 'control',
  default_chat_model: '',
  default_pipeline_model: '',
};

const hasFirebaseConfig = [
  firebaseConfig.apiKey,
  firebaseConfig.authDomain,
  firebaseConfig.projectId,
  firebaseConfig.storageBucket,
  firebaseConfig.messagingSenderId,
  firebaseConfig.appId,
].every(Boolean);

let app: FirebaseApp | null = null;
let auth: Auth | null = null;
let googleProvider: GoogleAuthProvider | null = null;
let analytics: Analytics | null = null;
let performance: object | null = null;
let remoteConfig: RemoteConfig | null = null;
let messaging: Messaging | null = null;
let appCheck: AppCheck | null = null;
let telemetryBootstrapped = false;
let remoteConfigBootstrapped = false;

const isBrowser = typeof window !== 'undefined';

const appCheckSiteKey = (
  import.meta.env.VITE_FIREBASE_APPCHECK_SITE_KEY ||
  import.meta.env.VITE_FIREBASE_RECAPTCHA_ENTERPRISE_SITE_KEY ||
  import.meta.env.VITE_FIREBASE_RECAPTCHA_V3_SITE_KEY ||
  ''
).trim();

const appCheckUsesEnterprise = (import.meta.env.VITE_FIREBASE_APPCHECK_PROVIDER || 'enterprise').trim().toLowerCase() !== 'recaptcha-v3';

const messagingVapidKey = (import.meta.env.VITE_FIREBASE_MESSAGING_VAPID_KEY || '').trim();

export const isFirebaseClientConfigured = (): boolean => hasFirebaseConfig;

export const isFirebaseAuthEnabled = (): boolean =>
  hasFirebaseConfig && (import.meta.env.VITE_FIREBASE_AUTH_ENABLED || '1').trim() !== '0';

export const isBrowserNotificationsEnabled = (): boolean =>
  hasFirebaseConfig && (import.meta.env.VITE_FIREBASE_MESSAGING_ENABLED || '1').trim() !== '0';

export const getFirebaseAppClient = (): FirebaseApp | null => {
  if (!hasFirebaseConfig || !isBrowser) {
    return null;
  }
  if (!app) {
    app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  }
  return app;
};

export const getFirebaseAuthClient = async (): Promise<Auth | null> => {
  const firebaseApp = getFirebaseAppClient();
  if (!firebaseApp) {
    return null;
  }
  if (!auth) {
    auth = getAuth(firebaseApp);
    try {
      const persistPromise = setPersistence(auth, browserLocalPersistence);
      const timeoutPromise = new Promise((_, reject) => setTimeout(() => reject(new Error('Persistence timeout')), 1000));
      await Promise.race([persistPromise, timeoutPromise]);
    } catch {
      // Ignore persistence failures (e.g. strict browser blocking IndexedDB).
    }
  }
  return auth;
};

export const getFirebaseGoogleProvider = (): GoogleAuthProvider | null => {
  if (!isFirebaseAuthEnabled()) {
    return null;
  }
  if (!googleProvider) {
    googleProvider = new GoogleAuthProvider();
    googleProvider.setCustomParameters({ prompt: 'select_account' });
  }
  return googleProvider;
};

const ensureRemoteConfig = async (): Promise<RemoteConfig | null> => {
  const firebaseApp = getFirebaseAppClient();
  if (!firebaseApp || remoteConfigBootstrapped) {
    return remoteConfig;
  }
  remoteConfigBootstrapped = true;
  try {
    remoteConfig = getRemoteConfig(firebaseApp);
    remoteConfig.settings = {
      minimumFetchIntervalMillis: 15 * 60 * 1000,
      fetchTimeoutMillis: 7000,
    };
    remoteConfig.defaultConfig = remoteDefaults;
    await fetchAndActivate(remoteConfig);
  } catch {
    // Keep defaults if remote fetch fails.
  }
  return remoteConfig;
};

const ensureAppCheck = (): AppCheck | null => {
  const firebaseApp = getFirebaseAppClient();
  if (!firebaseApp || !appCheckSiteKey || appCheck) {
    return appCheck;
  }
  const provider = appCheckUsesEnterprise
    ? new ReCaptchaEnterpriseProvider(appCheckSiteKey)
    : new ReCaptchaV3Provider(appCheckSiteKey);
  appCheck = initializeAppCheck(firebaseApp, {
    provider,
    isTokenAutoRefreshEnabled: true,
  });
  return appCheck;
};

const maybeEnableTelemetry = async () => {
  const firebaseApp = getFirebaseAppClient();
  if (!firebaseApp || !hasOptionalTelemetryConsent()) {
    return;
  }
  if (!analytics) {
    try {
      if (await analyticsSupported()) {
        analytics = getAnalytics(firebaseApp);
      }
    } catch {
      analytics = null;
    }
  }
  if (!performance) {
    try {
      performance = getPerformance(firebaseApp);
    } catch {
      performance = null;
    }
  }
};

export const bootstrapGoogleServices = async (): Promise<void> => {
  if (!isBrowser || telemetryBootstrapped) {
    return;
  }
  telemetryBootstrapped = true;
  getFirebaseAppClient();
  ensureAppCheck();
  await ensureRemoteConfig();
  await maybeEnableTelemetry();
  window.addEventListener(COOKIE_CONSENT_EVENT, () => {
    void maybeEnableTelemetry();
  });
};

export const getRemoteBoolean = async (key: string, fallback = false): Promise<boolean> => {
  const rc = await ensureRemoteConfig();
  if (!rc) {
    return fallback;
  }
  try {
    return getBoolean(rc, key);
  } catch {
    return fallback;
  }
};

export const getRemoteStringValue = async (key: string, fallback = ''): Promise<string> => {
  const rc = await ensureRemoteConfig();
  if (!rc) {
    return fallback;
  }
  try {
    return getString(rc, key) || fallback;
  } catch {
    return fallback;
  }
};

export const getUiDensityDefault = async (): Promise<'regular' | 'minimal'> => {
  const value = (await getRemoteStringValue('ui_density_default', 'regular')).toLowerCase();
  return value === 'minimal' ? 'minimal' : 'regular';
};

export const logAnalyticsEvent = async (name: string, params?: Record<string, string | number | boolean>) => {
  await maybeEnableTelemetry();
  if (!analytics) {
    return;
  }
  firebaseLogEvent(analytics, name, params);
};

export const trackRouteView = async (path: string) => {
  const screenName = path || '/';
  await logAnalyticsEvent('screen_view', {
    firebase_screen: screenName,
    firebase_screen_class: 'route',
  });
};

export const getAppCheckTokenValue = async (): Promise<string | null> => {
  const instance = ensureAppCheck();
  if (!instance) {
    return null;
  }
  try {
    // Add a 2s timeout. Firebase App Check sometimes hangs indefinitely on localhost.
    const tokenPromise = getAppCheckToken(instance, false);
    const timeoutPromise = new Promise<{ token: string | null }>((_, reject) => 
      setTimeout(() => reject(new Error('AppCheck token fetch timed out')), 2000)
    );
    const token = await Promise.race([tokenPromise, timeoutPromise]);
    return token.token || null;
  } catch {
    return null;
  }
};

export const requestPushNotifications = async (): Promise<{ token: string | null; permission: NotificationPermission | 'unsupported' }> => {
  const firebaseApp = getFirebaseAppClient();
  if (!firebaseApp || !isBrowserNotificationsEnabled()) {
    return { token: null, permission: 'unsupported' };
  }
  if (!(await messagingSupported())) {
    return { token: null, permission: 'unsupported' };
  }
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    return { token: null, permission };
  }
  messaging = messaging || getMessaging(firebaseApp);
  const token = await getMessagingToken(messaging, {
    vapidKey: messagingVapidKey || undefined,
    serviceWorkerRegistration: await navigator.serviceWorker.register('/firebase-messaging-sw.js'),
  });
  return { token: token || null, permission };
};

export const registerForegroundNotificationHandler = async (
  callback: (payload: Record<string, unknown>) => void,
) => {
  const firebaseApp = getFirebaseAppClient();
  if (!firebaseApp || !isBrowserNotificationsEnabled()) {
    return () => undefined;
  }
  if (!(await messagingSupported())) {
    return () => undefined;
  }
  messaging = messaging || getMessaging(firebaseApp);
  return onMessage(messaging, (payload) => callback(payload as unknown as Record<string, unknown>));
};
