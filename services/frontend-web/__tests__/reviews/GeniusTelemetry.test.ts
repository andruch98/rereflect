import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const sentry = vi.hoisted(() => ({ init: vi.fn(), replayIntegration: vi.fn(), captureRouterTransitionStart: vi.fn() }));
vi.mock('@sentry/nextjs', () => sentry);

describe('Ask Genius telemetry boundaries', () => {
  beforeEach(() => {
    vi.resetModules(); vi.clearAllMocks();
    vi.stubEnv('NEXT_PUBLIC_SENTRY_DSN', 'https://synthetic.invalid/1');
    vi.stubEnv('SENTRY_DSN', 'https://synthetic.invalid/1');
    vi.stubEnv('NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW', 'true');
    window.history.replaceState({}, '', '/ask-genius');
  });
  afterEach(() => { vi.unstubAllEnvs(); window.history.replaceState({}, '', '/'); });

  it('does not initialize session recording in the preview', async () => {
    const instrumentation = await import('../../instrumentation-client');
    await import('../../sentry.client.config');
    instrumentation.onRouterTransitionStart('/share/ask-genius/example', 'push');
    expect(sentry.init).not.toHaveBeenCalled();
    expect(sentry.replayIntegration).not.toHaveBeenCalled();
    expect(sentry.captureRouterTransitionStart).not.toHaveBeenCalled();
  });

  it('does not initialize server or edge telemetry in the preview', async () => {
    await import('../../sentry.server.config');
    await import('../../sentry.edge.config');
    expect(sentry.init).not.toHaveBeenCalled();
  });

  it('does not initialize client telemetry on a shared chat route', async () => {
    vi.stubEnv('NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW', 'false');
    window.history.replaceState({}, '', '/share/ask-genius/example');
    await import('../../instrumentation-client');
    await import('../../sentry.client.config');
    expect(sentry.init).not.toHaveBeenCalled();
  });

  it('preserves regular app telemetry but never traces a shared chat navigation', async () => {
    vi.stubEnv('NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW', 'false');
    const instrumentation = await import('../../instrumentation-client');
    expect(sentry.init).toHaveBeenCalledOnce();
    instrumentation.onRouterTransitionStart('/share/ask-genius/example', 'push');
    expect(sentry.captureRouterTransitionStart).not.toHaveBeenCalled();
    instrumentation.onRouterTransitionStart('/dashboard', 'push');
    expect(sentry.captureRouterTransitionStart).toHaveBeenCalledOnce();
  });
});
