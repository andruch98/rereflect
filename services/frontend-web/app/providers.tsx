'use client';

import { useEffect } from 'react';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { AuthProvider } from '@/contexts/AuthContext';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { QueryProvider } from '@/components/providers/QueryProvider';
import { initAnalytics } from '@/lib/analytics';
import { usePathname } from 'next/navigation';

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;

export function Providers({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  // Initialize Mixpanel analytics
  useEffect(() => {
    initAnalytics();
  }, []);
  // A resident capability link does not need an account or OAuth provider.
  if (pathname.startsWith('/survey/')) return <QueryProvider><ThemeProvider>{children}</ThemeProvider></QueryProvider>;
  const content = (
    <QueryProvider>
      <ThemeProvider>
        <AuthProvider>
          {children}
        </AuthProvider>
      </ThemeProvider>
    </QueryProvider>
  );

  // Only wrap with GoogleOAuthProvider if client ID is configured
  if (GOOGLE_CLIENT_ID) {
    return (
      <GoogleOAuthProvider clientId={GOOGLE_CLIENT_ID}>
        {content}
      </GoogleOAuthProvider>
    );
  }

  return content;
}
