import { REVIEW_PREVIEW_ENABLED } from '@/lib/review-preview';
import { ReviewPreviewLogin } from '@/components/reviews/ReviewPreviewLogin';
import LegacyLoginPage from './LegacyLoginPage';

export default function LoginPage() {
  return REVIEW_PREVIEW_ENABLED ? <ReviewPreviewLogin /> : <LegacyLoginPage />;
}
