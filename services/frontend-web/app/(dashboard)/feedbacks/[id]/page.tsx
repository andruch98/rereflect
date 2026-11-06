'use client';

import { Suspense } from 'react';
import { useParams, useSearchParams } from 'next/navigation';
import LegacyFeedbackPage from './LegacyFeedbackPage';
import { ReviewDetail } from '@/components/reviews/ReviewDetail';
import { REVIEW_PREVIEW_ENABLED } from '@/lib/review-preview';
import { readReplyFilter } from '@/lib/review-response-status';

function PreviewDetail() {
  const { id } = useParams<{ id: string }>();
  const filter = readReplyFilter(useSearchParams().get('response_status'));
  return <ReviewDetail id={Number(id)} responseFilter={filter} />;
}

export default function FeedbackDetailPage() {
  if (!REVIEW_PREVIEW_ENABLED) return <LegacyFeedbackPage />;
  return <Suspense fallback={<p role="status">Loading review…</p>}><PreviewDetail /></Suspense>;
}
