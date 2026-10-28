import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AskGenius } from '@/components/reviews/AskGenius';
import { MessageBubble } from '@/components/copilot/MessageBubble';
const mocks = vi.hoisted(() => ({ status: vi.fn(), saveDefaultPeriod: vi.fn(), conversations: vi.fn(), conversation: vi.fn(), ask: vi.fn(), user: { id: 1, organization_id: 11 } }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: mocks.user }) }));
vi.mock('@/lib/api/ask-genius', () => ({ askGeniusAPI: mocks }));
vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn() }) }));
function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const ui = () => <QueryClientProvider client={client}><AskGenius /></QueryClientProvider>;
  return { ...render(ui()), ui };
}
function connectedStatus(overrides: Record<string, unknown> = {}) {
  return { ready: true, default_period: { preset: 'all_time' }, available_sources: ['reviews', 'analysis'], timezone: 'America/New_York', date_coverage: { total_reviews: 6, dated_reviews: 0, undated_reviews: 6 }, ...overrides };
}
beforeEach(() => {
  mocks.status.mockResolvedValue(connectedStatus());
  mocks.saveDefaultPeriod.mockImplementation(async default_period => ({ default_period }));
  mocks.conversations.mockResolvedValue({ conversations: [], total: 0 });
  mocks.conversation.mockResolvedValue({ public_id: 'one', title: 'Praise', period: { preset: 'all_time' }, messages: [] });
  mocks.ask.mockResolvedValue({ conversation_id: 'one', title: 'Praise', answer: 'The saved reviews praise helpful staff.', message_id: 10, period: { preset: 'all_time' }, default_period: { preset: 'all_time' }, preference_updated: false });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); mocks.user = { id: 1, organization_id: 11 }; });
it('makes no model requests on mount or when a starter is selected', async () => {
  mount();
  const starter = await screen.findByRole('button', { name: 'What did residents praise in reviews during this period?' });
  await waitFor(() => expect(starter).toBeEnabled());
  expect(mocks.ask).not.toHaveBeenCalled();
  fireEvent.click(starter);
  expect(screen.getByRole('textbox', { name: 'Your question' })).toHaveValue('What did residents praise in reviews during this period?');
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
  expect(mocks.ask).toHaveBeenCalledWith('What do residents praise?', expect.any(String), undefined, { preset: 'all_time' });
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
  expect(screen.getByRole('button', { name: 'New chat' })).toBeDisabled();
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
  await screen.findByText(/This answer could not be completed/);
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

it('requires a chosen period when the account has no saved default', async () => {
  mocks.status.mockResolvedValue(connectedStatus({ default_period: null }));
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  const picker = screen.getByRole('combobox', { name: 'Time period' });
  expect(picker).toHaveValue('');
  expect(picker).not.toHaveClass('ring-2');
  expect(screen.getByRole('button', { name: 'Which topics came up most often in reviews during this period?' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Which topics came up most often in reviews during this period?' }));
  expect(input).toHaveValue('Which topics came up most often in reviews during this period?');
  expect(picker).toHaveFocus();
  expect(screen.getByText('Choose a time period above to send your question.')).toBeInTheDocument();
  input.focus();
  expect(picker).not.toHaveFocus();
  fireEvent.change(input, { target: { value: 'What are the main complaints?' } });
  expect(picker).toHaveClass('ring-2', 'ring-primary');
  expect(picker).toHaveAttribute('aria-invalid', 'true');
  fireEvent.keyDown(input, { key: 'Enter' });
  expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled();
  expect(mocks.ask).not.toHaveBeenCalled();
  fireEvent.change(picker, { target: { value: 'last_14_days' } });
  expect(picker).not.toHaveClass('ring-2');
  expect(picker).not.toHaveAttribute('aria-invalid');
  expect(screen.getByRole('button', { name: 'Send question' })).toBeEnabled();
  expect(mocks.saveDefaultPeriod).not.toHaveBeenCalled();
});

it('keeps the period reminder highlighted until a complete valid custom range is selected', async () => {
  mocks.status.mockResolvedValue(connectedStatus({ default_period: null }));
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  const picker = screen.getByRole('combobox', { name: 'Time period' });
  fireEvent.click(screen.getByRole('button', { name: 'Which topics came up most often in reviews during this period?' }));
  fireEvent.change(picker, { target: { value: 'custom' } });
  input.focus();
  expect(picker).toHaveClass('ring-2', 'ring-primary');
  fireEvent.change(screen.getByLabelText('Period start date'), { target: { value: '2026-10-10' } });
  expect(picker).toHaveClass('ring-2', 'ring-primary');
  fireEvent.change(screen.getByLabelText('Period end date'), { target: { value: '2026-10-01' } });
  expect(picker).toHaveAttribute('aria-invalid', 'true');
  expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Period end date'), { target: { value: '2026-10-27' } });
  expect(picker).not.toHaveClass('ring-2');
  expect(picker).not.toHaveAttribute('aria-invalid');
  expect(screen.getByRole('button', { name: 'Send question' })).toBeEnabled();
  expect(mocks.ask).not.toHaveBeenCalled();
});

it('keeps a manually submitted missing-period reminder visible after blur and resets it for a new chat', async () => {
  mocks.status.mockResolvedValue(connectedStatus({ default_period: null }));
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  const picker = screen.getByRole('combobox', { name: 'Time period' });
  fireEvent.change(input, { target: { value: 'What are the main complaints?' } });
  fireEvent.keyDown(input, { key: 'Enter' });
  input.focus();
  expect(picker).not.toHaveFocus();
  expect(picker).toHaveClass('ring-2', 'ring-primary');
  expect(mocks.ask).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }));
  expect(picker).toHaveValue('');
  expect(picker).not.toHaveClass('ring-2');
  expect(picker).not.toHaveAttribute('aria-invalid');
});

it('shows all category tabs while only connected questions can be selected', async () => {
  mount();
  const browse = screen.getByRole('button', { name: 'Browse more questions' });
  await waitFor(() => expect(browse).toBeEnabled());
  fireEvent.click(browse);
  for (const name of ['Reviews', 'Analysis', 'Surveys', 'Management responses']) expect(screen.getByRole('tab', { name: new RegExp(name) })).toBeInTheDocument();
  fireEvent.mouseDown(screen.getByRole('tab', { name: /Surveys/ }), { button: 0, ctrlKey: false });
  const survey = await screen.findByRole('button', { name: 'How many survey responses did we receive during this period?' });
  expect(survey).toBeDisabled();
  fireEvent.mouseDown(screen.getByRole('tab', { name: 'Analysis' }), { button: 0, ctrlKey: false });
  fireEvent.click(await screen.findByRole('button', { name: 'What did reviews say about maintenance during this period?' }));
  const input = screen.getByRole('textbox', { name: 'Your question' });
  expect(input).toHaveValue('What did reviews say about maintenance during this period?');
  fireEvent.change(input, { target: { value: 'What did reviews say about parking during this period?' } });
  expect(mocks.ask).not.toHaveBeenCalled();
  expect(mocks.saveDefaultPeriod).not.toHaveBeenCalled();
});

it('sends a calendar period distinctly from a rolling window', async () => {
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  const picker = screen.getByRole('combobox', { name: 'Time period' });
  expect(screen.getByRole('option', { name: 'Last 30 days' })).toHaveValue('last_30_days');
  fireEvent.change(picker, { target: { value: 'last_month' } });
  fireEvent.change(input, { target: { value: 'How many reviews in this period?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText('The saved reviews praise helpful staff.');
  expect(mocks.ask).toHaveBeenCalledWith('How many reviews in this period?', expect.any(String), undefined, { preset: 'last_month' });
});

it('requires both valid custom dates and sends the exact range', async () => {
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(screen.getByRole('combobox', { name: 'Time period' }), { target: { value: 'custom' } });
  fireEvent.change(input, { target: { value: 'How many reviews?' } });
  fireEvent.change(screen.getByLabelText('Period start date'), { target: { value: '2026-10-10' } });
  expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Period end date'), { target: { value: '2026-10-01' } });
  expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled();
  expect(screen.getByRole('button', { name: 'Save as my default' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Period end date'), { target: { value: '2026-10-27' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText('The saved reviews praise helpful staff.');
  expect(mocks.ask).toHaveBeenCalledWith('How many reviews?', expect.any(String), undefined, { preset: 'custom', start_date: '2026-10-10', end_date: '2026-10-27' });
});

it('confirms a default only after successful saving and uses it for new conversations', async () => {
  let resolve!: (value: unknown) => void;
  mocks.saveDefaultPeriod.mockReturnValue(new Promise(r => { resolve = r; }));
  mocks.status.mockResolvedValue(connectedStatus({ default_period: null }));
  mount();
  const picker = screen.getByRole('combobox', { name: 'Time period' });
  await waitFor(() => expect(picker).toBeEnabled());
  fireEvent.change(picker, { target: { value: 'last_30_days' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save as my default' }));
  expect(mocks.saveDefaultPeriod).toHaveBeenCalledWith({ preset: 'last_30_days' });
  expect(screen.queryByText(/saved as your default for new conversations/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'New chat' })).toBeDisabled();
  resolve({ default_period: { preset: 'last_30_days' } });
  await screen.findByText('Last 30 days saved as your default for new conversations.');
  fireEvent.change(picker, { target: { value: 'last_7_days' } });
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }));
  expect(picker).toHaveValue('last_30_days');
  expect(mocks.saveDefaultPeriod).toHaveBeenCalledTimes(1);
  expect(mocks.ask).not.toHaveBeenCalled();
});

it('does not claim a failed preference change succeeded', async () => {
  mocks.saveDefaultPeriod.mockRejectedValue(new Error('Network failure'));
  mount();
  const picker = screen.getByRole('combobox', { name: 'Time period' });
  await waitFor(() => expect(picker).toBeEnabled());
  fireEvent.change(picker, { target: { value: 'last_7_days' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save as my default' }));
  await screen.findByText('Your default change could not be confirmed. Try again.');
  expect(screen.queryByText(/saved as your default for new conversations/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }));
  expect(picker).toHaveValue('all_time');
});

it('clearing a saved default requires a period again for the next conversation', async () => {
  mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Remove default' }));
  await screen.findByText('Default removed. Choose a period when starting a new conversation.');
  expect(mocks.saveDefaultPeriod).toHaveBeenCalledWith(null);
  expect(screen.getByRole('combobox', { name: 'Time period' })).toHaveValue('all_time');
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }));
  expect(screen.getByRole('combobox', { name: 'Time period' })).toHaveValue('');
  expect(screen.getByRole('button', { name: 'Send question' })).toBeDisabled();
});

it('restores the conversation period instead of substituting the account default', async () => {
  mocks.conversations.mockResolvedValue({ conversations: [{ public_id: 'one', title: 'Last week' }], total: 1 });
  mocks.conversation.mockResolvedValue({ public_id: 'one', title: 'Last week', period: { preset: 'last_7_days' }, messages: [{ id: 3, role: 'assistant', content: 'Saved weekly answer.', structured_data: null, created_at: '' }] });
  mount();
  fireEvent.click(await screen.findByRole('button', { name: 'Last week' }));
  await screen.findByText('Saved weekly answer.');
  expect(screen.getByRole('combobox', { name: 'Time period' })).toHaveValue('last_7_days');
  expect(mocks.ask).not.toHaveBeenCalled();
});

it('uses a new request id after the selected period changes', async () => {
  mocks.ask.mockRejectedValueOnce(new Error('Ambiguous network failure'));
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'How many reviews?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText(/The answer could not be completed/);
  const firstId = mocks.ask.mock.calls[0][1];
  fireEvent.change(screen.getByRole('combobox', { name: 'Time period' }), { target: { value: 'last_14_days' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText('The saved reviews praise helpful staff.');
  expect(mocks.ask.mock.calls[1][1]).not.toBe(firstId);
  expect(mocks.ask.mock.calls[1][3]).toEqual({ preset: 'last_14_days' });
});

it('explains missing dates and never automatically widens a selected period', async () => {
  mocks.status.mockResolvedValue(connectedStatus({ default_period: { preset: 'last_7_days' } }));
  mount();
  const notice = await screen.findByTestId('date-coverage-notice');
  expect(notice).toHaveTextContent('6 reviews have no posting date.');
  expect(notice).toHaveTextContent('Excluded from date filters.');
  expect(screen.getByRole('combobox', { name: 'Time period' })).toHaveValue('last_7_days');
  expect(mocks.ask).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Use all available history' }));
  expect(screen.getByRole('combobox', { name: 'Time period' })).toHaveValue('all_time');
  expect(mocks.saveDefaultPeriod).not.toHaveBeenCalled();
});

it('accepts an explicit save-default chat command before a period is chosen', async () => {
  mocks.status.mockResolvedValue(connectedStatus({ default_period: null }));
  mocks.ask.mockResolvedValue({ conversation_id: 'one', title: 'Default', answer: 'Last 14 days saved as your default.', message_id: 10, period: { preset: 'last_14_days' }, default_period: { preset: 'last_14_days' }, preference_updated: true });
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'Use the last 14 days as my default going forward.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText('Last 14 days saved as your default.');
  expect(mocks.ask).toHaveBeenCalledWith('Use the last 14 days as my default going forward.', expect.any(String), undefined, undefined);
  fireEvent.click(screen.getByRole('button', { name: 'New chat' }));
  expect(screen.getByRole('combobox', { name: 'Time period' })).toHaveValue('last_14_days');
});

it.each(['Can you', 'Could you', 'Would you please'])('accepts a polite default request starting with "%s" before period selection', async prefix => {
  mocks.status.mockResolvedValue(connectedStatus({ default_period: null }));
  mocks.ask.mockResolvedValue({ conversation_id: 'one', title: 'Default', answer: 'Last 30 days saved as your default.', message_id: 10, period: { preset: 'last_30_days' }, default_period: { preset: 'last_30_days' }, preference_updated: true });
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  const question = `${prefix} use last 30 days as my default?`;
  fireEvent.change(input, { target: { value: question } });
  expect(screen.getByRole('button', { name: 'Send question' })).toBeEnabled();
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByText('Last 30 days saved as your default.');
  expect(mocks.ask).toHaveBeenCalledWith(question, expect.any(String), undefined, undefined);
});

it('shows a safe server clarification for an unsupported period', async () => {
  const detail = 'Choose one supported period in the time-period selector, or enter a custom date range.';
  mocks.ask.mockRejectedValue({ isAxiosError: true, response: { status: 422, data: { detail } } });
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'Compare last week with last year.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  expect(await screen.findByRole('alert')).toHaveTextContent(detail);
  expect(input).toHaveValue('Compare last week with last year.');
});

it('keeps a friendly fallback instead of exposing raw validation details', async () => {
  mocks.ask.mockRejectedValue({ isAxiosError: true, response: { status: 422, data: { detail: [{ input: 'PRIVATE_VALIDATION_INPUT', type: 'value_error' }] } } });
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'What are the complaints?' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Check the selected period and question.');
  expect(screen.queryByText(/PRIVATE_VALIDATION_INPUT/)).not.toBeInTheDocument();
});

it('does not reuse a different account’s selected or saved period', async () => {
  const { rerender, ui } = mount();
  const picker = screen.getByRole('combobox', { name: 'Time period' });
  await waitFor(() => expect(picker).toBeEnabled());
  fireEvent.change(picker, { target: { value: 'last_7_days' } });
  mocks.status.mockResolvedValue(connectedStatus({ default_period: null }));
  mocks.user = { id: 2, organization_id: 22 };
  rerender(ui());
  await waitFor(() => expect(screen.getByRole('combobox', { name: 'Time period' })).toBeEnabled());
  expect(screen.getByRole('combobox', { name: 'Time period' })).toHaveValue('');
});

it('shows a failed question beside Retry and uses the safe server explanation', async () => {
  mocks.ask.mockRejectedValueOnce({ isAxiosError: true, response: { status: 502, data: { detail: { code: 'ask_genius_failed', message: 'The model took too long to answer. Please try again.' } } } });
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'Show the actual review.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  expect(await screen.findByText('The model took too long to answer. Please try again.')).toBeInTheDocument();
  expect(screen.getByText('Show the actual review.', { selector: 'div' })).toBeInTheDocument();
  const requestId = mocks.ask.mock.calls[0][1];
  fireEvent.change(input, { target: { value: 'A different draft' } });
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  await screen.findByText('The saved reviews praise helpful staff.');
  expect(mocks.ask.mock.calls[1][0]).toBe('Show the actual review.');
  expect(mocks.ask.mock.calls[1][1]).not.toBe(requestId);
});

it('keeps a failed first question attached to its saved chat for the retry', async () => {
  mocks.ask.mockRejectedValueOnce({ isAxiosError: true, response: { status: 502, data: { detail: { code: 'ask_genius_failed', conversation_id: 'failed-chat', message: 'This answer could not be completed.' } } } });
  mount();
  const input = screen.getByRole('textbox', { name: 'Your question' });
  await waitFor(() => expect(input).toBeEnabled());
  fireEvent.change(input, { target: { value: 'Show me the reviews.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Send question' }));
  await screen.findByRole('button', { name: 'Retry' });
  fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
  await screen.findByText('The saved reviews praise helpful staff.');
  expect(mocks.ask.mock.calls[1][2]).toBe('failed-chat');
});

it('allows retrying a saved failed question after reopening its chat', async () => {
  mocks.conversations.mockResolvedValue({ conversations: [{ public_id: 'one', title: 'Saved failure' }], total: 1 });
  mocks.conversation.mockResolvedValue({ public_id: 'one', title: 'Saved failure', period: { preset: 'all_time' }, messages: [{ id: 3, role: 'user', content: 'Show me the original review.', structured_data: null, created_at: '', status: 'failed' }] });
  mount();
  fireEvent.click(await screen.findByRole('button', { name: /^Saved\ failure$/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'Retry' }));
  await screen.findByText('The saved reviews praise helpful staff.');
  expect(mocks.ask).toHaveBeenCalledWith('Show me the original review.', expect.any(String), 'one', { preset: 'all_time' });
  expect(screen.getAllByText('Show me the original review.')).toHaveLength(1);
});
