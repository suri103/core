// Shared reCAPTCHA v3 token helper (M-14).
// Extracted from PublicBooking.tsx so the patient portal and public booking
// both satisfy the backend's fail-closed CAPTCHA requirement when
// RECAPTCHA_SECRET_KEY is configured server-side.

interface RecaptchaV3 {
  ready: (cb: () => void) => void;
  execute: (siteKey: string, options: { action: string }) => Promise<string>;
}

const RECAPTCHA_SCRIPT_ID = 'coredent-recaptcha-v3';
let recaptchaLoader: Promise<RecaptchaV3> | undefined;

function getRecaptcha(): RecaptchaV3 | undefined {
  return (window as typeof window & { grecaptcha?: RecaptchaV3 }).grecaptcha;
}

export function loadRecaptcha(siteKey: string): Promise<RecaptchaV3> {
  const existingCaptcha = getRecaptcha();
  if (existingCaptcha) return Promise.resolve(existingCaptcha);
  if (recaptchaLoader) return recaptchaLoader;

  const loader = new Promise<RecaptchaV3>((resolve, reject) => {
    const resolveCaptcha = () => {
      const captcha = getRecaptcha();
      if (captcha) {
        resolve(captcha);
      } else {
        recaptchaLoader = undefined;
        reject(new Error('CAPTCHA could not be initialized. Please try again.'));
      }
    };

    const existingScript = document.getElementById(RECAPTCHA_SCRIPT_ID) as HTMLScriptElement | null;
    if (existingScript) {
      existingScript.addEventListener('load', resolveCaptcha, { once: true });
      existingScript.addEventListener('error', () => {
        recaptchaLoader = undefined;
        reject(new Error('CAPTCHA could not be loaded. Please try again.'));
      }, { once: true });
    } else {
      const script = document.createElement('script');
      script.id = RECAPTCHA_SCRIPT_ID;
      script.src = `https://www.google.com/recaptcha/api.js?render=${encodeURIComponent(siteKey)}`;
      script.async = true;
      script.addEventListener('load', resolveCaptcha, { once: true });
      script.addEventListener('error', () => {
        recaptchaLoader = undefined;
        reject(new Error('CAPTCHA could not be loaded. Please try again.'));
      }, { once: true });
      document.head.appendChild(script);
    }
  });

  recaptchaLoader = loader;
  return loader;
}

/**
 * Mint a one-time reCAPTCHA v3 token for the given action.
 * Throws a user-actionable error when the site key is missing so the caller
 * can surface a configuration problem instead of a doomed request.
 */
export async function getCaptchaToken(action: string): Promise<string | undefined> {
  const siteKey = import.meta.env.VITE_RECAPTCHA_SITE_KEY?.trim();
  if (!siteKey) {
    throw new Error(
      'This practice requires CAPTCHA verification, but this page is not configured for it. Please contact the practice.'
    );
  }

  const captcha = await loadRecaptcha(siteKey);
  const token = await new Promise<string>((resolve, reject) => {
    captcha.ready(() => {
      captcha.execute(siteKey, { action }).then(resolve).catch(reject);
    });
  });

  if (!token) {
    throw new Error('CAPTCHA verification did not return a token. Please try again.');
  }
  return token;
}
