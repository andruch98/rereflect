import { Badge, badgeVariants, type BadgeProps } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  groupSavedQuotations,
  readSavedApartmentAnalysis,
  type ApartmentSentiment,
  type QuotationGroupLabel,
} from '@/lib/apartment-analysis';

interface ApartmentAnalysisProps {
  analysis?: unknown;
  reviewText: string;
}

const SENTIMENT_LABELS: Record<ApartmentSentiment, string> = {
  positive: 'Positive',
  negative: 'Negative',
  mixed: 'Mixed',
  neutral: 'Neutral',
  unknown: 'Unknown',
};

const SENTIMENT_VARIANTS: Record<ApartmentSentiment, BadgeProps['variant']> = {
  positive: 'success',
  negative: 'destructive',
  mixed: 'warning',
  neutral: 'secondary',
  unknown: 'outline',
};

function SentimentBadge({ sentiment }: { sentiment: ApartmentSentiment }) {
  return <Badge variant={SENTIMENT_VARIANTS[sentiment]}>{SENTIMENT_LABELS[sentiment]}</Badge>;
}

function groupLabel(label: QuotationGroupLabel, fallback: boolean): string {
  if (label === 'unlabeled') return fallback ? 'Matched words and phrases' : 'Unlabeled quotations';
  return SENTIMENT_LABELS[label];
}

/** Presentation only: uses final_result, with no model/API calls or data writes. */
export function ApartmentAnalysis({ analysis, reviewText }: ApartmentAnalysisProps) {
  const state = readSavedApartmentAnalysis(analysis);

  if (state.status !== 'available') {
    return (
      <Card>
        <CardHeader>
          <CardTitle><h2>Saved analysis</h2></CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            {state.status === 'missing'
              ? 'No saved analysis is available for this review.'
              : 'The saved analysis is unavailable for display.'}
          </p>
        </CardContent>
      </Card>
    );
  }

  const { result } = state;
  const fallback = result.method === 'keyword_fallback';
  const ratingOnly = reviewText.trim().length === 0;

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle><h2>Saved analysis</h2></CardTitle>
          <Badge variant={fallback ? 'warning' : 'info'}>
            {fallback ? 'Keyword fallback' : 'AI analysis'}
          </Badge>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm" aria-label="Overall sentiment">
          <span className="text-muted-foreground">Overall sentiment</span>
          <SentimentBadge sentiment={result.sentiment} />
        </div>
        {fallback && (
          <p className="text-sm text-muted-foreground">
            This saved result uses keyword matching. Topic sentiment was not determined.
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {result.topics.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {ratingOnly
              ? 'No written review was provided. No topics or quotations were saved. A rating alone does not establish whether there were issues.'
              : fallback
                ? 'No keyword matches were saved. This does not mean the review has no concerns.'
                : 'No topics were returned in this saved analysis.'}
          </p>
        ) : (
          result.topics.map((topic, index) => {
            const groups = groupSavedQuotations(topic.quotations);
            return (
              <section key={`${index}-${topic.name}`} aria-label={topic.name} className="rounded-lg border border-border p-4">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                  <h3 className="font-medium">{topic.name}</h3>
                  <SentimentBadge sentiment={topic.sentiment} />
                </div>
                <div className="space-y-4">
                  {groups.length === 0 && (
                    <p className="text-sm text-muted-foreground">No quotations were saved for this topic.</p>
                  )}
                  {groups.map(({ label, texts }) => (
                    <section key={label} aria-label={groupLabel(label, fallback)} className="space-y-2">
                      <h4 className={label === 'unlabeled'
                        ? 'text-sm font-medium'
                        : badgeVariants({ variant: SENTIMENT_VARIANTS[label] })}>
                        {groupLabel(label, fallback)}
                      </h4>
                      {texts.map((text, quoteIndex) => (
                        <blockquote key={quoteIndex} className="whitespace-pre-wrap break-words border-l-2 border-border pl-3 text-sm leading-relaxed text-muted-foreground">
                          {text}
                        </blockquote>
                      ))}
                    </section>
                  ))}
                </div>
              </section>
            );
          })
        )}
      </CardContent>
    </Card>
  );
}
