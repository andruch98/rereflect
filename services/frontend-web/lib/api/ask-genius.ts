import apiClient from '../api-client';
import type { ChatMessage } from '@/components/copilot/ChatArea';

export type GeniusPeriodPreset = 'last_7_days' | 'last_14_days' | 'last_30_days' | 'last_month' | 'last_quarter' | 'last_6_months' | 'year_to_date' | 'all_time' | 'custom';

export interface GeniusPeriod {
  preset: GeniusPeriodPreset;
  start_date?: string;
  end_date?: string;
}

export interface GeniusStatus {
  ready: boolean;
  reason?: string;
  default_period: GeniusPeriod | null;
  available_sources: string[];
  timezone: string;
  date_coverage: { total_reviews: number; dated_reviews: number; undated_reviews: number };
}

export interface GeniusConversation {
  public_id: string;
  title: string;
  updated_at?: string;
  period?: GeniusPeriod | null;
}

export interface GeniusAnswer {
  conversation_id: string;
  title: string;
  answer: string;
  message_id: number;
  structured_data?: Record<string, unknown>[] | Record<string, unknown> | null;
  period: GeniusPeriod | null;
  default_period: GeniusPeriod | null;
  preference_updated: boolean;
}

export const askGeniusAPI = {
  async status() {
    return (await apiClient.get<GeniusStatus>('/api/v1/ask-genius/status')).data;
  },
  async saveDefaultPeriod(period: GeniusPeriod | null) {
    return (await apiClient.put<{ default_period: GeniusPeriod | null }>('/api/v1/ask-genius/preferences', { default_period: period })).data;
  },
  async conversations() {
    return (await apiClient.get<{ conversations: GeniusConversation[]; total: number }>('/api/v1/ask-genius/conversations')).data;
  },
  async conversation(id: string) {
    return (await apiClient.get<GeniusConversation & { messages: ChatMessage[] }>(`/api/v1/ask-genius/conversations/${encodeURIComponent(id)}`)).data;
  },
  async ask(question: string, requestId: string, conversationId?: string, period?: GeniusPeriod | null) {
    return (await apiClient.post<GeniusAnswer>('/api/v1/ask-genius/questions', {
      question, request_id: requestId, ...(conversationId ? { conversation_id: conversationId } : {}),
      ...(period ? { period } : {}),
    })).data;
  },
};
