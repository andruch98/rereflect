import { isAxiosError } from 'axios';
import apiClient from '@/lib/api-client';
import type { SurveyEventType } from './surveys';

export type HoldTopic = 'safety' | 'billing' | 'legal' | 'staff_allegations';
export type ReviewSettings = {
  community_name: string; public_email: string; public_phone: string; facts: string;
  tone: 'warm' | 'professional' | 'concise'; signature: string;
  praise_guidance: string; complaint_guidance: string;
  mode: 'approval' | 'automatic'; hold_at_or_below: number; hold_topics: HoldTopic[];
};
export type SurveySettings = {
  schedule: Record<SurveyEventType, { enabled: boolean; delay_hours: number }>;
  reminder_hours: number | null; flag_low_ratings: boolean; flag_unresolved: boolean;
};
export type SettingSection<T> = { version: number; configured: boolean; values: T };
export type CommunitySettings = {
  can_edit: boolean; community_name: string;
  reviews: SettingSection<ReviewSettings>; surveys: SettingSection<SurveySettings>;
};
export type SampleReply = {
  review_text: string; star_rating: number; text: string;
  status: 'pending_approval' | 'approved'; reason: string; generation_method: 'example' | 'ai';
};
type Preview = { examples: SampleReply[]; publishing_connected: boolean };
export function settingsError(error: unknown, fallback: string) {
  const detail = isAxiosError(error) ? error.response?.data?.detail : null;
  if (typeof detail === 'string') return detail;
  if (!Array.isArray(detail)) return fallback;
  const [first] = detail;
  const field = Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : undefined;
  if (field === 'public_email') return 'Enter a complete public email address or leave it blank.';
  if (field === 'community_name') return 'Enter the community name you want to use in replies.';
  return fallback;
}
const base = '/api/v1/agent-settings';
export const agentSettingsAPI = {
  async preview(values: ReviewSettings): Promise<Preview> {
    return (await apiClient.post<Preview>('/api/v1/review-replies/preview', values)).data;
  },
  async get(): Promise<CommunitySettings> {
    return (await apiClient.get<CommunitySettings>(base)).data;
  },
  async save<T extends ReviewSettings | SurveySettings>(section: 'reviews' | 'surveys', version: number, values: T) {
    return (await apiClient.put<SettingSection<T>>(`${base}/${section}`, { version, values })).data;
  },
};
