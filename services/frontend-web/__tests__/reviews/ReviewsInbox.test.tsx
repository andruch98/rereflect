import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReviewsInbox } from '@/components/reviews/ReviewsInbox';
import { ReviewDetail } from '@/components/reviews/ReviewDetail';
import type { FeedbackItem } from '@/lib/api/feedback';

const mocks = vi.hoisted(() => ({ list: vi.fn(), get: vi.fn(), user: { id: 1, organization_id: 11 } }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: mocks.user }) }));
vi.mock('@/lib/api/feedback', () => ({ feedbackAPI: { list: mocks.list, get: mocks.get } }));

const ratingOnly = { id: 6, organization_id: 11, text: '', source: 'apartment_review_ai', star_rating: 4,
  sentiment_label: 'positive', apartment_analysis: { final_result: { method: 'ai_model', sentiment: 'positive', topics: [] } },
} as FeedbackItem;

function mount(component: React.ReactNode, client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
  return { ...render(<QueryClientProvider client={client}>{component}</QueryClientProvider>), client };
}
afterEach(() => { cleanup(); vi.clearAllMocks(); });

describe('review inbox and detail', () => {
  it('displays a rating-only review accurately, uses a keyboard-accessible detail link, and omits software risk columns', async () => {
    mocks.list.mockResolvedValue({ items: [ratingOnly], total: 1, total_pages: 1 });
    mount(<ReviewsInbox />);
    expect(await screen.findByText('Rating only — no written review')).toBeInTheDocument();
    expect(screen.getByLabelText('4 out of 5 stars')).toBeInTheDocument();
    expect(screen.getByText('Imported review')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Review #6' })).toHaveAttribute('href', '/feedbacks/6');
    expect(screen.queryByText(/Churn|Normal|Urgency/)).not.toBeInTheDocument();
  });

  it('sends search, Mixed filter, sorting and pagination to the API instead of sorting just the current page', async () => {
    mocks.list.mockResolvedValue({ items: [ratingOnly], total: 40, total_pages: 2 });
    mount(<ReviewsInbox />);
    await screen.findByRole('link', { name: 'Review #6' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Filter by overall sentiment' }), { target: { value: 'mixed' } });
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(1, 20, expect.objectContaining({ sentiment: 'mixed' })));
    fireEvent.change(await screen.findByRole('textbox', { name: 'Search review text…' }), { target: { value: 'pool' } });
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(1, 20, expect.objectContaining({ search: 'pool', sentiment: 'mixed' })));
    fireEvent.click(await screen.findByRole('button', { name: 'Stars' }));
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(1, 20, expect.objectContaining({ sort_by: 'star_rating' })));
    fireEvent.click(await screen.findByRole('button', { name: 'Next' }));
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(2, 20, expect.objectContaining({ sort_by: 'star_rating' })));
  });

  it('reports a request failure without claiming there are no reviews', async () => {
    mocks.list.mockRejectedValue(new Error('offline'));
    mount(<ReviewsInbox />);
    expect(await screen.findByRole('alert')).toHaveTextContent('Reviews could not be loaded');
    expect(screen.queryByText('No reviews found')).not.toBeInTheDocument();
  });

  it('does not reuse another account’s cached inbox', async () => {
    mocks.list.mockResolvedValue({ items: [], total: 0, total_pages: 0 });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    client.setQueryData(['boomsay-reviews', 99, 99, 1, 20, { sort_by: 'id', sort_order: 'asc' }], { items: [ratingOnly], total: 1, total_pages: 1 });
    mount(<ReviewsInbox />, client);
    await screen.findByText('No reviews found');
    expect(screen.queryByText('Review #6')).not.toBeInTheDocument();
  });

  it('opens the saved detail with stars and no fabricated topics', async () => {
    mocks.get.mockResolvedValue(ratingOnly);
    mount(<ReviewDetail id={6} />);
    expect(await screen.findByRole('heading', { name: 'Review #6' })).toBeInTheDocument();
    expect(screen.getByLabelText('4 out of 5 stars')).toBeInTheDocument();
    expect(screen.getByText(/No written review was provided/)).toBeInTheDocument();
    expect(mocks.get).toHaveBeenCalledWith(6);
  });
});
