import { afterEach, expect, it, vi } from 'vitest';

const mock = vi.hoisted(() => ({ init: vi.fn(), identify: vi.fn(), people: { set: vi.fn() }, track: vi.fn(), reset: vi.fn() }));
vi.mock('mixpanel-browser', () => ({ default: mock }));
afterEach(() => { vi.unstubAllEnvs(); vi.resetModules(); vi.clearAllMocks(); window.history.replaceState(null, '', '/'); });

it('does not initialize or track during preview navigation into a public snapshot', async () => {
  vi.stubEnv('NODE_ENV', 'production'); vi.stubEnv('NEXT_PUBLIC_MIXPANEL_TOKEN', 'test'); vi.stubEnv('NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW', 'true');
  const analytics = await import('@/lib/analytics');
  window.history.replaceState(null, '', '/ask-genius'); analytics.initAnalytics(); analytics.identifyUser('1');
  window.history.replaceState(null, '', '/share/ask-genius/bearer-token'); analytics.initAnalytics(); analytics.trackEvent('Shared chat');
  expect(mock.init).not.toHaveBeenCalled(); expect(mock.track).not.toHaveBeenCalled(); expect(mock.identify).not.toHaveBeenCalled();
});
it('excludes direct anonymous share URLs even outside preview configuration', async () => {
  vi.stubEnv('NODE_ENV', 'production'); vi.stubEnv('NEXT_PUBLIC_MIXPANEL_TOKEN', 'test'); vi.stubEnv('NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW', 'false');
  window.history.replaceState(null, '', '/share/ask-genius/bearer-token');
  const analytics = await import('@/lib/analytics'); analytics.initAnalytics(); analytics.trackEvent('Shared chat');
  expect(mock.init).not.toHaveBeenCalled(); expect(mock.track).not.toHaveBeenCalled();
});
