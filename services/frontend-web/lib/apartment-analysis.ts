/**
 * Display types for the payload saved by _analyze_apartment_item in the worker.
 * This reader never uses ai_attempt, reinterprets a sentiment, or repairs data.
 */
export type ApartmentSentiment = 'positive' | 'negative' | 'mixed' | 'neutral' | 'unknown';
export type QuotationSentiment = Exclude<ApartmentSentiment, 'mixed'>;

export type ApartmentQuotation = string | {
  text: string;
  sentiment: QuotationSentiment;
};

export interface ApartmentTopic {
  name: string;
  sentiment: ApartmentSentiment;
  quotations: ApartmentQuotation[];
}

export interface SavedApartmentResult {
  method: 'ai_model' | 'keyword_fallback';
  sentiment: ApartmentSentiment;
  topics: ApartmentTopic[];
}

export type SavedApartmentAnalysisState =
  | { status: 'missing' }
  | { status: 'unavailable' }
  | { status: 'available'; result: SavedApartmentResult };

const SENTIMENTS: readonly string[] = ['positive', 'negative', 'mixed', 'neutral', 'unknown'];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isSentiment(value: unknown): value is ApartmentSentiment {
  return typeof value === 'string' && SENTIMENTS.includes(value);
}

function isQuotation(value: unknown): value is ApartmentQuotation {
  // Older saved AI results and mechanical keyword matches contain plain strings.
  return typeof value === 'string' || (
    isRecord(value) &&
    typeof value.text === 'string' &&
    isSentiment(value.sentiment) &&
    value.sentiment !== 'mixed'
  );
}

function isTopic(value: unknown): value is ApartmentTopic {
  return isRecord(value) &&
    typeof value.name === 'string' &&
    isSentiment(value.sentiment) &&
    Array.isArray(value.quotations) &&
    value.quotations.every(isQuotation);
}

/** Check only the saved display shape; never substitute a raw/parsed candidate. */
export function readSavedApartmentAnalysis(value: unknown): SavedApartmentAnalysisState {
  if (value === null || value === undefined) return { status: 'missing' };
  if (!isRecord(value) || !isRecord(value.final_result)) return { status: 'unavailable' };

  const result = value.final_result;
  if (
    (result.method !== 'ai_model' && result.method !== 'keyword_fallback') ||
    !isSentiment(result.sentiment) ||
    !Array.isArray(result.topics) ||
    !result.topics.every(isTopic)
  ) {
    return { status: 'unavailable' };
  }

  return {
    status: 'available',
    result: {
      method: result.method,
      sentiment: result.sentiment,
      topics: result.topics,
    },
  };
}

export type QuotationGroupLabel = QuotationSentiment | 'unlabeled';

/** Group by the quotation's own saved label, never by its topic's sentiment. */
export function groupSavedQuotations(quotations: ApartmentQuotation[]) {
  const order: QuotationGroupLabel[] = ['positive', 'negative', 'neutral', 'unknown', 'unlabeled'];
  return order.flatMap((label) => {
    const texts = quotations.flatMap((quotation) => {
      if (typeof quotation === 'string') return label === 'unlabeled' ? [quotation] : [];
      return quotation.sentiment === label ? [quotation.text] : [];
    });
    return texts.length ? [{ label, texts }] : [];
  });
}
