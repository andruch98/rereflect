import type { ReplyStatus } from '../review-response-status';
import apiClient from '../api-client';

export interface ReviewReply {
  review_id: number;
  status: ReplyStatus;
  text: string | null;
  reason: string | null;
  version: number;
  approved_by: string | null;
  approved_at: string | null;
  published_at: string | null;
  publishing_connected: boolean;
  generation_method: 'example' | 'ai' | null;
  settings_confirmed: boolean;
  uses_previous_settings?: boolean;
  error: string | null;
}

const base = '/api/v1/review-replies';

export const reviewRepliesAPI = {
  async get(id: number): Promise<ReviewReply> {
    return (await apiClient.get<ReviewReply>(`${base}/${id}`)).data;
  },
  async draft(id: number): Promise<ReviewReply> {
    return (await apiClient.post<ReviewReply>(`${base}/${id}/draft`)).data;
  },
  async save(id: number, version: number, text: string): Promise<ReviewReply> {
    return (await apiClient.put<ReviewReply>(`${base}/${id}`, { version, text })).data;
  },
  async approve(id: number, version: number): Promise<ReviewReply> {
    return (await apiClient.post<ReviewReply>(`${base}/${id}/approve`, { version })).data;
  },
};
