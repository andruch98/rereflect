'use client';

import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { feedbackAPI } from '@/lib/api/feedback';
import { ApartmentAnalysis } from './ApartmentAnalysis';
import { ReviewRating, ReviewSentiment, reviewSourceLabel } from './ReviewFields';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

export function ReviewDetail({ id }: { id: number }) {
  const { user } = useAuth();
  const validId = Number.isSafeInteger(id) && id > 0;
  const query = useQuery({
    queryKey: ['boomsay-review', user?.organization_id, user?.id, id],
    queryFn: () => feedbackAPI.get(id), enabled: !!user && validId,
  });
  const review = query.data;
  return <main className="mx-auto max-w-4xl space-y-6 px-4 py-8 sm:px-6">
    <Link href="/feedbacks" className="text-sm underline underline-offset-4">Back to reviews</Link>
    {!validId || query.isError ? <div role="alert"><p>This review could not be loaded or is not available to your account.</p>{validId && <Button variant="outline" onClick={() => query.refetch()}>Try again</Button>}</div>
      : !review ? <p role="status">Loading review…</p> : <>
        <Card><CardHeader><CardTitle><h1>Review #{review.id}</h1></CardTitle>
          <div className="flex flex-wrap items-center gap-3 text-sm"><ReviewRating rating={review.star_rating} /><ReviewSentiment sentiment={review.sentiment_label} /><span>{reviewSourceLabel(review.source)}</span></div>
        </CardHeader><CardContent>
          <p className="whitespace-pre-wrap break-words leading-relaxed">{review.text.trim() ? review.text : review.star_rating != null ? 'Rating only — no written review' : 'No written review'}</p>
        </CardContent></Card>
        <ApartmentAnalysis analysis={review.apartment_analysis} reviewText={review.text} />
      </>}
  </main>;
}
