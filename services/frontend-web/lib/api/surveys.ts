import apiClient, { publicApiClient } from '../api-client';

export type SurveyAnswers = Record<string, string | number | null>;

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
  request_description: string;
  ticket_id: string;
  ticket_completed_at: string;
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
  async list(page = 1, pageSize = 50) {
    return (await apiClient.get<{ surveys: SurveyInstance[]; total: number }>('/api/v1/surveys', {
      params: { page, page_size: pageSize },
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

export function surveyDate(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}
