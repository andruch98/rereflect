import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ResidentSurvey } from '@/components/surveys/ResidentSurvey';
import { SurveyDashboard, SurveyDetail } from '@/components/surveys/SurveyDashboard';
import { SurveyUnsubscribe } from '@/components/surveys/SurveyUnsubscribe';
import type { SurveyInstance } from '@/lib/api/surveys';

const api = vi.hoisted(() => ({ resident: vi.fn(), saveDraft: vi.fn(), submit: vi.fn(), list: vi.fn(), get: vi.fn(), unsubscribe: vi.fn() }));
vi.mock('@/lib/api/surveys', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/api/surveys')>(), surveysAPI: api }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 1, organization_id: 11 } }) }));
const survey: SurveyInstance = {
  public_id: '11111111-1111-4111-8111-111111111111', status: 'draft', submitted_at: null,
  context: { community_name: 'Fictional Oaks', resident_name: 'Fictional Resident', unit_number: '204', ticket_id: 'TEST-42', request_description: 'the kitchen leak', ticket_completed_at: '2026-10-26T12:00:00Z' },
  questionnaire: { id: 'maintenance_v1', title: 'Tell us about your maintenance experience', version: 1, catalog_version: 1, rating_labels: { '1': 'Terrible', '2': 'Bad', '3': 'Okay', '4': 'Good', '5': 'Excellent' }, questions: [
    { id: 'maintenance_overall', type: 'rating', text: 'Overall rating', rendered_text: 'Overall rating for the kitchen leak?', required: true },
    { id: 'issue_resolution', type: 'single_choice', text: 'Is the issue fully resolved?', rendered_text: 'Is the issue fully resolved?', required: true, options: [{ value: 'resolved', label: 'Yes, fully resolved' }, { value: 'unresolved', label: 'No, still unresolved' }] },
    { id: 'maintenance_response_time', type: 'rating', text: 'Response time?', rendered_text: 'Response time?', required: true, special_options: [{ value: 'not_sure', label: 'Not sure' }] },
    { id: 'maintenance_comment', type: 'text', text: 'Your comment?', rendered_text: 'Your comment?', required: false, max_length: 2000 },
  ] },
  answers: {}, draft_answers: { maintenance_overall: 2, issue_resolution: 'unresolved', maintenance_response_time: 'not_sure', maintenance_comment: 'The leak remains.' },
  invitation: { status: 'simulated', is_simulated: true, recipient: 'resident@example.invalid', subject: 'Maintenance survey', html: '<p>not rendered</p>', text: 'Please answer your maintenance survey.', survey_url: 'http://localhost:3000/survey/private-token' },
};
const completed = { ...survey, status: 'submitted' as const, submitted_at: '2026-10-27T15:00:00Z', answers: survey.draft_answers };
function mountDashboard(children: React.ReactNode) { return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>); }
beforeEach(() => {
  api.resident.mockResolvedValue(survey); api.saveDraft.mockResolvedValue(survey); api.submit.mockResolvedValue(completed);
  api.list.mockResolvedValue({ surveys: [survey, { ...completed, public_id: '22222222-2222-4222-8222-222222222222' }], total: 2 }); api.get.mockResolvedValue(completed);
  api.unsubscribe.mockResolvedValue({ status: 'unsubscribed' });
});
afterEach(() => { cleanup(); vi.clearAllMocks(); });

it('resumes the saved original questionnaire and draft including Not sure', async () => {
  render(<ResidentSurvey token="private-token" />);
  expect(await screen.findByRole('heading', { name: survey.questionnaire.title })).toBeInTheDocument();
  expect(screen.getByRole('radio', { name: 'No, still unresolved' })).toBeChecked();
  expect(screen.getByRole('radio', { name: 'Not sure' })).toBeChecked();
  expect(screen.getByRole('textbox', { name: 'Your comment?' })).toHaveValue('The leak remains.');
  expect(api.resident).toHaveBeenCalledWith('private-token');
  expect(screen.getByRole('status')).toHaveTextContent('Draft saved.');
});
it('does not claim a blank untouched survey is saved; confirms an explicit successful save', async () => {
  api.resident.mockResolvedValue({ ...survey, status: 'pending', draft_answers: {} });
  render(<ResidentSurvey token="private-token" />);
  await screen.findByRole('heading', { name: survey.questionnaire.title });
  expect(screen.queryByText(/Draft saved/)).not.toBeInTheDocument();
  expect(api.saveDraft).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
  expect(await screen.findByText(/Draft saved/)).toBeInTheDocument();
});
it('clears the saved confirmation when answers change and ignores a stale save completion', async () => {
  let finishDraft!: (value: SurveyInstance) => void;
  api.saveDraft.mockImplementationOnce(() => new Promise(resolve => { finishDraft = resolve; }));
  render(<ResidentSurvey token="private-token" />);
  await screen.findByRole('heading', { name: survey.questionnaire.title });
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(api.saveDraft).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'New unsaved text.' } });
  expect(screen.queryByText(/Draft saved/)).not.toBeInTheDocument();
  await act(async () => { finishDraft(survey); });
  expect(screen.queryByText(/Draft saved/)).not.toBeInTheDocument();
  expect(screen.getByRole('textbox')).toHaveValue('New unsaved text.');
});
it.each([
  ['email_test_accepted', false, 'Test email sent'],
  ['simulated', true, 'Simulated invitation — no email sent'],
  ['email_test_reserved', false, 'Test email sending not confirmed'],
  ['email_test_failed', false, 'Test email send failed'],
  ['suppressed_opt_out', true, 'Invitation suppressed — opted out'],
  ['unrecognized', false, 'Sending history unavailable'],
] as const)('shows truthful invitation state %s in both list and detail', async (status, is_simulated, expected) => {
  const row = { ...completed, invitation: { ...survey.invitation!, status, is_simulated } };
  api.list.mockResolvedValue({ surveys: [row], total: 1 }); api.get.mockResolvedValue(row);
  const list = mountDashboard(<SurveyDashboard />);
  expect(await screen.findByText(expected)).toBeInTheDocument();
  expect(screen.getByText('submitted')).toBeInTheDocument();
  list.unmount();
  mountDashboard(<SurveyDetail id={row.public_id} />);
  await screen.findByRole('heading', { name: 'Original questions and answers' });
  expect(screen.getAllByText(expected)).toHaveLength(2);
  expect(screen.queryByText(/No email was sent\./)).not.toBeInTheDocument();
  expect(screen.queryByText(/Delivered/)).not.toBeInTheDocument();
});
it('shows unavailable sending history without an invitation record', async () => {
  api.get.mockResolvedValue({ ...completed, invitation: undefined });
  mountDashboard(<SurveyDetail id={survey.public_id} />);
  expect(await screen.findByText('Sending history unavailable')).toBeInTheDocument();
  expect(screen.getByText('submitted')).toBeInTheDocument();
});
it('persists edits as a draft using numeric ratings and the actual private token', async () => {
  render(<ResidentSurvey token="private-token" />); await screen.findByRole('heading', { name: survey.questionnaire.title });
  fireEvent.click(screen.getAllByRole('radio', { name: '1 — Terrible' })[0]);
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(api.saveDraft).toHaveBeenCalledWith('private-token', { ...survey.draft_answers, maintenance_overall: 1 }));
});
it('keeps failed saves visibly unsuccessful and preserves editable answers', async () => {
  api.saveDraft.mockRejectedValue(new Error('database unavailable'));
  render(<ResidentSurvey token="private-token" />); await screen.findByRole('heading', { name: survey.questionnaire.title });
  fireEvent.change(screen.getByRole('textbox', { name: 'Your comment?' }), { target: { value: 'Still leaking.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be saved');
  expect(screen.queryByRole('heading', { name: 'Thank you for your feedback' })).not.toBeInTheDocument();
  expect(screen.getByRole('textbox', { name: 'Your comment?' })).toHaveValue('Still leaking.');
});
it('waits for a pending draft before final submission and confirms only the persisted result', async () => {
  let finishDraft!: (value: SurveyInstance) => void;
  api.saveDraft.mockImplementation(() => new Promise(resolve => { finishDraft = resolve; }));
  render(<ResidentSurvey token="private-token" />); await screen.findByRole('heading', { name: survey.questionnaire.title });
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
  await waitFor(() => expect(api.saveDraft).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: 'Submit survey' }));
  expect(api.submit).not.toHaveBeenCalled();
  expect(screen.queryByRole('heading', { name: 'Thank you for your feedback' })).not.toBeInTheDocument();
  await act(async () => { finishDraft(survey); });
  expect(await screen.findByRole('heading', { name: 'Thank you for your feedback' })).toBeInTheDocument();
  expect(api.submit).toHaveBeenCalledTimes(1);
  expect(api.submit).toHaveBeenCalledWith('private-token', survey.draft_answers);
});
it('does not claim success for a failed or unconfirmed final write', async () => {
  api.submit.mockResolvedValue(survey);
  render(<ResidentSurvey token="private-token" />); await screen.findByRole('heading', { name: survey.questionnaire.title });
  fireEvent.click(screen.getByRole('button', { name: 'Submit survey' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('not been confirmed as submitted');
  expect(screen.queryByRole('heading', { name: 'Thank you for your feedback' })).not.toBeInTheDocument();
});
it('shows existing completed state without re-enabling answers or sending new writes', async () => {
  api.resident.mockResolvedValue(completed);
  render(<ResidentSurvey token="private-token" />);
  expect(await screen.findByRole('heading', { name: 'Thank you for your feedback' })).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Submit survey' })).not.toBeInTheDocument();
  expect(api.saveDraft).not.toHaveBeenCalled(); expect(api.submit).not.toHaveBeenCalled();
});
it('shows pending and completed instances with simulated invitation status and original detail links', async () => {
  mountDashboard(<SurveyDashboard />);
  expect(await screen.findByText('2 surveys')).toBeInTheDocument();
  expect(screen.getAllByText('Simulated invitation — no email sent')).toHaveLength(2);
  expect(screen.getAllByRole('link', { name: /View answers/ })[0]).toHaveAttribute('href', `/surveys/${survey.public_id}`);
  expect(screen.getByText('draft')).toBeInTheDocument(); expect(screen.getByText('submitted')).toBeInTheDocument();
});
it('shows the snapshotted original answers with readable labels and keeps ticket/submission dates separate', async () => {
  mountDashboard(<SurveyDetail id={survey.public_id} />);
  expect(await screen.findByRole('heading', { name: 'Original questions and answers' })).toBeInTheDocument();
  expect(screen.getByText('2 — Bad')).toBeInTheDocument(); expect(screen.getByText('Not sure')).toBeInTheDocument();
  expect(screen.getByText('No, still unresolved')).toBeInTheDocument(); expect(screen.getByText('The leak remains.')).toBeInTheDocument();
  expect(screen.getByText('Ticket marked completed')).toBeInTheDocument(); expect(screen.getByText('Survey submitted')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: 'Open resident survey' })).toHaveAttribute('rel', 'noreferrer');
  expect(screen.queryByText('Employee / vendor')).not.toBeInTheDocument();
  expect(screen.queryByText('not rendered')).not.toBeInTheDocument();
});
it('does not unsubscribe merely by opening the link; confirmation persists the preference', async () => {
  render(<SurveyUnsubscribe token="private-token" />);
  expect(api.unsubscribe).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Stop survey invitations' }));
  expect(await screen.findByRole('status')).toHaveTextContent('Future survey invitations for this community are stopped');
  expect(api.unsubscribe).toHaveBeenCalledWith('private-token');
});
