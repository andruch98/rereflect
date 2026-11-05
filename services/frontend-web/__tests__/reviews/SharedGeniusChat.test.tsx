import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SharedGeniusChat } from '@/components/reviews/SharedGeniusChat';
import userEvent from '@testing-library/user-event';

const { shared, privateReview, privateSurvey } = vi.hoisted(() => ({ shared: vi.fn(), privateReview: vi.fn(), privateSurvey: vi.fn() }));
vi.mock('@/lib/api/ask-genius', () => ({ askGeniusAPI: { shared } }));
vi.mock('@/lib/api/feedback', () => ({ feedbackAPI: { get: privateReview } }));
vi.mock('@/lib/api/surveys', async importOriginal => ({ ...await importOriginal<object>(), surveysAPI: { get: privateSurvey } }));
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
  expect(screen.getByRole('button', { name: 'View review' })).toBeInTheDocument();
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

it('opens shared survey answers and expands the same submission without private requests', async () => {
  const user = userEvent.setup();
  shared.mockResolvedValue({ title: 'Survey concerns', created_at: '', messages: [
    { id: 1, role: 'assistant', content: '- **Maintenance:** A leak remains unresolved.', created_at: '',
      structured_data: { kind: 'ask_genius', sources: [{ source: 'survey', kind: 'survey',
        survey_id: '00000000-0000-4000-8000-000000000001', topic: 'Maintenance', question_id: 'resolution',
        survey: { title: 'Maintenance feedback', survey_type_label: 'Maintenance', questions: [
          { id: 'resolution', text: 'Is the issue resolved?', answer_label: 'No, still unresolved' },
          { id: 'comment', text: 'Anything else?', answer_label: 'Water near the door.' },
        ] } }] } },
  ] });
  mount();
  await user.click(await screen.findByRole('button', { name: 'View original answers' }));
  expect(screen.getByText('Is the issue resolved?')).toBeInTheDocument();
  expect(screen.getByText('No, still unresolved')).toBeInTheDocument();
  expect(screen.queryByText('Water near the door.')).not.toBeInTheDocument();
  await user.click(screen.getByRole('button', { name: 'View all answers from this survey' }));
  expect(screen.getByText('Water near the door.')).toBeInTheDocument();
  expect(privateSurvey).not.toHaveBeenCalled();
  expect(privateReview).not.toHaveBeenCalled();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
});

it('does not fetch private survey records when shared answers are missing', async () => {
  const user = userEvent.setup();
  shared.mockResolvedValue({ title: 'Incomplete snapshot', created_at: '', messages: [
    { id: 1, role: 'assistant', content: 'A survey finding.', created_at: '', structured_data: {
      kind: 'ask_genius', sources: [{ source: 'survey', kind: 'survey', survey_id: '00000000-0000-4000-8000-000000000001' }],
    } },
  ] });
  mount();
  await user.click(await screen.findByRole('button', { name: 'View original answers' }));
  expect(screen.getByText('The original answers were not included in this shared chat.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Reload answers' })).not.toBeInTheDocument();
  expect(privateSurvey).not.toHaveBeenCalled();
});
