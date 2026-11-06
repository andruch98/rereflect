import { SURVEY_TYPES, type SurveyEventType, type SurveyView } from './api/surveys';

export const surveyViews: Record<SurveyView, string> = {
  all: 'All activity',
  sent: 'Invitations sent',
  submitted: 'Responses received',
  needs_review: 'Needs review',
  reviewed: 'Reviewed',
};

export interface SurveyFilters {
  eventType: SurveyEventType | '';
  startDate: string;
  endDate: string;
  view: SurveyView;
  page: number;
}

export const defaultSurveyFilters: SurveyFilters = {
  eventType: '', startDate: '', endDate: '', view: 'all', page: 1,
};

export type SurveySearchParams = Record<string, string | string[] | undefined>;

function validDate(value: unknown): string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return '';
  const time = Date.parse(value);
  return Number.isFinite(time) && new Date(time).toISOString().startsWith(value) ? value : '';
}

export function readSurveyFilters(params: SurveySearchParams): SurveyFilters {
  const page = Number(params.page);
  return {
    eventType: SURVEY_TYPES.find(item => item.eventType === params.event_type)?.eventType ?? '',
    startDate: validDate(params.start_date),
    endDate: validDate(params.end_date),
    view: typeof params.view === 'string' && Object.hasOwn(surveyViews, params.view) ? params.view as SurveyView : 'all',
    page: Number.isSafeInteger(page) && page > 0 ? page : 1,
  };
}

export function surveyHref(filters: SurveyFilters, id?: string) {
  const query = new URLSearchParams();
  if (filters.eventType) query.set('event_type', filters.eventType);
  if (filters.startDate) query.set('start_date', filters.startDate);
  if (filters.endDate) query.set('end_date', filters.endDate);
  if (filters.view !== 'all') query.set('view', filters.view);
  if (filters.page > 1) query.set('page', String(filters.page));
  return '/surveys' + (id ? '/' + encodeURIComponent(id) : '') + (query.size ? '?' + query : '');
}
