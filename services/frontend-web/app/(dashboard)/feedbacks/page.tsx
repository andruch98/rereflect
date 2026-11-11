'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import LegacyFeedbackPage from './LegacyFeedbackPage';
import { ReviewsInbox } from '@/components/reviews/ReviewsInbox';
import { REVIEW_PREVIEW_ENABLED } from '@/lib/review-preview';
import { readReplyFilter } from '@/lib/review-response-status';

function PreviewInbox() {
  const filter = readReplyFilter(useSearchParams().get('response_status'));
  return <ReviewsInbox responseFilter={filter} />;
}

export default function FeedbackPage() {
  if (!REVIEW_PREVIEW_ENABLED) return <LegacyFeedbackPage />;
  return <Suspense fallback={<p role="status">Loading reviews…</p>}><PreviewInbox /></Suspense>;
}
