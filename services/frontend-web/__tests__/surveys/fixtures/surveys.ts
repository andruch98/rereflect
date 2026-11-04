import catalog from './original-survey-catalog.json';
import type { SurveyAnswers, SurveyEventType, SurveyInstance, SurveyQuestion } from '@/lib/api/surveys';

// Exact original catalog from andruch98/boomsay-agent@9af23a3:data/survey_catalog.json.
// Fictional resident inputs below exercise the existing rating, choice and text formats.
const cases: { id: string; label: string; dateLabel: string; answers: SurveyAnswers; labels: string[] }[] = [
  { id: 'move_in_v1', label: 'Move-in', dateLabel: 'Move-in completed', answers: { move_in_overall: 4, apartment_condition: 3, move_in_unresolved: 'yes', move_in_comment: 'Fictional move-in comment.' }, labels: ['4 — Good', '3 — Okay', 'Yes', 'Fictional move-in comment.'] },
  { id: 'maintenance_v1', label: 'Maintenance', dateLabel: 'Ticket marked completed', answers: { maintenance_overall: 2, issue_resolution: 'unresolved', maintenance_response_time: 'not_sure', maintenance_comment: 'Fictional maintenance comment.' }, labels: ['2 — Bad', 'No, still unresolved', 'Not sure', 'Fictional maintenance comment.'] },
  { id: 'lease_month_3_v1', label: '3-month', dateLabel: '3-month milestone', answers: { community_overall: 4, community_team_help: 'no_help_needed', follow_up_requested: 'yes', lease_month_3_comment: 'Fictional three-month comment.' }, labels: ['4 — Good', 'I haven’t needed help', 'Yes', 'Fictional three-month comment.'] },
  { id: 'lease_month_6_v1', label: '6-month', dateLabel: '6-month milestone', answers: { community_overall: 3, shared_spaces_upkeep: 'not_applicable', improvement_priority: 'parking', lease_month_6_comment: 'Fictional six-month comment.' }, labels: ['3 — Okay', 'Not applicable', 'Parking', 'Fictional six-month comment.'] },
  { id: 'lease_month_9_v1', label: '9-month renewal planning', dateLabel: '9-month milestone', answers: { community_overall: 3, renewal_intent: 'probably_not_renew', renewal_factor: 'rent_fees', lease_month_9_comment: 'Fictional renewal-planning comment.' }, labels: ['3 — Okay', 'Probably will not renew', 'Rent and fees', 'Fictional renewal-planning comment.'] },
  { id: 'lease_renewed_v1', label: 'Lease renewal', dateLabel: 'Lease renewed', answers: { community_overall: 4, renewal_process: 5, renewal_reason: 'avoid_move', renewal_comment: 'Fictional completed-renewal comment.' }, labels: ['4 — Good', '5 — Excellent', 'Avoiding a move', 'Fictional completed-renewal comment.'] },
  { id: 'move_out_v1', label: 'Move-out', dateLabel: 'Move-out completed', answers: { move_out_overall: 2, move_out_reason: 'prefer_not', move_out_instructions: 'not_received', move_out_comment: 'Fictional move-out comment.' }, labels: ['2 — Bad', 'Prefer not to answer', 'I did not receive instructions', 'Fictional move-out comment.'] },
];

export const surveyCases = cases.map((testCase, index) => {
  const template = catalog.templates.find(item => item.id === testCase.id)!;
  const render = (text: string) => text.replaceAll('{community_name}', 'Fictional Oaks').replaceAll('{request_description}', 'the kitchen leak');
  const survey: SurveyInstance = {
    public_id: `11111111-1111-4111-8111-${String(index + 1).padStart(12, '0')}`,
    status: 'draft', submitted_at: null,
    context: { community_name: 'Fictional Oaks', resident_name: 'Fictional Resident', unit_number: '204',
      event_type: template.event_type as SurveyEventType, survey_type_label: testCase.label,
      event_occurred_at: '2026-11-01T12:00:00Z',
      ...(template.event_type === 'maintenance_completed' ? { ticket_id: 'TEST-42', request_description: 'the kitchen leak', ticket_completed_at: '2026-11-01T12:00:00Z' } : {}),
    },
    questionnaire: { id: template.id, title: render(template.title), version: 1, catalog_version: catalog.catalog_version,
      rating_labels: catalog.rating_labels,
      questions: template.questions.map(question => ({ ...question, rendered_text: render(question.text) })) as SurveyQuestion[],
    },
    answers: {}, draft_answers: testCase.answers,
    invitation: { status: 'simulated', is_simulated: true, recipient: 'resident@example.invalid', subject: render(template.title), html: '', text: 'Fictional invitation.', survey_url: `http://localhost:3000/survey/fictional-${testCase.id}` },
  };
  return { ...testCase, survey, completed: { ...survey, status: 'submitted' as const, submitted_at: '2026-11-02T15:00:00Z', answers: testCase.answers } };
});
