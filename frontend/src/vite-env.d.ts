/// <reference types="vite/client" />

interface ImportMetaEnv {
  // Backend API
  readonly VITE_API_URL: string;
  readonly VITE_API_TIMEOUT_MS?: string;

  // Firebase Web SDK
  readonly VITE_FIREBASE_API_KEY: string;
  readonly VITE_FIREBASE_AUTH_DOMAIN: string;
  readonly VITE_FIREBASE_PROJECT_ID: string;
  readonly VITE_FIREBASE_STORAGE_BUCKET: string;
  readonly VITE_FIREBASE_MESSAGING_SENDER_ID: string;
  readonly VITE_FIREBASE_APP_ID: string;
  readonly VITE_FIREBASE_MEASUREMENT_ID?: string;

  // Firebase feature toggles
  readonly VITE_FIREBASE_AUTH_ENABLED?: string;
  readonly VITE_FIREBASE_APPCHECK_PROVIDER?: string;
  readonly VITE_FIREBASE_APPCHECK_SITE_KEY?: string;
  readonly VITE_FIREBASE_MESSAGING_VAPID_KEY?: string;

  // Error tracking
  readonly VITE_SENTRY_DSN?: string;

  // Payment (future)
  readonly VITE_RAZORPAY_KEY_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
