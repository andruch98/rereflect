import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SharedGeniusChat } from '@/components/reviews/SharedGeniusChat';

const { shared, privateReview } = vi.hoisted(() => ({ shared: vi.fn(), privateReview: vi.fn() }));
vi.mock('@/lib/api/ask-genius', () => ({ askGeniusAPI: { shared } }));
vi.mock('@/lib/api/feedback', () => ({ feedbackAPI: { get: privateReview } }));
vi.mock('@/components/reviews/BoomSayLogo', () => ({ BoomSayLogo: () => <span>BoomSay</span> }));
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><SharedGeniusChat token="public-snapshot-token" /></QueryClientProvider>);
}
beforeEach(() => vi.clearAllMocks());
afterEach(cleanup);

it('shows only the shared snapshot without sign-in, a private sidebar or a composer', async () => {
  shared.mockResolvedValue({ title: 'Repair concerns', created_at: '2026-10-28T12:00:00Z', messages: [
    { id: 1, role: 'user', content: 'What were the complaints?', created_at: '', structured_data: null },
    { id: 2, role: 'assistant', content: 'Residents reported repair delays.', created_at: '', structured_data: { kind: 'ask_genius', sources: [{ review_id: 1, excerpt: 'We waited for a repair.', review: { original_review: 'We waited for a repair. No update arrived.', star_rating: 1, saved_analysis: { status: 'missing' } } }] } },
  ] });
  mount();
  expect(await screen.findByRole('heading', { name: 'Repair concerns' })).toBeInTheDocument();
  expect(screen.getByText('Residents reported repair delays.')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /We waited for a repair.*Open review/ })).toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'New chat' })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Sign in/ })).not.toBeInTheDocument();
  expect(shared).toHaveBeenCalledWith('public-snapshot-token');
  expect(privateReview).not.toHaveBeenCalled();
});

it('shows a generic error without exposing backend details or redirecting to sign-in', async () => {
  shared.mockRejectedValue({ response: { status: 404, data: { detail: 'PRIVATE_ROW_DETAIL' } } });
  mount();
  expect(await screen.findByRole('alert')).toHaveTextContent('This shared chat is unavailable');
  expect(screen.queryByText(/PRIVATE_ROW_DETAIL/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  expect(privateReview).not.toHaveBeenCalled();
});
