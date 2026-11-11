import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AgentSettings } from '@/components/agent-settings/AgentSettings';
import type { CommunitySettings, ReviewSettings, SurveySettings } from '@/lib/api/agent-settings';
import { SURVEY_TYPES } from '@/lib/api/surveys';

const api = vi.hoisted(() => ({ get: vi.fn(), save: vi.fn(), preview: vi.fn() }));
vi.mock('@/lib/api/agent-settings', async load => ({ ...await load<typeof import('@/lib/api/agent-settings')>(), agentSettingsAPI: api }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 1, organization_id: 11 } }) }));
const review: ReviewSettings = {
  community_name: 'Example Community', public_email: '', public_phone: '', facts: '',
  tone: 'professional', signature: 'The Example team', praise_guidance: '', complaint_guidance: '',
  mode: 'approval', hold_at_or_below: 2, hold_topics: ['safety'],
};
const survey: SurveySettings = {
  schedule: Object.fromEntries(SURVEY_TYPES.map(type => [type.eventType, { enabled: true, delay_hours: 0 }])) as SurveySettings['schedule'],
  flag_low_ratings: true, flag_unresolved: true, reminder_hours: null,
};
const initial: CommunitySettings = { can_edit: true, community_name: 'Example Community',
  reviews: { version: 0, configured: false, values: review }, surveys: { version: 0, configured: false, values: survey } };
const samples = { examples: [
  { review_text: 'Wonderful team.', star_rating: 5, text: 'Thank you for the note.', status: 'approved', reason: 'Matches policy.', generation_method: 'example' },
  { review_text: 'The side door lock feels unsafe.', star_rating: 4, text: 'Please contact our team.', status: 'pending_approval', reason: 'Safety topic.', generation_method: 'example' },
], publishing_connected: false };

beforeEach(() => {
  api.get.mockResolvedValue(initial);
  api.save.mockImplementation(async (_name, version, values) => ({ configured: true, version: version + 1, values }));
  api.preview.mockResolvedValue(samples);
});
afterEach(() => { cleanup(); vi.resetAllMocks(); });

function mount() {
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><AgentSettings /></QueryClientProvider>);
}
const tab = (name: string) => within(screen.getByRole('tabpanel', { name }));
const clickTab = (name: string) => fireEvent.mouseDown(screen.getByRole('tab', { name }), { button: 0 });
const click = (section: string, label: string) => fireEvent.click(tab(section).getByRole('button', { name: label }));

it('uses the proposed rules for sample replies and saves only on final confirmation', async () => {
  mount();
  await screen.findByRole('tab', { name: 'Review Responses' });
  const pane = 'Review Responses';
  click(pane, 'Edit Community details');
  fireEvent.change(tab(pane).getByLabelText('Public email (optional)'), { target: { value: 'office@example.org' } });
  click(pane, 'Confirm and continue');
  click(pane, 'Back');
  expect(tab(pane).getByText('office@example.org')).toBeVisible();
  click(pane, 'Confirm and continue');
  click(pane, 'Confirm and continue');
  click(pane, 'Edit Reply approval');
  fireEvent.click(tab(pane).getByLabelText('BoomSay approves eligible replies automatically'));
  click(pane, 'Confirm and continue');
  expect(await tab(pane).findByText('The side door lock feels unsafe.')).toBeVisible();
  expect(tab(pane).getByText('Would need manager approval')).toBeVisible();
  expect(tab(pane).getByText('Would be approved automatically')).toBeVisible();
  expect(api.preview).toHaveBeenCalledWith({ ...review, public_email: 'office@example.org', mode: 'automatic' });
  expect(api.save).not.toHaveBeenCalled();
  click(pane, 'Confirm settings');
  expect(await tab(pane).findByRole('heading', { name: 'Current settings' })).toBeVisible();
  expect(api.save).toHaveBeenCalledWith('reviews', 0, { ...review, public_email: 'office@example.org', mode: 'automatic' });
});

it('retains the individual survey edits across tabs and always includes explicit follow-ups', async () => {
  mount(); await screen.findByRole('tab', { name: 'Surveys' }); clickTab('Surveys');
  const pane = 'Surveys';
  click(pane, 'Edit Survey schedule');
  const form = tab(pane);
  expect(form.getAllByRole('checkbox')).toHaveLength(7);
  fireEvent.click(form.getByLabelText('Enable Move-out survey'));
  expect(form.getByLabelText('Invitation timing for Move-out')).toBeDisabled();
  fireEvent.change(form.getByLabelText('Invitation timing for Maintenance'), { target: { value: 48 } });
  clickTab('Review Responses'); clickTab(pane);
  expect(tab(pane).getByLabelText('Invitation timing for Maintenance')).toHaveValue('48');
  click(pane, 'Confirm and continue');
  click(pane, 'Edit Email reminder');
  fireEvent.change(tab(pane).getByLabelText('When to remind'), { target: { value: 24 } });
  click(pane, 'Confirm and continue');
  click(pane, 'Edit Responses needing review');
  fireEvent.click(tab(pane).getByLabelText('Include ratings of 1 or 2'));
  expect(tab(pane).getByText(/always included, even if/)).toBeVisible();
  click(pane, 'Confirm and continue');
  expect(api.save).not.toHaveBeenCalled(); expect(api.preview).not.toHaveBeenCalled();
  click(pane, 'Confirm settings');
  expect(await tab(pane).findByText('Settings saved.')).toBeVisible();
  expect(api.save).toHaveBeenCalledWith('surveys', 0, { ...survey,
    schedule: { ...survey.schedule, move_out_completed: { enabled: false, delay_hours: 0 },
      maintenance_completed: { enabled: true, delay_hours: 48 } }, reminder_hours: 24, flag_low_ratings: false });
});

it('safely cancels or saves just the changed section on return', async () => {
  api.get.mockResolvedValue({ ...initial, reviews: { configured: true, version: 3, values: review } });
  mount(); await screen.findByRole('tab', { name: 'Review Responses' });
  const pane = 'Review Responses';
  click(pane, 'Edit Reply style');
  fireEvent.change(tab(pane).getByLabelText('Signature (optional)'), { target: { value: 'Ignored' } });
  click(pane, 'Cancel edit');
  expect(tab(pane).getByText('The Example team')).toBeVisible(); expect(api.save).not.toHaveBeenCalled();
  click(pane, 'Edit Reply style');
  fireEvent.change(tab(pane).getByLabelText('Signature (optional)'), { target: { value: 'Leasing team' } });
  click(pane, 'Save changes');
  expect(await tab(pane).findByText('Settings saved.')).toBeVisible();
  expect(api.save).toHaveBeenCalledWith('reviews', 3, { ...review, signature: 'Leasing team' });
});

it('prevents stale changes from overwriting another manager and loads their newer confirmation', async () => {
  api.save.mockRejectedValueOnce({ isAxiosError: true, response: { status: 409 } });
  api.get.mockResolvedValueOnce({ ...initial, reviews: { configured: true, version: 1, values: review } })
    .mockResolvedValueOnce({ ...initial, reviews: { configured: true, version: 2, values: { ...review, signature: 'New shared signature' } } });
  mount(); await screen.findByRole('tab', { name: 'Review Responses' });
  const pane = 'Review Responses';
  click(pane, 'Edit Reply style'); click(pane, 'Save changes');
  expect(await tab(pane).findByRole('alert')).toHaveTextContent('A teammate changed');
  expect(tab(pane).getByRole('button', { name: 'Save changes' })).toBeDisabled();
  click(pane, 'Load latest settings');
  expect(await tab(pane).findByText('New shared signature')).toBeVisible();
});

it('shows current choices read-only to members without exposing manager preview or save actions', async () => {
  api.get.mockResolvedValue({ ...initial, can_edit: false });
  mount(); await screen.findByRole('tab', { name: 'Review Responses' });
  const pane = tab('Review Responses');
  expect(pane.getByText(/awaiting confirmation by a community manager/)).toBeVisible();
  expect(pane.queryByRole('button')).toBeNull();
});

it('keeps setup unsaved when preview fails and allows one correction from the final summary', async () => {
  api.preview.mockRejectedValueOnce(new Error('unavailable'));
  mount(); await screen.findByRole('tab', { name: 'Review Responses' });
  const pane = 'Review Responses';
  for (let step = 0; step < 3; step++) click(pane, 'Confirm and continue');
  expect(await tab(pane).findByRole('alert')).toHaveTextContent('Could not load');
  expect(tab(pane).getByRole('button', { name: 'Confirm settings' })).toBeDisabled();
  click(pane, 'Edit Community details');
  fireEvent.change(tab(pane).getByLabelText('Public community name'), { target: { value: 'Sample Oaks' } });
  click(pane, 'Return to summary');
  expect(await tab(pane).findByText('The side door lock feels unsafe.')).toBeVisible();
  expect(api.preview).toHaveBeenLastCalledWith({ ...review, community_name: 'Sample Oaks' });
  click(pane, 'Edit Community details');
  fireEvent.change(tab(pane).getByLabelText('Public community name'), { target: { value: 'Discard this name' } });
  click(pane, 'Cancel edit');
  expect(await tab(pane).findByText('Sample Oaks')).toBeVisible();
  expect(api.preview).toHaveBeenCalledTimes(2);
  expect(api.save).not.toHaveBeenCalled();
});
