# Security Audit Exceptions

This file documents dependency audit exceptions that are accepted for the SaaS build. Exceptions must be narrow, validated by CI, and removed when an applicable fixed release is available.

## React Router RSC advisory

- Advisory: `GHSA-qwww-vcr4-c8h2`
- Package: `react-router` via `react-router-dom`
- Status: Accepted only while CoreDent remains a browser-only SPA with no React Router RSC or server-router usage.
- CI control: `npm run audit:prod` allows this advisory only when `src/` contains no imports or symbols for React Router RSC/server APIs such as `react-router-dom/server`, `react-router/dom`, `createStaticRouter`, `StaticRouter`, `HydratedRouter`, `ServerRouter`, `RSCHydratedRouter`, or `unstable_*RSC*`.
- Review trigger: remove this exception when a stable React Router release clears the advisory without reintroducing the older client-side redirect advisories.
