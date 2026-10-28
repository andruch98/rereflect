import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { AuthProvider } from '@/contexts/AuthContext';

const mocks = vi.hoisted(() => ({ push: vi.fn(), getMe: vi.fn(), pathname: '/share/ask-genius/public-token' }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: mocks.push }), usePathname: () => mocks.pathname }));
vi.mock('@/lib/api/auth', () => ({ authAPI: { getMe: mocks.getMe } }));
vi.mock('@/lib/analytics', () => ({ identifyUser: vi.fn(), analytics: { logout: vi.fn() } }));
afterEach(() => { cleanup(); localStorage.clear(); vi.clearAllMocks(); mocks.pathname = '/share/ask-genius/public-token'; });

it('renders a public snapshot without a token or login redirect', async () => {
  render(<AuthProvider><p>Shared chat content</p></AuthProvider>);
  expect(await screen.findByText('Shared chat content')).toBeInTheDocument();
  expect(mocks.push).not.toHaveBeenCalled(); expect(mocks.getMe).not.toHaveBeenCalled();
});
it('still renders a public snapshot when an existing account token is expired', async () => {
  localStorage.setItem('access_token', 'expired'); mocks.getMe.mockRejectedValue(new Error('expired'));
  render(<AuthProvider><p>Shared chat content</p></AuthProvider>);
  expect(await screen.findByText('Shared chat content')).toBeInTheDocument();
  await waitFor(() => expect(localStorage.getItem('access_token')).toBeNull());
  expect(mocks.push).not.toHaveBeenCalled();
});
it('continues protecting private chat routes', async () => {
  mocks.pathname = '/ask-genius';
  render(<AuthProvider><p>Private content</p></AuthProvider>);
  await waitFor(() => expect(mocks.push).toHaveBeenCalledWith('/login'));
});
