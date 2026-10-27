import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MessageBubble } from '@/components/copilot/MessageBubble';
import type { ChatMessage } from '@/components/copilot/ChatArea';

const { push } = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }));

function show(content: string, structuredData: ChatMessage['structured_data'] = null) {
  return render(<MessageBubble answerOnly message={{
    id: 15,
    role: 'assistant',
    content,
    structured_data: structuredData,
    created_at: '',
  }} />);
}

beforeEach(() => { vi.clearAllMocks(); });
afterEach(cleanup);

describe('Ask Genius supporting information', () => {
  it('opens the exact authorized review link supplied by the server', () => {
    show('The repair delay appears in [Review #7](/feedbacks/7).', {
      kind: 'ask_genius',
      sources: [{ review_id: 7, label: 'Review #7', href: '/feedbacks/7' }],
    });
    const link = screen.getByRole('link', { name: 'Review #7' });
    expect(link).toHaveAttribute('href', '/feedbacks/7');
    fireEvent.click(link);
    expect(push).toHaveBeenCalledWith('/feedbacks/7');
  });

  it('does not make an uncited internal review or external address clickable', () => {
    show('[Authorized](/feedbacks/7), [Other review](/feedbacks/8), [External](https://example.invalid), [Settings](/settings).', {
      kind: 'ask_genius',
      sources: [{ review_id: 7, label: 'Review #7', href: '/feedbacks/7' }],
    });
    expect(screen.getAllByRole('link')).toHaveLength(1);
    expect(screen.getByRole('link')).toHaveTextContent('Authorized');
    expect(screen.getByText('Other review')).toBeInTheDocument();
    expect(screen.getByText('External')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it.each([
    { review_id: 7, href: '/feedbacks/8' },
    { review_id: 7, href: 'https://example.invalid/feedbacks/7' },
    { review_id: 7, href: '/feedbacks/7?redirect=https://example.invalid' },
    { review_id: 7, href: '//example.invalid/feedbacks/7' },
    { review_id: '7', href: '/feedbacks/7' },
    { review_id: 0, href: '/feedbacks/0' },
    { review_id: -1, href: '/feedbacks/-1' },
    { review_id: 1.5, href: '/feedbacks/1.5' },
    { review_id: Number.MAX_SAFE_INTEGER + 1, href: `/feedbacks/${Number.MAX_SAFE_INTEGER + 1}` },
  ])('rejects noncanonical source metadata: %j', source => {
    show(`[Source](${source.href})`, { kind: 'ask_genius', sources: [source] });
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('requires the Ask Genius server envelope even if a source list exists', () => {
    show('[Review](/feedbacks/7)', { sources: [{ review_id: 7, href: '/feedbacks/7' }] });
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('keeps old answers without verified sources readable without activating links', () => {
    show('An older [review](/feedbacks/7).');
    expect(screen.getByText('review')).toBeInTheDocument();
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  it('blocks images and action controls even alongside an authorized source', () => {
    show('[Review](/feedbacks/7) ![Remote image](https://example.invalid/image.png)', {
      kind: 'ask_genius',
      sources: [{ review_id: 7, href: '/feedbacks/7' }],
      structured_data: [{ data_type: 'actions', data: {
        proposal_id: 'invalid-action', actions: [{ action: 'send_email', label: 'Send email' }],
      } }],
    });
    expect(screen.getByRole('link')).toHaveAttribute('href', '/feedbacks/7');
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('renders separate paragraphs, emphasis, lists and quoted evidence', () => {
    const { container } = show('**Maintenance delays** came up most often.\n\nBilling was also mentioned.\n\n- Waiting for repairs\n- Waiting for updates\n\n> I called twice.\n\nWould you like more supporting reviews?');
    expect(screen.getByText('Maintenance delays').tagName).toBe('STRONG');
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
    expect(container.querySelector('blockquote')).toHaveTextContent('I called twice.');
    expect(screen.getByText('Billing was also mentioned.').tagName).toBe('P');
    expect(screen.getByText('Would you like more supporting reviews?').tagName).toBe('P');
  });
});
