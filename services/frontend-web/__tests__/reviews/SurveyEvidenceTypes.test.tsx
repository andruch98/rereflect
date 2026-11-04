import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { GeniusMessage } from '@/components/reviews/GeniusMessage';
import type { ChatMessage } from '@/components/copilot/ChatArea';
import { surveyCases } from '../surveys/fixtures/surveys';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api/surveys', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/api/surveys')>(), surveysAPI: { get } }));
function show(sources: unknown[], publicSnapshot = false) {
  return render(<GeniusMessage publicSnapshot={publicSnapshot} message={{ id: 1, role: 'assistant', content: 'Original survey evidence.', created_at: '', structured_data: { kind: 'ask_genius', sources } as ChatMessage['structured_data'] }} />);
}
afterEach(() => { cleanup(); vi.resetAllMocks(); });

it('identifies all seven survey snapshots and shows each original submitted answer without fetching', () => {
  show(surveyCases.map(({ completed, label, labels }) => ({ source: 'survey', survey_id: completed.public_id, survey: {
    title: completed.questionnaire.title, template_id: completed.questionnaire.id,
    event_type: completed.context.event_type, survey_type_label: label,
    questions: completed.questionnaire.questions.map((question, index) => ({ id: question.id, text: question.rendered_text, answer_label: labels[index] })),
  } })));
  expect(get).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'View answers from 7 surveys' }));
  const sections = within(screen.getByRole('dialog')).getAllByRole('region', { name: 'Original survey submission' });
  expect(sections).toHaveLength(7);
  surveyCases.forEach(({ completed, label, labels }, index) => {
    const section = sections[index];
    expect(within(section).getByRole('heading', { name: completed.questionnaire.title })).toBeInTheDocument();
    expect(within(section).getByText(label)).toBeInTheDocument();
    completed.questionnaire.questions.forEach(question => expect(section).toHaveTextContent(question.rendered_text));
    labels.forEach(answer => expect(section).toHaveTextContent(answer));
  });
  expect(get).not.toHaveBeenCalled();
});

it('keeps a legacy maintenance snapshot identifiable using its saved template ID', () => {
  show([{ source: 'survey', survey_id: surveyCases[1].completed.public_id, survey: { template_id: 'maintenance_v1', questions: [
    { id: 'issue_resolution', text: 'Is the issue fully resolved?', answer_label: 'No, still unresolved' },
  ] } }]);
  fireEvent.click(screen.getByRole('button', { name: 'View original answers' }));
  expect(screen.getByRole('dialog')).toHaveTextContent('Maintenance');
  expect(screen.getByRole('dialog')).toHaveTextContent('No, still unresolved');
  expect(get).not.toHaveBeenCalled();
});

it('loads the title, type and original answers for an older source without a snapshot', async () => {
  const { completed, labels } = surveyCases[6];
  get.mockResolvedValue(completed);
  show([{ source: 'survey', survey_id: completed.public_id }]);
  expect(get).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'View original answers' }));
  const modal = screen.getByRole('dialog');
  expect(await within(modal).findByRole('heading', { name: completed.questionnaire.title })).toBeInTheDocument();
  expect(modal).toHaveTextContent('Move-out');
  labels.forEach(answer => expect(modal).toHaveTextContent(answer));
  expect(get).toHaveBeenCalledExactlyOnceWith(completed.public_id);
});

it('keeps the new survey labels and private snapshots out of public chats', () => {
  const { completed } = surveyCases[5];
  show([{ source: 'survey', survey_id: completed.public_id, survey: { title: completed.questionnaire.title, survey_type_label: 'Lease renewal', questions: [{ id: 'renewal_comment', text: 'Private question', answer_label: 'Private resident answer.' }] } }], true);
  expect(screen.queryByRole('button', { name: /View.*answers/ })).not.toBeInTheDocument();
  expect(screen.queryByText(completed.questionnaire.title)).not.toBeInTheDocument();
  expect(screen.queryByText('Private resident answer.')).not.toBeInTheDocument();
  expect(get).not.toHaveBeenCalled();
});
