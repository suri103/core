// ============================================
// CoreDent PMS - Email Verification Page
// Verifies the account email via a token that
// arrived in the confirmation email link.
// ============================================

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Loader2, CheckCircle, MailCheck, XCircle, Stethoscope } from 'lucide-react';
import { authApi } from '@/services/api';
import { useToast } from '@/hooks/use-toast';
import { useOneTimeToken } from '@/hooks/useOneTimeToken';

type VerifyState = 'verifying' | 'success' | 'error';

export default function VerifyEmail() {
  // M-11 FIX: the email link now ships the code as `?code=…` (query
  // string) instead of `#token=…` (fragment). ``useOneTimeToken`` accepts
  // either and scrubs both from the address bar immediately, so the
  // server never sees the plaintext credential and the token never
  // lingers in browser history.
  const { token } = useOneTimeToken('code');
  const [state, setState] = useState<VerifyState>(token ? 'verifying' : 'error');
  const [message, setMessage] = useState<string>(
    token ? '' : 'This verification link is invalid or has expired.',
  );
  const { toast } = useToast();

  useEffect(() => {
    let cancelled = false;

    async function verify() {
      if (!token) return;
      setState('verifying');
      try {
        // Token is sent in the request body (never in the URL), keeping it
        // out of proxy/access logs.
        const response = await authApi.verifyEmail(token);
        if (cancelled) return;
        if (response.success) {
          setState('success');
          toast({
            title: 'Email Verified',
            description: 'Your email address has been verified successfully.',
          });
        } else {
          setState('error');
          setMessage(response.error?.message || 'This verification link is invalid or has expired.');
        }
      } catch {
        if (cancelled) return;
        setState('error');
        setMessage('Unable to verify your email right now. Please try again later.');
      }
    }

    verify();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-muted/30 p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary mb-4">
            <Stethoscope className="h-8 w-8 text-primary-foreground" />
          </div>
          <h1 className="text-3xl font-bold">CoreDent</h1>
          <p className="text-muted-foreground">Dental Practice Management</p>
        </div>

        <Card className="shadow-lg">
          <CardContent className="pt-6">
            <div className="flex flex-col items-center text-center space-y-4">
              {state === 'verifying' && (
                <>
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                    <Loader2 className="h-8 w-8 animate-spin text-primary" />
                  </div>
                  <h2 className="text-2xl font-semibold">Verifying your email…</h2>
                  <p className="text-muted-foreground">
                    Please wait while we confirm your email address.
                  </p>
                </>
              )}

              {state === 'success' && (
                <>
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
                    <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
                  </div>
                  <h2 className="text-2xl font-semibold">Email Verified</h2>
                  <p className="text-muted-foreground">
                    Your email address has been verified successfully. You can now sign in.
                  </p>
                </>
              )}

              {state === 'error' && (
                <>
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10">
                    {token ? (
                      <XCircle className="h-8 w-8 text-destructive" />
                    ) : (
                      <MailCheck className="h-8 w-8 text-destructive" />
                    )}
                  </div>
                  <h2 className="text-2xl font-semibold">Verification Failed</h2>
                  <p className="text-muted-foreground">{message}</p>
                </>
              )}
            </div>
          </CardContent>
          <CardFooter>
            <Link to="/login" className="w-full">
              <Button className="w-full" size="lg" disabled={state === 'verifying'}>
                Go to Sign In
              </Button>
            </Link>
          </CardFooter>
        </Card>

        <p className="text-center text-sm text-muted-foreground mt-6">
          © 2025 CoreDent PMS. All rights reserved.
        </p>
      </div>
    </div>
  );
}
