import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SurveyDashboard, SurveyDetail } from '@/components/surveys/SurveyDashboard';
import type { SurveyInstance, SurveyListScope } from '@/lib/api/surveys';
import { readSurveyFilters } from '@/lib/survey-list-filters';
import { surveyCases } from './fixtures/surveys';

const { api, user } = vi.hoisted(() => ({
  api: { list: vi.fn(), get: vi.fn(), markReviewed: vi.fn() }, user: { id: 1, organization_id: 11, role: 'admin' },
}));
vi.mock('@/lib/api/surveys', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/api/surveys')>(), surveysAPI: api }));
vi.mock('@/contexts/AuthContext', () => ({ useAuth: () => ({ user }) }));

const sample = surveyCases.find(item => item.id === 'maintenance_v1')!;
const submitted: SurveyInstance = {
  ...sample.completed,
  attention_reasons: sample.completed.questionnaire.questions.slice(0, 2).map((question, index) => ({
    question_id: question.id, label: question.rendered_text, answer: sample.labels[index],
  })),
};
const reviewed: SurveyInstance = { ...submitted, reviewed_at: '2026-11-03T16:00:00Z', reviewed_by: 'Jo Manager' };

function mount(children: React.ReactNode, client = new QueryClient()) {
  return render(<QueryClientProvider client={client}>{children}</QueryClientProvider>);
}
beforeEach(() => {
  api.get.mockResolvedValue(submitted);
  api.list.mockResolvedValue({ surveys: [submitted], total: 1, counts: { needs_review: 1, submitted: 31, sent: 0 } });
  user.role = 'admin';
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  window.history.replaceState({}, '', '/surveys');
});

it('uses full filtered counts, opens the flagged original answer from the row and preserves the queue on return', async () => {
  const client = new QueryClient();
  const list = mount(<SurveyDashboard />, client);
  expect(await screen.findByRole('button', { name: 'Responses received 31' })).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Survey type'), { target: { value: 'maintenance_completed' } });
  fireEvent.change(screen.getByLabelText('From'), { target: { value: '2026-11-01' } });
  fireEvent.change(screen.getByLabelText('Through'), { target: { value: '2026-11-03' } });
  fireEvent.click(await screen.findByRole('button', { name: 'Needs review 1' }));
  await waitFor(() => expect(api.list).toHaveBeenLastCalledWith(1, 50, 'maintenance_completed', {
    start_date: '2026-11-01', end_date: '2026-11-03', view: 'needs_review',
  }));
  const row = await screen.findByRole('row', { name: /Fictional Resident/ });
  const original = within(row).getByRole('link', { name: submitted.attention_reasons![0].label + ' ' + submitted.attention_reasons![0].answer });
  expect(original.getAttribute('href')).toContain('#answer-maintenance_overall');
  const extra = within(row).getByRole('link', { name: submitted.attention_reasons![1].label + ' ' + submitted.attention_reasons![1].answer });
  expect(within(row).queryByText(/more flagged answer/)).not.toBeInTheDocument();
  expect(extra.getAttribute('href')).toContain('#answer-issue_resolution');
  const listPath = window.location.pathname + window.location.search;
  const search = Object.fromEntries(new URLSearchParams(window.location.search));
  list.unmount();
  window.history.replaceState({}, '', extra.getAttribute('href'));
  mount(<SurveyDetail id={submitted.public_id} listFilters={readSurveyFilters(search)} />, client);
  expect(await screen.findByRole('region', { name: 'Original questions and answers' })).toHaveTextContent('No, still unresolved');
  expect(document.activeElement?.id).toBe('answer-issue_resolution');
  expect(screen.getByRole('link', { name: 'Back to Surveys' })).toHaveAttribute('href', listPath);
});

it('records a manager read, refreshes the queue, and keeps the resident’s unresolved answer', async () => {
  let saved = false;
  api.list.mockImplementation(async (_page: number, _size: number, _type: string, filters: SurveyListScope) => ({
    surveys: (filters.view === 'needs_review' && saved) ? [] : [saved ? reviewed : submitted],
    total: filters.view === 'needs_review' && saved ? 0 : 1, counts: { sent: 0, submitted: 1, needs_review: saved ? 0 : 1 },
  }));
  api.markReviewed.mockImplementation(async () => { saved = true; return reviewed; });
  const client = new QueryClient();
  const filters = readSurveyFilters({ view: 'needs_review' });
  const list = mount(<SurveyDashboard initialFilters={filters} />, client);
  expect(await screen.findByRole('button', { name: 'Needs review 1' })).toBeInTheDocument();
  list.unmount();
  const detail = mount(<SurveyDetail id={submitted.public_id} listFilters={filters} />, client);
  fireEvent.click(await screen.findByRole('button', { name: 'Mark reviewed' }));
  expect(await screen.findByText('Reviewed by Jo Manager')).toBeInTheDocument();
  expect(api.markReviewed).toHaveBeenCalledExactlyOnceWith(submitted.public_id);
  expect(screen.getByRole('region', { name: 'Manager review' }).querySelector('time')).toHaveAttribute('datetime', reviewed.reviewed_at);
  expect(screen.getByRole('region', { name: 'Original questions and answers' })).toHaveTextContent('No, still unresolved');
  detail.unmount();
  mount(<SurveyDashboard initialFilters={filters} />, client);
  expect(await screen.findByText('No responses are waiting for review in this view.')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Needs review 0' })).toBeInTheDocument();
  fireEvent.change(screen.getByRole('combobox', { name: 'Show' }), { target: { value: 'reviewed' } });
  expect(await screen.findByText('Reviewed by Jo Manager')).toBeInTheDocument();
});

it('keeps an unsuccessful review actionable and waits for the saved receipt', async () => {
  api.markReviewed.mockRejectedValueOnce(new Error('Connection dropped')).mockResolvedValueOnce(submitted).mockResolvedValueOnce(reviewed);
  mount(<SurveyDetail id={submitted.public_id} />);
  fireEvent.click(await screen.findByRole('button', { name: 'Mark reviewed' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('could not be confirmed');
  fireEvent.click(screen.getByRole('button', { name: 'Mark reviewed' }));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('could not be confirmed'));
  expect(screen.queryByText(/^Reviewed by/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Mark reviewed' }));
  expect(await screen.findByText('Reviewed by Jo Manager')).toBeInTheDocument();
});

it('keeps read-only accounts and incomplete drafts out of manager review actions', async () => {
  user.role = 'member';
  const detail = mount(<SurveyDetail id={submitted.public_id} />);
  expect(await screen.findByText('A community administrator or owner can mark this response reviewed.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Mark reviewed' })).not.toBeInTheDocument();
  detail.unmount();
  user.role = 'admin';
  api.get.mockResolvedValue(sample.survey);
  mount(<SurveyDetail id={submitted.public_id} />);
  await screen.findByRole('heading', { name: sample.survey.questionnaire.title });
  expect(screen.queryByRole('region', { name: 'Manager review' })).not.toBeInTheDocument();
});

it('shows why test emails and simulations can coexist with zero invitations sent', async () => {
  api.list.mockImplementation(async (_, __, ___, filters: SurveyListScope) => ({
    surveys: filters.view === 'sent' ? [] : [submitted], total: filters.view === 'sent' ? 0 : 1,
    counts: { sent: 0, submitted: 1, needs_review: 1 },
  }));
  mount(<SurveyDashboard />);
  fireEvent.click(await screen.findByRole('button', { name: 'Invitations sent 0' }));
  expect(await screen.findByText('No confirmed invitations in this view.')).toBeInTheDocument();
  expect(screen.getByText(/Test emails and simulations are excluded/)).toBeInTheDocument();
});

it('blocks an inverted date range and allows clearing it without making a failed request', async () => {
  mount(<SurveyDashboard initialFilters={readSurveyFilters({ start_date: '2026-11-03', end_date: '2026-11-02' })} />);
  expect(screen.getByRole('alert')).toHaveTextContent('Choose an end date on or after the start date.');
  expect(api.list).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Clear filters' }));
  expect(await screen.findByRole('button', { name: 'Responses received 31' })).toBeInTheDocument();
});

it('shows scheduled and simulated delivery times as distinct from email sends', async () => {
  api.get.mockResolvedValue({ ...sample.survey, invitation: {
    ...sample.survey.invitation!, status: 'scheduled', scheduled_for: '2026-11-03T16:00:00Z',
  } });
  const detail = mount(<SurveyDetail id={submitted.public_id} />);
  expect((await screen.findAllByText('Invitation simulation scheduled')).length).toBeGreaterThan(0);
  expect(screen.getByRole('region', { name: 'Simulated invitation' })).toHaveTextContent('Scheduled for');
  detail.unmount();
  api.get.mockResolvedValue({ ...sample.survey, invitation: {
    ...sample.survey.invitation!, status: 'simulated', reminder_simulated_at: '2026-11-03T16:00:00Z',
  } });
  mount(<SurveyDetail id={submitted.public_id} />);
  expect(await screen.findByText('Reminder simulated')).toBeInTheDocument();
  expect(screen.queryByText('Email accepted')).not.toBeInTheDocument();
});
