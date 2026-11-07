import { withSentryConfig } from "@sentry/nextjs";
import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  // Serialize prerender workers so a small VPS does not launch eight Node heaps.
  // This affects build parallelism, not the application's request handling.
  experimental: { cpus: 1 },
  // Enable standalone output for Docker deployments
  output: "standalone",
  // Required for monorepo: tells Next.js to trace dependencies from the workspace root
  outputFileTracingRoot: path.join(import.meta.dirname, "../../"),
};

// Local BoomSay previews do not upload build artifacts or initialize Sentry.
// Runtime configs use the same preview flag; production instrumentation is unchanged.
export default process.env.NEXT_PUBLIC_BOOMSAY_REVIEW_PREVIEW === 'true' ? nextConfig : withSentryConfig(nextConfig, {
  // For all available options, see:
  // https://www.npmjs.com/package/@sentry/webpack-plugin#options

  org: "rereflect",

  project: "frontend-web",

  // Only print logs for uploading source maps in CI
  silent: !process.env.CI,

  // For all available options, see:
  // https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/

  // Upload a larger set of source maps for prettier stack traces (increases build time)
  widenClientFileUpload: true,

  // Route browser requests to Sentry through a Next.js rewrite to circumvent ad-blockers.
  // This can increase your server load as well as your hosting bill.
  // Note: Check that the configured route will not match with your Next.js middleware, otherwise reporting of client-
  // side errors will fail.
  tunnelRoute: "/monitoring",

  webpack: {
    // Enables automatic instrumentation of Vercel Cron Monitors. (Does not yet work with App Router route handlers.)
    // See the following for more information:
    // https://docs.sentry.io/product/crons/
    // https://vercel.com/docs/cron-jobs
    automaticVercelMonitors: true,

    // Tree-shaking options for reducing bundle size
    treeshake: {
      // Automatically tree-shake Sentry logger statements to reduce bundle size
      removeDebugLogging: true,
    },
  },
});
