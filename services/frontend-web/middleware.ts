import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const MARKETING_DOMAIN = 'https://rereflect.ca';
const landingRoutes = ['/privacy', '/terms', '/changelog'];

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  if (process.env.NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW === 'true' &&
      (pathname === '/' || pathname === '/dashboard' || pathname === '/signup')) {
    return NextResponse.redirect(new URL('/ask-genius', request.url));
  }

  // Skip middleware for static files and API routes
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname.includes('.')
  ) {
    return NextResponse.next();
  }

  // Redirect landing routes to marketing domain
  if (landingRoutes.some(route => pathname.startsWith(route))) {
    return NextResponse.redirect(new URL(pathname, MARKETING_DOMAIN));
  }

  // Redirect root to dashboard
  if (pathname === '/') {
    return NextResponse.redirect(new URL('/dashboard', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
