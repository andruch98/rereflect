/**
 * Sentry client-side configuration.
 * Runs in the browser. Initializes only when NEXT_PUBLIC_SENTRY_DSN is set, so a
 * self-hosted install sends nothing anywhere unless the operator opts in.
 *
 * Reference: https://docs.sentry.io/platforms/javascript/guides/nextjs/
 */
import * as Sentry from "@sentry/nextjs";

const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;

// Public chat links are capabilities; never record preview sessions or their URLs.
const telemetryAllowed = process.env.NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW !== 'true' &&
  !(typeof window !== 'undefined' && ['/share/ask-genius/', '/survey/'].some(prefix => window.location.pathname.startsWith(prefix)));

if (dsn && telemetryAllowed) {
  Sentry.init({
    dsn,
    environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? "development",
    tracesSampleRate: parseFloat(
      process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? "0.1",
    ),

    // Replay captures user sessions for reproductions — 10 % normal / 100 % on error.
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    integrations: [Sentry.replayIntegration()],

    // Do not send PII (emails, usernames) to Sentry.
    sendDefaultPii: false,
  });
}

export const onRouterTransitionStart: typeof Sentry.captureRouterTransitionStart = (...args) => {
  if (!telemetryAllowed || ['/share/ask-genius/', '/survey/'].some(prefix => String(args[0]).includes(prefix))) return;
  return Sentry.captureRouterTransitionStart(...args);
};
