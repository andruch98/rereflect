import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ResidentSurvey } from '@/components/surveys/ResidentSurvey';
import { SurveyDashboard, SurveyDetail } from '@/components/surveys/SurveyDashboard';
import type { SurveyAnswers } from '@/lib/api/surveys';
import { surveyCases } from './fixtures/surveys';

const api = vi.hoisted(() => ({ resident: vi.fn(), saveDraft: vi.fn(), submit: vi.fn(), list: vi.fn(), get: vi.fn() }));
vi.mock('@/lib/api/surveys', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/api/surveys')>(), surveysAPI: api }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user: { id: 1, organization_id: 11 } }) }));
function mountManager(children: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>);
}
beforeEach(() => { api.list.mockResolvedValue({ surveys: surveyCases.map(item => item.completed), total: 7 }); });
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it.each(surveyCases)('resumes, saves and submits the original $id questionnaire with its own context', async ({ id, label, survey, completed, labels }) => {
  const token = `fictional-${id}`;
  api.resident.mockResolvedValue(survey);
  api.saveDraft.mockResolvedValue(survey);
  api.submit.mockImplementation(async (_token: string, answers: SurveyAnswers) => ({ ...completed, answers }));
  render(<ResidentSurvey token={token} />);
  expect(await screen.findByRole('heading', { name: survey.questionnaire.title })).toBeInTheDocument();
  expect(screen.getByText(label, { selector: 'p' })).toBeInTheDocument();
  survey.questionnaire.questions.forEach((question, index) => {
    const field = screen.getByRole('group', { name: `${question.rendered_text}${question.required ? '' : ' (optional)'}` });
    if (question.type === 'text') {
      expect(within(field).getByRole('textbox')).toHaveValue(labels[index]);
      expect(within(field).getByRole('textbox')).toHaveAttribute('maxlength', '2000');
    } else {
      expect(within(field).getByRole('radio', { name: labels[index] })).toBeChecked();
      expect(within(field).getByRole('radio', { name: labels[index] })).toBeRequired();
    }
  });
  if (id === 'maintenance_v1') {
    expect(screen.getByText(/Maintenance request: the kitchen leak/)).toHaveTextContent('Ticket: TEST-42');
  } else {
    expect(screen.queryByText(/Maintenance request:|Ticket:/)).not.toBeInTheDocument();
  }
  const firstQuestion = survey.questionnaire.questions[0];
  const comment = survey.questionnaire.questions[3];
  fireEvent.click(within(screen.getByRole('group', { name: firstQuestion.rendered_text })).getByRole('radio', { name: '5 — Excellent' }));
  fireEvent.change(screen.getByRole('textbox'), { target: { value: `Updated fictional ${id} feedback.` } });
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }));
  const updated = { ...survey.draft_answers, [firstQuestion.id]: 5, [comment.id]: `Updated fictional ${id} feedback.` };
  await waitFor(() => expect(api.saveDraft).toHaveBeenCalledWith(token, updated));
  await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Draft saved.'));
  fireEvent.click(screen.getByRole('button', { name: 'Submit survey' }));
  const confirmation = await screen.findByRole('region', { name: 'Survey confirmation' });
  expect(confirmation).toHaveTextContent('Your survey has been submitted.');
  expect(confirmation).toHaveTextContent(`${label} · Fictional Oaks`);
  expect(confirmation).not.toHaveTextContent('Your maintenance survey');
  expect(api.submit).toHaveBeenCalledExactlyOnceWith(token, updated);
});

it.each(surveyCases)('shows the original $id answers and separates the event date from submission', async ({ id, label, dateLabel, completed, labels }) => {
  api.get.mockResolvedValue(completed);
  mountManager(<SurveyDetail id={completed.public_id} />);
  expect(await screen.findByRole('heading', { name: completed.questionnaire.title })).toBeInTheDocument();
  const context = screen.getByRole('region', { name: id === 'maintenance_v1' ? 'Maintenance context' : 'Survey context' });
  expect(context).toHaveTextContent(label);
  expect(context).toHaveTextContent(dateLabel);
  expect(context).toHaveTextContent(new Date('2026-11-01T12:00:00Z').toLocaleString());
  expect(context).toHaveTextContent('Survey submitted');
  expect(context).toHaveTextContent(new Date('2026-11-02T15:00:00Z').toLocaleString());
  if (id !== 'maintenance_v1') expect(context).not.toHaveTextContent(/Maintenance ticket|Request|Ticket marked completed|Employee \/ vendor/);
  const answers = screen.getByRole('region', { name: 'Original questions and answers' });
  completed.questionnaire.questions.forEach(question => expect(answers).toHaveTextContent(question.rendered_text));
  labels.forEach(value => expect(answers).toHaveTextContent(value));
  expect(screen.getByRole('link', { name: 'Open resident survey' })).toHaveAttribute('href', completed.invitation!.survey_url);
});

it('lists mixed survey types with their existing links and a ticket only for maintenance', async () => {
  mountManager(<SurveyDashboard />);
  const table = await screen.findByRole('table', { name: 'Surveys for your community' });
  expect(within(table).getAllByRole('row')).toHaveLength(8);
  for (const { label, completed } of surveyCases) {
    const link = within(table).getByRole('link', { name: `View answers for ${label} — Fictional Resident${completed.context.ticket_id ? ' — ticket TEST-42' : ''}` });
    expect(link).toHaveAttribute('href', `/surveys/${completed.public_id}`);
    expect(link.closest('tr')).toHaveTextContent(label);
  }
  expect(within(table).getAllByText('Ticket TEST-42')).toHaveLength(1);
  expect(screen.queryByText('Maintenance survey invitations and resident responses.')).not.toBeInTheDocument();
});

it('filters every survey kind through the API and resets pagination when the type changes', async () => {
  api.list.mockImplementation(async (_page: number, _size: number, eventType?: string) => ({
    surveys: surveyCases.filter(item => !eventType || item.survey.context.event_type === eventType).map(item => item.completed), total: eventType ? 1 : 51,
  }));
  mountManager(<SurveyDashboard />);
  await screen.findByText('51 surveys');
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  await waitFor(() => expect(api.list).toHaveBeenLastCalledWith(2, 50, undefined));
  for (const { label, survey } of surveyCases) {
    fireEvent.change(screen.getByRole('combobox', { name: 'Survey type' }), { target: { value: survey.context.event_type } });
    await waitFor(() => expect(api.list).toHaveBeenLastCalledWith(1, 50, survey.context.event_type));
    const table = await screen.findByRole('table');
    expect(within(table).getAllByRole('row')).toHaveLength(2);
    expect(table).toHaveTextContent(label);
    expect(screen.getByText('Page 1')).toBeInTheDocument();
  }
  fireEvent.change(screen.getByRole('combobox', { name: 'Survey type' }), { target: { value: '' } });
  await waitFor(() => expect(api.list).toHaveBeenLastCalledWith(1, 50, undefined));
  expect(await screen.findByText('51 surveys')).toBeInTheDocument();
});

it('uses a generic empty state and a specific empty state for a selected type', async () => {
  api.list.mockResolvedValue({ surveys: [], total: 0 });
  mountManager(<SurveyDashboard />);
  expect(await screen.findByText('No surveys yet.')).toBeInTheDocument();
  fireEvent.change(screen.getByRole('combobox', { name: 'Survey type' }), { target: { value: 'move_in_completed' } });
  expect(await screen.findByText('No surveys of this type yet.')).toBeInTheDocument();
});
