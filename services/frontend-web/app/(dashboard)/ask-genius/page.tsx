import { notFound } from 'next/navigation';
import { AskGenius } from '@/components/reviews/AskGenius';
import { REVIEW_PREVIEW_ENABLED } from '@/lib/review-preview';

export default function AskGeniusPage() {
  if (!REVIEW_PREVIEW_ENABLED) notFound();
  return <AskGenius />;
}
