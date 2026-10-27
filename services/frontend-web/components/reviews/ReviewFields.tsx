import { Star } from 'lucide-react';
import { Badge, type BadgeProps } from '@/components/ui/badge';
import { readSavedApartmentAnalysis } from '@/lib/apartment-analysis';

export function ReviewRating({ rating }: { rating?: number | null }) {
  if (rating == null) return <span className="text-muted-foreground">Rating unavailable</span>;
  return <span className="inline-flex items-center gap-1 whitespace-nowrap" aria-label={`${rating} out of 5 stars`}>
    <Star aria-hidden="true" className="h-4 w-4 fill-amber-400 text-amber-500" />{rating}/5
  </span>;
}

export function reviewSourceLabel(source: string | null) {
  // These values identify the import/run, not the original publishing platform.
  if (source === 'apartment_review_ai' || source === 'apartment_review_fallback') return 'Imported review';
  if (source === 'csv_import') return 'CSV import';
  if (source === 'manual') return 'Manual entry';
  return source || 'Source unavailable';
}

const variants: Record<string, BadgeProps['variant']> = {
  positive: 'success', negative: 'destructive', mixed: 'warning', neutral: 'secondary', unknown: 'outline',
};
export function ReviewSentiment({ sentiment }: { sentiment: string | null }) {
  if (!sentiment) return <span className="text-muted-foreground">Not analyzed</span>;
  return <Badge variant={variants[sentiment] || 'outline'}>{sentiment.charAt(0).toUpperCase() + sentiment.slice(1)}</Badge>;
}

export function ReviewAnalysisStatus({ analysis }: { analysis: unknown }) {
  const state = readSavedApartmentAnalysis(analysis);
  if (state.status === 'missing') return <span className="text-muted-foreground">No saved analysis</span>;
  if (state.status === 'unavailable') return <span className="text-muted-foreground">Analysis unavailable</span>;
  return <Badge variant={state.result.method === 'ai_model' ? 'info' : 'warning'}>
    {state.result.method === 'ai_model' ? 'AI analysis' : 'Keyword fallback'}
  </Badge>;
}
