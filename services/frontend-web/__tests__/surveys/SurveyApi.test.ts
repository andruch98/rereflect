import { beforeEach, expect, it, vi } from 'vitest';
import { surveysAPI } from '@/lib/api/surveys';

const { get } = vi.hoisted(() => ({ get: vi.fn() }));
vi.mock('@/lib/api-client', () => ({ default: { get }, publicApiClient: {} }));
beforeEach(() => { get.mockReset(); get.mockResolvedValue({ data: { surveys: [], total: 0 } }); });

it('passes the selected survey type and page to the server', async () => {
  await surveysAPI.list(2, 50, 'lease_month_9');
  expect(get).toHaveBeenCalledExactlyOnceWith('/api/v1/surveys', { params: { page: 2, page_size: 50, event_type: 'lease_month_9' } });
});

it('omits the event filter when listing all surveys', async () => {
  await surveysAPI.list();
  expect(get).toHaveBeenCalledExactlyOnceWith('/api/v1/surveys', { params: { page: 1, page_size: 50 } });
});
