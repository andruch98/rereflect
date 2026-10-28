import LegacyFeedbackPage from './LegacyFeedbackPage';
import { ReviewsInbox } from '@/components/reviews/ReviewsInbox';
import { REVIEW_PREVIEW_ENABLED } from '@/lib/review-preview';

export default function FeedbackPage() {
  return REVIEW_PREVIEW_ENABLED ? <ReviewsInbox /> : <LegacyFeedbackPage />;
}
