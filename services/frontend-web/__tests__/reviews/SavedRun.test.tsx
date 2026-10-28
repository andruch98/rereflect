// Opt-in private replay. Inputs remain outside Git, never reconstructed from AI output.
import { readFileSync } from 'node:fs';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { ApartmentAnalysis } from '@/components/reviews/ApartmentAnalysis';
import { ReviewRating } from '@/components/reviews/ReviewFields';
import { readSavedApartmentAnalysis } from '@/lib/apartment-analysis';
import type { FeedbackItem } from '@/lib/api/feedback';

const input = process.env.BOOMSAY_PRIVATE_REVIEW_REPLAY;
const records: FeedbackItem[] = input ? JSON.parse(readFileSync(input, 'utf8')) : [];
afterEach(cleanup);

describe.skipIf(!input)('private saved review replay (no AI or network)', () => {
  it('contains the six saved AI records', () => {
    expect(records).toHaveLength(6);
    expect(records.every(r => readSavedApartmentAnalysis(r.apartment_analysis).status === 'available')).toBe(true);
  });
  records.forEach((review, index) => it(`renders saved record ${index + 1} without losing quotation text`, () => {
    const before = JSON.stringify(review);
    const { container } = render(<><ReviewRating rating={review.star_rating} /><ApartmentAnalysis analysis={review.apartment_analysis} reviewText={review.text} /></>);
    const state = readSavedApartmentAnalysis(review.apartment_analysis);
    expect(state.status).toBe('available');
    if (state.status !== 'available') return;
    expect(screen.getByLabelText(`${review.star_rating} out of 5 stars`)).toBeInTheDocument();
    expect(container.querySelectorAll('h3')).toHaveLength(state.result.topics.length);
    const expected = state.result.topics.flatMap(t => t.quotations.map(q => typeof q === 'string' ? q : q.text)).sort();
    expect([...container.querySelectorAll('blockquote')].map(n => n.textContent).sort()).toEqual(expected);
    expect(JSON.stringify(review)).toBe(before);
  }));
});
