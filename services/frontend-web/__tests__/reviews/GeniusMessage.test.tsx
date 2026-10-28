import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { GeniusMessage } from '@/components/reviews/GeniusMessage';
import type { ChatMessage } from '@/components/copilot/ChatArea';

const { get, writeText } = vi.hoisted(() => ({ get: vi.fn(), writeText: vi.fn() }));
vi.mock('@/lib/api/feedback', () => ({ feedbackAPI: { get } }));

const original = 'The team ignored my calls. I called three times about the repair.';
const source = {
  review_id: 7, excerpt: 'The team ignored my calls.',
  review: { original_review: original, star_rating: 1, saved_analysis: {
    status: 'available', method: 'ai_model', sentiment: 'negative',
    topics: [{ name: 'Staff & customer service', sentiment: 'negative', quotations: [{ text: 'The team ignored my calls.', sentiment: 'negative' }] }],
  } },
};
function show(content = 'Residents reported communication concerns.', data: ChatMessage['structured_data'] = { kind: 'ask_genius', sources: [source] }, publicSnapshot = false) {
  return render(<GeniusMessage message={{ id: 1, role: 'assistant', content, created_at: '', structured_data: data }} publicSnapshot={publicSnapshot} />);
}
beforeEach(() => {
  vi.clearAllMocks();
  writeText.mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
});
afterEach(cleanup);

describe('Ask Genius review excerpts', () => {
  it('opens a snapshot review without fetching and expands saved analysis on demand', async () => {
    show();
    fireEvent.click(screen.getByRole('button', { name: 'View review' }));
    const modal = screen.getByRole('dialog');
    expect(within(modal).getByText(original)).toBeInTheDocument();
    expect(within(modal).getByRole('heading', { name: 'Review' })).toBeInTheDocument();
    expect(within(modal).queryByText(/Review #7/)).not.toBeInTheDocument();
    expect(within(modal).queryByRole('region', { name: 'Staff & customer service' })).not.toBeInTheDocument();
    fireEvent.click(within(modal).getByRole('button', { name: /Saved analysis/ }));
    expect(within(modal).getByRole('region', { name: 'Staff & customer service' })).toBeInTheDocument();
    fireEvent.click(within(modal).getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();
  });

  it('keeps legacy saved string quotations unlabeled', () => {
    const legacy = { ...source, review: { ...source.review, saved_analysis: { ...source.review.saved_analysis, topics: [{ name: 'Staff', sentiment: 'negative', quotations: [{ text: 'The team ignored my calls.', sentiment: 'unlabeled' }] }] } } };
    show('Concerns.', { kind: 'ask_genius', sources: [legacy] });
    fireEvent.click(screen.getByRole('button', { name: 'View review' }));
    fireEvent.click(screen.getByRole('button', { name: /Saved analysis/ }));
    expect(screen.getByRole('heading', { name: 'Unlabeled quotations' })).toBeInTheDocument();
  });

  it('marks an excerpt as shortened without shortening the popup review', () => {
    show('Concerns.', { kind: 'ask_genius', sources: [{ ...source, excerpt: 'The team ignored', excerpt_truncated: true }] });
    fireEvent.click(screen.getByRole('button', { name: 'View review' }));
    expect(screen.getByRole('dialog')).toHaveTextContent(original);
  });

  it('loads an older private source through the authorized review API', async () => {
    get.mockResolvedValue({ text: original, star_rating: 1, apartment_analysis: null });
    show('See [Review #7](/feedbacks/7).', { kind: 'ask_genius', sources: [{ review_id: 7, label: 'Review #7', href: '/feedbacks/7' }] });
    const trigger = await screen.findByRole('button', { name: 'View review' });
    expect(get).not.toHaveBeenCalled();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.queryByText('Review #7')).not.toBeInTheDocument();
    fireEvent.click(trigger);
    await waitFor(() => expect(screen.getByRole('dialog')).toHaveTextContent(original));
    expect(get).toHaveBeenCalledWith(7);
  });

  it('never fetches private reviews from a public snapshot, including malformed legacy sources', async () => {
    show('Shared finding.', { kind: 'ask_genius', sources: [{ review_id: 999, href: '/feedbacks/999', excerpt: 'An excerpt.' }] }, true);
    fireEvent.click(screen.getByRole('button', { name: 'View review' }));
    expect(screen.getByText('The full review was not included in this shared chat.')).toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();
  });

  it('renders paragraphs and bullets but strips navigation, images, HTML and copilot actions', () => {
    const { container } = show('**Concerns** first.\n\nA second paragraph.\n\n- Repairs\n- Billing\n\n[External](https://evil.invalid) ![Tracker](https://evil.invalid/t.png) <iframe src="https://evil.invalid"></iframe>', {
      kind: 'ask_genius', structured_data: [{ data_type: 'actions', data: { actions: [{ action: 'send_email', label: 'Send email' }] } }],
    });
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(screen.getByText('A second paragraph.').tagName).toBe('P');
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(container.querySelector('iframe')).toBeNull();
    expect(screen.queryByText('Send email')).not.toBeInTheDocument();
  });

  it.each([{ review_id: '7' }, { review_id: 0 }, { review_id: 1.1 }])('rejects invalid review identifiers %j', invalid => {
    show('Answer.', { kind: 'ask_genius', sources: [invalid] });
    expect(get).not.toHaveBeenCalled();
    expect(screen.queryByLabelText('Supporting reviews')).not.toBeInTheDocument();
  });

  it('copies only the written answer, excluding popup records', async () => {
    show();
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));
    await screen.findByRole('button', { name: 'Copied' });
    expect(writeText).toHaveBeenCalledWith('Residents reported communication concerns.');
    expect(writeText.mock.calls[0][0]).not.toContain('three times');
  });

  it('shows a useful fallback when clipboard access fails', async () => {
    writeText.mockRejectedValue(new Error('Denied'));
    show();
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Select the answer text to copy it.'));
    expect(screen.queryByRole('button', { name: 'Copied' })).not.toBeInTheDocument();
  });

  it('resets copy confirmation after two seconds', async () => {
    vi.useFakeTimers();
    try {
      show();
      await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Copy' })); });
      expect(screen.getByRole('button', { name: 'Copied' })).toBeInTheDocument();
      act(() => { vi.advanceTimersByTime(2000); });
      expect(screen.getByRole('button', { name: 'Copy' })).toBeInTheDocument();
    } finally { vi.useRealTimers(); }
  });
});


describe('Topic links and complete review collections', () => {
  it('attaches each popup directly to its topic and deduplicates matching reviews', () => {
    show('- **Staff:** Reports of unanswered calls.\n- **Billing:** Reports of disputed fees.', { kind: 'ask_genius', sources: [
      { ...source, topic: 'Staff' }, { ...source, topic: 'Staff' },
      { ...source, review_id: 8, topic: 'Billing', review: { ...source.review, original_review: 'The fee was unexplained.' } },
    ] });
    const bullets = screen.getAllByRole('listitem');
    expect(bullets).toHaveLength(2);
    expect(screen.queryByText(original)).not.toBeInTheDocument();
    fireEvent.click(within(bullets[1]).getByRole('button', { name: 'View review' }));
    expect(screen.getByRole('dialog')).toHaveTextContent('The fee was unexplained.');
    expect(screen.getByRole('dialog')).not.toHaveTextContent(original);
  });

  it('shows 78 reviews in manager-triggered pages of 50 and 28, with no private fetching', () => {
    const sources = Array.from({ length: 78 }, (_, index) => ({ ...source, review_id: index + 1, review: { ...source.review, original_review: `Original content ${index + 1}.` } }));
    show('Found 78 matching reviews.', { kind: 'ask_genius', sources }, true);
    expect(screen.getByText('Found 78 reviews. Showing 1–50 of 78 reviews.')).toBeInTheDocument();
    expect(screen.queryByRole('article', { name: 'Additional reviews' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'View 50 reviews' }));
    expect(within(screen.getByRole('dialog')).getAllByRole('region', { name: 'Original review' })).toHaveLength(50);
    expect(screen.getByRole('dialog')).not.toHaveTextContent('Original content 51.');
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Close' }));
    fireEvent.click(screen.getByRole('button', { name: 'Show remaining 28' }));
    const next = screen.getByRole('article', { name: 'Additional reviews' });
    expect(next).toHaveTextContent('Showing 51–78 of 78 reviews.');
    fireEvent.click(within(next).getByRole('button', { name: 'View 28 reviews' }));
    const modal = screen.getByRole('dialog');
    expect(within(modal).getAllByRole('region', { name: 'Original review' })).toHaveLength(28);
    expect(modal).toHaveTextContent('Original content 78.');
    expect(modal).not.toHaveTextContent('Original content 1.');
    expect(screen.queryByRole('button', { name: /Show (?:remaining|next)/ })).not.toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();
  });
});
