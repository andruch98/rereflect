import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AskGenius } from '@/components/reviews/AskGenius';
import { MessageBubble } from '@/components/copilot/MessageBubble';
const mocks = vi.hoisted(() => ({ status: vi.fn(), conversations: vi.fn(), conversation: vi.fn(), ask: vi.fn(), user: { id: 1, organization_id: 11 } }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: mocks.user }) }));
vi.mock('@/lib/api/ask-genius', () => ({ askGeniusAPI: mocks }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui = () => <QueryClientProvider client={client}><AskGenius /></QueryClientProvider>;
  return { ...render(ui()), ui };
}
beforeEach(() => {
  mocks.status.mockResolvedValue({ ready: true });
  mocks.conversations.mockResolvedValue({ conversations: [], total: 0 });
  mocks.conversation.mockResolvedValue({ public_id: 'one', title: 'Praise', messages: [] });
  mocks.ask.mockResolvedValue({ conversation_id: 'one', title: 'Praise', answer: 'The saved reviews praise helpful staff.', message_id: 10 });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); mocks.user = { id: 1, organization_id: 11 }; });
it('makes no model requests on mount or when a starter is selected', async () => {
  mount();
  const starter = await screen.findByRole('button', { name: 'What do residents praise?' });
  await waitFor(() => expect(starter).toBeEnabled());
  expect(mocks.ask).not.toHaveBeenCalled();
  fireEvent.click(starter);
  expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue('What do residents praise?');
  expect(mocks.ask).not.toHaveBeenCalled();
});
it('disables questions honestly while setup is incomplete', async () => {
  mocks.status.mockResolvedValue({ ready: false, reason: 'MODEL_CONFIG missing' }); mount();
  await screen.findByText(/Ask Genius setup is not complete yet/);
  expect(screen.getByRole('textbox', { name: 'Your question' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled();
  expect(screen.queryByText('MODEL_CONFIG missing')).not.toBeInTheDocument();
  expect(mocks.ask).not.toHaveBeenCalled();
});
it('sends only the explicit question and renders the saved answer', async () => {
  mount(); const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'What do residents praise?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  expect(await screen.findByText('The saved reviews praise helpful staff.')).toBeInTheDocument();
  expect(mocks.ask).toHaveBeenCalledTimes(1);
  expect(mocks.ask).toHaveBeenCalledWith('What do residents praise?', expect.any(String), undefined);
  expect(input).toHaveValue('');
});
it('preserves the question and request id on a manual retry without automatic retries', async () => {
  mocks.ask.mockRejectedValueOnce(new Error('provider unavailable')); mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'What complaints mention staff?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText(/The answer could not be completed/);
  expect(input).toHaveValue('What complaints mention staff?');
  expect(mocks.ask).toHaveBeenCalledTimes(1); const id = mocks.ask.mock.calls[0][1];
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText('The saved reviews praise helpful staff.');
  expect(mocks.ask.mock.calls[1][1]).toBe(id);
});
it('blocks duplicate sends and conversation switching while a request is pending', async () => {
  let resolve!: (value: unknown) => void;
  mocks.ask.mockReturnValue(new Promise(r => { resolve = r; })); mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'How many reviews?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  fireEvent.keyDown(input, { key: 'Enter' });
  expect(mocks.ask).toHaveBeenCalledTimes(1);
  expect(screen.getByRole('button', { name: 'New conversation' })).toBeDisabled();
  resolve({ conversation_id: 'one', title: 'Counts', answer: 'Six saved reviews.', message_id: 11 });
  await screen.findByText('Six saved reviews.');
});
it('loads saved conversation history without asking again', async () => {
  mocks.conversations.mockResolvedValue({ conversations: [{ public_id: 'one', title: 'Earlier question' }], total: 1 });
  mocks.conversation.mockResolvedValue({ public_id: 'one', title: 'Earlier question', messages: [{ id: 3, role: 'assistant', content: 'Saved answer.', structured_data: null, created_at: '' }] }); mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Earlier question' }));
  await screen.findByText('Saved answer.');
  expect(mocks.conversation).toHaveBeenCalledWith('one');
  expect(mocks.ask).not.toHaveBeenCalled();
});
it('clears the draft question when the account changes', async () => {
  const { rerender, ui } = mount(); const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'Private draft question' } });
  mocks.user = { id: 2, organization_id: 22 }; rerender(ui());
  expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue('');
  expect(mocks.ask).not.toHaveBeenCalled();
});
it('reuses answer presentation without links, images or action controls', () => {
  render(<MessageBubble answerOnly message={{ id: 1, role: 'assistant', created_at: '', content: 'A [reference](/feedbacks/1) and ![remote image](https://example.invalid/a.png).', structured_data: { structured_data: [{ data_type: 'actions', data: { proposal_id: 'x', actions: [{ action: 'send_email', label: 'Send email' }] } }] } }} />);
  expect(screen.queryByRole('link')).not.toBeInTheDocument();
  expect(screen.queryByRole('img')).not.toBeInTheDocument();
  expect(screen.queryByRole('button')).not.toBeInTheDocument();
});
it('starts a new attempt only on a manual retry after a definite provider failure', async () => {
  mocks.ask.mockRejectedValueOnce({ isAxiosError: true, response: { status: 502, data: { detail: { code: 'ask_genius_failed' } } } }); mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'What do residents praise?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText(/Send the question again to start a new attempt/);
  expect(mocks.ask).toHaveBeenCalledTimes(1); const id = mocks.ask.mock.calls[0][1];
  await waitFor(() => expect(mocks.conversations).toHaveBeenCalledTimes(2));
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText('The saved reviews praise helpful staff.');
  expect(mocks.ask.mock.calls[1][1]).not.toBe(id);
});

it('retains the same request id after an ambiguous gateway 502', async () => {
  mocks.ask.mockRejectedValueOnce({ isAxiosError: true, response: { status: 502, data: 'Bad Gateway' } }); mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'What do residents praise?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText(/The answer could not be completed/);
  const id = mocks.ask.mock.calls[0][1];
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText('The saved reviews praise helpful staff.');
  expect(mocks.ask.mock.calls[1][1]).toBe(id);
});
