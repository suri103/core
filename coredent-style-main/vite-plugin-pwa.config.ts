import { VitePWA } from 'vite-plugin-pwa';

export const pwaConfig = VitePWA({
  registerType: 'prompt',
  includeAssets: ['favicon.ico', 'favicon.svg', 'robots.txt'],
  manifest: {
    name: 'CoreDent - Dental Practice Management',
    short_name: 'CoreDent',
    description: 'Comprehensive dental practice management system',
    theme_color: '#3b82f6',
    background_color: '#ffffff',
    display: 'standalone',
    orientation: 'portrait',
    scope: '/',
    start_url: '/',
    icons: [
      {
        src: 'favicon.svg',
        sizes: '192x192',
        type: 'image/svg+xml',
      },
      {
        src: 'favicon.svg',
        sizes: '512x512',
        type: 'image/svg+xml',
      },
    ],
  },
  workbox: {
    navigateFallbackDenylist: [/^\/api\//],
    globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
    runtimeCaching: [
      {
        // Never persist authenticated API responses (which may contain PHI)
        // in Cache Storage. This applies to same-origin and cross-origin APIs.
        urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
        handler: 'NetworkOnly',
        options: {
          cacheName: 'api-network-only',
        },
      },
      {
        urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
        handler: 'CacheFirst',
        options: {
          cacheName: 'google-fonts-cache',
          expiration: {
            maxEntries: 10,
            maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
          },
        },
      },
    ],
  },
  devOptions: {
    enabled: false, // Disable in production build
    type: 'module',
  },
});
