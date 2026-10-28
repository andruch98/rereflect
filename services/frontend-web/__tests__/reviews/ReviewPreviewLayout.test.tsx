import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReviewPreviewLayout } from '@/components/reviews/ReviewPreviewLayout';
const mocks = vi.hoisted(() => ({ get: vi.fn(), replace: vi.fn(), path: '/feedbacks' }));
vi.mock('@/lib/api-client', () => ({ default: { get: mocks.get } }));
vi.mock('next/navigation', () => ({ usePathname: () => mocks.path, useRouter: () => ({ replace: mocks.replace }) }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 1, organization_id: 11 }, logout: vi.fn() }) }));
afterEach(() => { cleanup(); vi.clearAllMocks(); mocks.path = '/feedbacks'; });
function mount() {
  window.matchMedia = vi.fn().mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() });
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><ReviewPreviewLayout><p>Authorized review content</p></ReviewPreviewLayout></QueryClientProvider>);
}
it('shows the authorized community and only the current milestone navigation', async () => {
  mocks.get.mockResolvedValue({ data: { organization_id: 11, name: 'Lake House Apartments' } });
  mount();
  await screen.findByText('Lake House Apartments');
  expect(screen.getByText('Authorized review content')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Reviews' })).toHaveAttribute('href', '/feedbacks');
  expect(screen.getByRole('link', { name: 'Ask Genius' })).toHaveAttribute('href', '/ask-genius');
  expect(screen.queryByText('AI Copilot')).not.toBeInTheDocument();
  expect(screen.queryByText('Churn Risks')).not.toBeInTheDocument();
});
it('does not render review children while community access is denied', async () => {
  mocks.get.mockRejectedValue(new Error('Forbidden'));
  mount();
  await screen.findByRole('alert');
  expect(screen.queryByText('Authorized review content')).not.toBeInTheDocument();
});
it('redirects unsupported dashboard sections without mounting their contents', async () => {
  mocks.path = '/conversations';
  mocks.get.mockResolvedValue({ data: { organization_id: 11, name: 'Lake House Apartments' } });
  mount();
  await screen.findByText('Lake House Apartments');
  expect(mocks.replace).toHaveBeenCalledWith('/ask-genius');
  expect(screen.queryByText('Authorized review content')).not.toBeInTheDocument();
});
