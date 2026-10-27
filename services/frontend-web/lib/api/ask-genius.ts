import apiClient from '../api-client';
import type { ChatMessage } from '@/components/copilot/ChatArea';

export interface GeniusConversation {
  public_id: string;
  title: string;
  updated_at?: string;
}

export interface GeniusAnswer {
  conversation_id: string;
  title: string;
  answer: string;
  message_id: number;
  structured_data?: Record<string, unknown>[] | Record<string, unknown> | null;
}

export const askGeniusAPI = {
  async status() {
    return (await apiClient.get<{ ready: boolean; reason?: string }>('/api/v1/ask-genius/status')).data;
  },
  async conversations() {
    return (await apiClient.get<{ conversations: GeniusConversation[]; total: number }>('/api/v1/ask-genius/conversations')).data;
  },
  async conversation(id: string) {
    return (await apiClient.get<GeniusConversation & { messages: ChatMessage[] }>(`/api/v1/ask-genius/conversations/${encodeURIComponent(id)}`)).data;
  },
  async ask(question: string, requestId: string, conversationId?: string) {
    return (await apiClient.post<GeniusAnswer>('/api/v1/ask-genius/questions', {
      question, request_id: requestId, ...(conversationId ? { conversation_id: conversationId } : {}),
    })).data;
  },
};
