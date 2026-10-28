'use client';

import { useParams } from 'next/navigation';
import LegacyFeedbackPage from './LegacyFeedbackPage';
import { ReviewDetail } from '@/components/reviews/ReviewDetail';
import { REVIEW_PREVIEW_ENABLED } from '@/lib/review-preview';

export default function FeedbackDetailPage() {
  const { id } = useParams<{ id: string }>();
  return REVIEW_PREVIEW_ENABLED ? <ReviewDetail id={Number(id)} /> : <LegacyFeedbackPage />;
}
