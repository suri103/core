import { useEffect, useState } from 'react';

/**
 * Reads a single-use credential (password reset, email verification, staff
 * invitation) from the URL and immediately removes it from the address bar.
 *
 * Audit finding H-11: these tokens were delivered as query parameters
 * (`/reset-password?token=...`). A query string is sent to the server on every
 * navigation, so the token ends up in web-server and proxy access logs, in
 * analytics page-view payloads, and in the `Referer` header of any subsequent
 * outbound request from that page. Any of those is a credential leak.
 *
 * The fragment (`/reset-password#token=...`) is never transmitted to a server,
 * so it cannot appear in server or proxy logs, analytics URLs, or referrers.
 * That is the same reasoning behind the OAuth implicit flow returning tokens
 * in the fragment.
 *
 * Two further mitigations here:
 *  - the fragment is stripped from the URL as soon as it is read, via
 *    `history.replaceState`, so it does not linger in the address bar or get
 *    captured by a later history entry;
 *  - the query parameter is still accepted as a fallback (older emails are
 *    already in inboxes) but is likewise stripped immediately, and its use is
 *    reported so the legacy path is observable.
 *
 * The token remains in the value returned here for the lifetime of the
 * component, which is what the submit handler needs. It is sent in the request
 * *body*, never in a URL.
 */
export interface OneTimeToken {
  /** The token, or null when the link carried none. */
  token: string | null;
  /** True when the token arrived as a query parameter rather than a fragment. */
  fromLegacyQueryParam: boolean;
}

function parseFragment(hash: string, key: string): string | null {
  // Accept both "#token=abc" and "#/path?token=abc" shapes.
  const raw = hash.startsWith('#') ? hash.slice(1) : hash;
  if (!raw) return null;
  const queryStart = raw.indexOf('?');
  const search = queryStart >= 0 ? raw.slice(queryStart + 1) : raw;
  const value = new URLSearchParams(search).get(key);
  return value && value.length > 0 ? value : null;
}

export function useOneTimeToken(key = 'token'): OneTimeToken {
  const [result] = useState<OneTimeToken>(() => {
    if (typeof window === 'undefined') {
      return { token: null, fromLegacyQueryParam: false };
    }
    const fromFragment = parseFragment(window.location.hash, key);
    if (fromFragment) {
      return { token: fromFragment, fromLegacyQueryParam: false };
    }
    const fromQuery = new URLSearchParams(window.location.search).get(key);
    return {
      token: fromQuery && fromQuery.length > 0 ? fromQuery : null,
      fromLegacyQueryParam: Boolean(fromQuery),
    };
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !result.token) return;
    // Scrub the credential from the visible URL and from this history entry.
    const url = new URL(window.location.href);
    url.hash = '';
    url.searchParams.delete(key);
    window.history.replaceState(window.history.state, '', url.toString());
  }, [result.token, key]);

  return result;
}
