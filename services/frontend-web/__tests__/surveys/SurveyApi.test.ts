import { beforeEach, expect, it, vi } from 'vitest';
import { surveysAPI } from '@/lib/api/surveys';

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }));
vi.mock('@/lib/api-client', () => ({ default: { get, post }, publicApiClient: {} }));
beforeEach(() => { get.mockReset(); get.mockResolvedValue({ data: { surveys: [], total: 0 } }); });

it('passes the selected survey type and page to the server', async () => {
  await surveysAPI.list(2, 50, 'lease_month_9');
  expect(get).toHaveBeenCalledExactlyOnceWith('/api/v1/surveys', { params: { page: 2, page_size: 50, event_type: 'lease_month_9' } });
});

it('omits the event filter when listing all surveys', async () => {
  await surveysAPI.list();
  expect(get).toHaveBeenCalledExactlyOnceWith('/api/v1/surveys', { params: { page: 1, page_size: 50 } });
});

it('sends only the requested dates, record view, type and page for the manager dashboard', async () => {
  await surveysAPI.list(1, 50, 'lease_month_3', { view: 'needs_review', start_date: '2026-11-01', end_date: '2026-11-03' });
  expect(get).toHaveBeenCalledExactlyOnceWith('/api/v1/surveys', { params: {
    page: 1, page_size: 50, event_type: 'lease_month_3', start_date: '2026-11-01', end_date: '2026-11-03', view: 'needs_review',
  } });
});

it('posts the manager review to the selected record without submitting new survey answers', async () => {
  post.mockResolvedValue({ data: { public_id: 'survey-1', reviewed_at: '2026-11-01T17:00:00Z', reviewed_by: 'manager' } });
  expect((await surveysAPI.markReviewed('survey-1')).reviewed_by).toBe('manager');
  expect(post).toHaveBeenCalledExactlyOnceWith('/api/v1/surveys/survey-1/reviewed');
});
