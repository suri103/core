/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />
import '@testing-library/jest-dom/vitest';

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL: string;
  readonly VITE_RECAPTCHA_SITE_KEY?: string;
  readonly VITE_DEV_BYPASS_AUTH: string;
  readonly MODE: string;
  readonly PROD: boolean;
  readonly DEV: boolean;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
