import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GeniusChatHistory } from '@/components/reviews/GeniusChatHistory';

const api = vi.hoisted(() => ({ updateConversation: vi.fn(), deleteConversation: vi.fn(), shareConversation: vi.fn() }));
vi.mock('@/lib/api/ask-genius', () => ({ askGeniusAPI: api }));
const chat = { public_id: 'one', title: 'Main complaints', is_pinned: false };
const callbacks = { onSelect: vi.fn(), onRefresh: vi.fn(), onDeleted: vi.fn() };
function mount(props: Partial<React.ComponentProps<typeof GeniusChatHistory>> = {}) {
  return render(<GeniusChatHistory conversations={[chat]} disabled={false} loading={false} failed={false} {...callbacks} {...props} />);
}
async function menu() { const user = userEvent.setup(); await user.click(screen.getByRole('button', { name: 'Options for Main complaints' })); return user; }
beforeEach(() => {
  api.updateConversation.mockResolvedValue(chat); api.deleteConversation.mockResolvedValue(undefined);
  api.shareConversation.mockResolvedValue({ token: 'snapshot-token', path: '/share/ask-genius/snapshot-token' });
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it('places pinned chats before other chats and toggles the pin without opening the chat', async () => {
  mount({ conversations: [chat, { public_id: 'two', title: 'Pinned chat', is_pinned: true }] });
  expect(screen.getAllByRole('region').map(el => el.getAttribute('aria-label'))).toEqual(['Pinned', 'Your chats']);
  fireEvent.click(screen.getByRole('button', { name: 'Unpin Pinned chat' }));
  await waitFor(() => expect(api.updateConversation).toHaveBeenCalledWith('two', { is_pinned: false }));
  expect(callbacks.onSelect).not.toHaveBeenCalled();
});
it('renames only after Save, trims the name, and refreshes history', async () => {
  mount(); const user = await menu();
  await user.click(screen.getByRole('menuitem', { name: 'Rename' }));
  const input = screen.getByRole('textbox', { name: 'Chat name' });
  expect(input).toHaveValue(chat.title); expect(api.updateConversation).not.toHaveBeenCalled();
  fireEvent.change(input, { target: { value: '  Billing concerns  ' } });
  await user.click(screen.getByRole('button', { name: /^Save$/ }));
  await waitFor(() => expect(api.updateConversation).toHaveBeenCalledWith('one', { title: 'Billing concerns' }));
  expect(callbacks.onRefresh).toHaveBeenCalled();
});
it('Cancel preserves the title and empty names cannot be saved', async () => {
  mount(); const user = await menu(); await user.click(screen.getByRole('menuitem', { name: 'Rename' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Chat name' }), { target: { value: '  ' } });
  expect(screen.getByRole('button', { name: /^Save$/ })).toBeDisabled();
  await user.click(screen.getByRole('button', { name: 'Cancel' }));
  expect(api.updateConversation).not.toHaveBeenCalled(); expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
it('requires delete confirmation and explains that shared copies remain', async () => {
  mount(); const user = await menu(); await user.click(screen.getByRole('menuitem', { name: /^Delete$/ }));
  expect(api.deleteConversation).not.toHaveBeenCalled();
  expect(screen.getByRole('dialog')).toHaveTextContent('Shared copies remain available.');
  await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Delete chat' }));
  await waitFor(() => expect(api.deleteConversation).toHaveBeenCalledWith('one'));
  expect(callbacks.onDeleted).toHaveBeenCalledWith('one');
});
it('creates and copies a public link with no manage-link option', async () => {
  mount(); const user = await menu(); const write = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
  await user.click(screen.getByRole('menuitem', { name: /^Share$/ }));
  expect(await screen.findByRole('status')).toHaveTextContent('Link copied. Anyone with the link can view this chat.');
  expect(write).toHaveBeenCalledWith(`${window.location.origin}/share/ask-genius/snapshot-token`);
  expect(api.shareConversation).toHaveBeenCalledWith('one');
  expect(screen.queryByText(/Manage link/)).not.toBeInTheDocument();
  expect(screen.getByRole('status')).toHaveClass('fixed', 'left-1/2', 'top-5');
  await user.click(screen.getByRole('button', { name: 'Dismiss share confirmation' }));
  expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
it('provides a selectable link if clipboard permission is unavailable', async () => {
  mount(); const user = await menu(); vi.spyOn(navigator.clipboard, 'writeText').mockRejectedValue(new Error('denied'));
  await user.click(screen.getByRole('menuitem', { name: /^Share$/ }));
  expect(await screen.findByRole('textbox', { name: 'Public chat link' })).toHaveValue(`${window.location.origin}/share/ask-genius/snapshot-token`);
  expect(screen.queryByText(/^Link copied/)).not.toBeInTheDocument();
});
it('shows a failed mutation without removing the chat or claiming success', async () => {
  api.updateConversation.mockRejectedValue(new Error('failed'));
  mount(); fireEvent.click(screen.getByRole('button', { name: 'Pin Main complaints' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('This change could not be confirmed.');
  expect(callbacks.onRefresh).not.toHaveBeenCalled(); expect(screen.getByRole('button', { name: /^Main\ complaints$/ })).toBeInTheDocument();
});
it('locks chat actions while an answer is pending', () => {
  mount({ disabled: true });
  for (const name of ['New chat', 'Main complaints', 'Pin Main complaints', 'Options for Main complaints']) expect(screen.getByRole('button', { name: new RegExp(`^${name}$`) })).toBeDisabled();
});
