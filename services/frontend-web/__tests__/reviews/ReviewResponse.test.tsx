import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReviewResponse } from '@/components/reviews/ReviewResponse';
import type { ReviewReply } from '@/lib/api/review-replies';

const user = vi.hoisted(() => ({id: 3, organization_id: 10, role: 'owner'}));
const api = vi.hoisted(() => ({ get: vi.fn(), draft: vi.fn(), save: vi.fn(), approve: vi.fn() }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user }) }));
vi.mock('@/lib/api/review-replies', async (importOriginal) => ({
  ...await importOriginal<typeof import('@/lib/api/review-replies')>(),
  reviewRepliesAPI: api,
}));

const initial: ReviewReply = {
  review_id: 42, status: 'not_drafted', version: 0, text: null, reason: null,
  generation_method: null, approved_by: null, approved_at: null, published_at: null,
  publishing_connected: false, settings_confirmed: true, error: null,
};

const draft: ReviewReply = {
  ...initial, status: 'pending_approval', version: 1, text: 'Thank you for sharing this.',
  reason: 'All replies need manager approval.', generation_method: 'example',
};

function mount(reply: ReviewReply) {
  api.get.mockResolvedValue(reply);
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><ReviewResponse id={42} /></QueryClientProvider>);
}

afterEach(() => { cleanup(); vi.resetAllMocks(); user.role = 'owner'; });

describe('review response workflow', () => {
  it('offers setup when no draft and no confirmed review settings exist', async () => {
    mount({ ...initial, settings_confirmed: false });
    expect(await screen.findByRole('link', { name: 'Set up review responses' })).toHaveAttribute('href', '/agent-settings');
    expect(screen.queryByRole('button', { name: 'Create draft' })).not.toBeInTheDocument();
  });

  it.each(['pending_approval', 'approved'] as const)('identifies earlier settings on a saved %s reply', async status => {
    mount({ ...draft, status, uses_previous_settings: true });
    expect(await screen.findByText(/This reply uses earlier community settings/)).toBeVisible();
    expect(screen.getByText(draft.text!)).toBeVisible();
  });

  it('makes a local example only when requested and explains the approval queue', async () => {
    mount(initial);
    api.draft.mockResolvedValue(draft);
    fireEvent.click(await screen.findByRole('button', { name: 'Create draft' }));
    expect(await screen.findByText(draft.text!)).toBeInTheDocument();
    expect(screen.getByText('Draft source · Built-in example')).toBeInTheDocument();
    expect(screen.getByText(/All replies need manager approval/)).toBeInTheDocument();
    expect(screen.getByText(/Approval saves your decision/)).toBeInTheDocument();
    expect(api.draft).toHaveBeenCalledWith(42);
    expect(api.approve).not.toHaveBeenCalled();
  });

  it.each<ReviewReply>([initial, draft, { ...draft, status: 'approved' }, { ...initial, status: 'failed' }])('keeps members read-only for $status', async reply => {
    user.role = 'member';
    mount(reply);
    expect(await screen.findByText('A community admin or owner can manage this reply.')).toBeVisible();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
    if (reply.text) expect(screen.getByText(reply.text)).toBeVisible();
  });

  it('allows cancel and edit without approving or changing community settings', async () => {
    mount(draft);
    fireEvent.click(await screen.findByRole('button', { name: 'Edit draft' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Edit this reply' }), { target: { value: 'Unsaved' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByText(draft.text!)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Edit draft' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Edit this reply' }), { target: { value: '   ' } });
    expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled();
    fireEvent.change(screen.getByRole('textbox', { name: 'Edit this reply' }), { target: { value: '  Revised response. ' } });
    api.save.mockResolvedValue({ ...draft, text: 'Revised response.', version: 2 });
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
    await waitFor(() => expect(screen.queryByRole('textbox')).not.toBeInTheDocument());
    expect(screen.getByText('Revised response.')).toBeInTheDocument();
    expect(api.save).toHaveBeenCalledWith(42, 1, 'Revised response.');
    expect(screen.getByText('Needs approval')).toBeInTheDocument();
    expect(api.approve).not.toHaveBeenCalled();
  });

  it('keeps the typed text on a conflicting save and requires reviewing the newer reply', async () => {
    mount(draft);
    fireEvent.click(await screen.findByRole('button', { name: 'Edit draft' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'My wording' } });
    api.save.mockRejectedValue({ isAxiosError: true, response: { status: 409 } });
    api.get.mockResolvedValue({ ...draft, text: 'Other manager’s wording', version: 2 });
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
    expect(await screen.findByText(/This reply or its settings changed/)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Save draft' })).toBeDisabled());
    expect(screen.getByRole('textbox')).toHaveValue('My wording');
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    expect(screen.getByText('Other manager’s wording')).toBeInTheDocument();
  });

  it('shows the approving manager and time while publication is still pending', async () => {
    mount({ ...draft, generation_method: 'ai' });
    api.approve.mockResolvedValue({
      ...draft, status: 'approved', version: 2, generation_method: 'ai',
      approved_by: 'manager@example.com', approved_at: '2026-11-05T18:00:00Z',
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Approve reply' }));
    expect(await screen.findByText('Approved · awaiting publication')).toBeInTheDocument();
    expect(screen.getByText(/Approved by manager@example.com/)).toBeInTheDocument();
    expect(screen.getByText(/This approved reply is saved/)).toBeInTheDocument();
    expect(screen.queryByText('Published')).not.toBeInTheDocument();
    expect(screen.queryByText('Draft source · Built-in example')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Edit draft' })).not.toBeInTheDocument();
    expect(api.approve).toHaveBeenCalledWith(42, 1);
    fireEvent.click(screen.getByRole('button', { name: 'Edit approved reply' }));
    expect(screen.getByText(/Saving your edit returns this reply to Needs approval/)).toBeInTheDocument();
  });

  it('displays a confirmed publication separately from automatic approval', async () => {
    mount({ ...draft, generation_method: 'ai', status: 'published', approved_by: 'BoomSay',
      approved_at: '2026-11-05T18:00:00Z', published_at: '2026-11-05T18:15:00Z', publishing_connected: true });
    expect(await screen.findByText('Published')).toBeInTheDocument();
    expect(screen.getByText(/Approved by BoomSay/)).toBeInTheDocument();
    expect(document.querySelector('time[datetime="2026-11-05T18:15:00Z"]')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve reply' })).not.toBeInTheDocument();
  });

  it('lets a manager retry a failed draft action without implying a post was attempted', async () => {
    mount({ ...initial, status: 'failed', error: 'The draft could not be created.', version: 1 });
    expect(await screen.findByRole('alert')).toHaveTextContent('The draft could not be created.');
    api.draft.mockResolvedValue({ ...draft, version: 2 });
    fireEvent.click(screen.getByRole('button', { name: 'Retry draft' }));
    expect(await screen.findByText('Needs approval')).toBeInTheDocument();
    expect(api.draft).toHaveBeenCalledWith(42);
    expect(screen.queryByText('Draft failed')).not.toBeInTheDocument();
  });
});
