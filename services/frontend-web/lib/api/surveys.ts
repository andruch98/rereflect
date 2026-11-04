import apiClient, { publicApiClient } from '../api-client';

export type SurveyAnswers = Record<string, string | number | null>;

export const SURVEY_TYPES = [
  { eventType: 'move_in_completed', templateId: 'move_in_v1', label: 'Move-in', dateLabel: 'Move-in completed' },
  { eventType: 'maintenance_completed', templateId: 'maintenance_v1', label: 'Maintenance', dateLabel: 'Ticket marked completed' },
  { eventType: 'lease_month_3', templateId: 'lease_month_3_v1', label: '3-month', dateLabel: '3-month milestone' },
  { eventType: 'lease_month_6', templateId: 'lease_month_6_v1', label: '6-month', dateLabel: '6-month milestone' },
  { eventType: 'lease_month_9', templateId: 'lease_month_9_v1', label: '9-month renewal planning', dateLabel: '9-month milestone' },
  { eventType: 'lease_renewed', templateId: 'lease_renewed_v1', label: 'Lease renewal', dateLabel: 'Lease renewed' },
  { eventType: 'move_out_completed', templateId: 'move_out_v1', label: 'Move-out', dateLabel: 'Move-out completed' },
] as const;
export type SurveyEventType = typeof SURVEY_TYPES[number]['eventType'];

/** Legacy survey snapshots have a template ID but no event type. */
export function surveyType(eventType?: string, templateId?: string) {
  return SURVEY_TYPES.find(type => type.eventType === eventType)
    ?? SURVEY_TYPES.find(type => type.templateId === templateId);
}

export interface SurveyOption { value: string; label: string }
export interface SurveyQuestion {
  id: string;
  text: string;
  rendered_text: string;
  type: 'rating' | 'single_choice' | 'text';
  required: boolean;
  options?: SurveyOption[];
  special_options?: SurveyOption[];
  max_length?: number;
}
export interface SurveyQuestionnaire {
  id: string;
  title: string;
  version: number;
  catalog_version: number;
  rating_labels: Record<string, string>;
  questions: SurveyQuestion[];
}
export interface SurveyContext {
  community_name: string;
  event_type?: SurveyEventType;
  survey_type_label?: string;
  event_occurred_at?: string | null;
  request_description?: string | null;
  ticket_id?: string | null;
  ticket_completed_at?: string | null;
  resident_id?: string;
  resident_name?: string;
  unit_id?: string;
  unit_number?: string;
  employee_id?: string | null;
  employee_name?: string | null;
}
export interface SurveyInvitation {
  status: string;
  is_simulated: boolean;
  recipient: string;
  subject: string;
  html: string;
  text: string;
  survey_url: string;
}
export interface SurveyInstance {
  public_id: string;
  status: 'pending' | 'draft' | 'submitted';
  submitted_at: string | null;
  questionnaire: SurveyQuestionnaire;
  context: SurveyContext;
  answers: SurveyAnswers;
  draft_answers: SurveyAnswers;
  invitation?: SurveyInvitation;
}

export const surveysAPI = {
  async list(page = 1, pageSize = 50, eventType?: SurveyEventType) {
    return (await apiClient.get<{ surveys: SurveyInstance[]; total: number }>('/api/v1/surveys', {
      params: { page, page_size: pageSize, ...(eventType ? { event_type: eventType } : {}) },
    })).data;
  },
  async get(id: string) {
    return (await apiClient.get<SurveyInstance>(`/api/v1/surveys/${encodeURIComponent(id)}`)).data;
  },
  async resident(token: string) {
    return (await publicApiClient.get<SurveyInstance>(`/api/v1/resident-surveys/${encodeURIComponent(token)}`)).data;
  },
  async saveDraft(token: string, answers: SurveyAnswers) {
    return (await publicApiClient.put<SurveyInstance>(`/api/v1/resident-surveys/${encodeURIComponent(token)}/draft`, { answers })).data;
  },
  async submit(token: string, answers: SurveyAnswers) {
    return (await publicApiClient.post<SurveyInstance>(`/api/v1/resident-surveys/${encodeURIComponent(token)}/submit`, { answers })).data;
  },
  async unsubscribe(token: string) {
    return (await publicApiClient.post<{ status: string; message: string }>(`/api/v1/resident-surveys/${encodeURIComponent(token)}/unsubscribe`)).data;
  },
};

export function surveyAnswerLabel(question: SurveyQuestion, value: string | number | null | undefined, questionnaire: SurveyQuestionnaire): string {
  if (value == null || value === '') return question.required ? 'No answer' : 'No comment provided';
  if (question.type === 'rating' && typeof value === 'number') {
    const label = questionnaire.rating_labels[String(value)];
    return label ? `${value} — ${label}` : String(value);
  }
  return [...(question.options ?? []), ...(question.special_options ?? [])].find(option => option.value === value)?.label ?? String(value);
}

export function surveyTypeLabel(survey: SurveyInstance): string {
  return survey.context.survey_type_label || surveyType(survey.context.event_type, survey.questionnaire.id)?.label || 'Survey';
}

export function surveyDate(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
