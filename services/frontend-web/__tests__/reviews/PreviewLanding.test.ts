import { afterEach, expect, it, vi } from 'vitest';
import type { NextRequest } from 'next/server';
import { middleware } from '@/middleware';

vi.mock('next/server', () => ({ NextResponse: {
  redirect: (url: URL) => ({ location: url.toString() }),
  next: () => ({ next: true }),
} }));
afterEach(() => vi.unstubAllEnvs());

function request(pathname: string) {
  return { nextUrl: { pathname }, url: `http://localhost:53004${pathname}` } as NextRequest;
}

it.each(['/', '/dashboard', '/signup'])('opens Ask Genius from preview entry %s', pathname => {
  vi.stubEnv('NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW', 'true');
  expect(middleware(request(pathname))).toEqual({ location: 'http://localhost:53004/ask-genius' });
});

it('keeps direct review links and Ask Genius available', () => {
  vi.stubEnv('NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW', 'true');
  for (const path of ['/feedbacks', '/feedbacks/1', '/ask-genius']) {
    expect(middleware(request(path))).toEqual({ next: true });
  }
});

it('preserves the upstream landing when the preview is disabled', () => {
  vi.stubEnv('NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW', 'false');
  expect(middleware(request('/'))).toEqual({ location: 'http://localhost:53004/dashboard' });
  expect(middleware(request('/dashboard'))).toEqual({ next: true });
});
