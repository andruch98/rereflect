import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import { ApartmentAnalysis } from '@/components/reviews/ApartmentAnalysis';

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('saved apartment analysis presentation', () => {
  it('shows a mixed topic once and keeps positive and negative evidence under their own labels', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    render(<ApartmentAnalysis reviewText="The team was helpful. The team later ignored my calls." analysis={{
      ai_attempt: { raw_output: 'Rejected private candidate', parsed_result: { sentiment: 'positive' } },
      final_result: {
        method: 'ai_model', sentiment: 'negative', topics: [{
          name: 'Staff & customer service', sentiment: 'mixed', quotations: [
            { text: 'The team later ignored my calls.', sentiment: 'negative' },
            { text: 'The team was helpful.', sentiment: 'positive' },
          ],
        }],
      },
    }} />);

    const topic = screen.getByRole('region', { name: 'Staff & customer service' });
    expect(screen.getAllByRole('heading', { name: 'Staff & customer service' })).toHaveLength(1);
    expect(within(topic).getByText('Mixed')).toBeInTheDocument();
    expect(within(within(topic).getByRole('region', { name: 'Positive' })).getByText('The team was helpful.')).toBeInTheDocument();
    expect(within(within(topic).getByRole('region', { name: 'Negative' })).getByText('The team later ignored my calls.')).toBeInTheDocument();
    expect(screen.getByLabelText('Overall sentiment')).toHaveTextContent('Negative');
    expect(screen.getByText('AI analysis')).toBeInTheDocument();
    expect(screen.queryByText('Rejected private candidate')).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('shows saved keyword results without substituting the rejected AI output or inventing topic sentiment', () => {
    render(<ApartmentAnalysis reviewText="The pool needs repairs." analysis={{
      ai_attempt: { raw_output: 'AI claimed an excellent pool', parsed_candidate: { sentiment: 'positive' } },
      final_result: {
        method: 'keyword_fallback', sentiment: 'neutral',
        evidence_kind: 'mechanical_keyword_spans',
        topics: [{ name: 'Amenities', sentiment: 'unknown', quotations: ['pool'], matches: [{ text: 'pool' }] }],
      },
    }} />);

    const topic = screen.getByRole('region', { name: 'Amenities' });
    expect(screen.getByText('Keyword fallback')).toBeInTheDocument();
    expect(screen.queryByText('AI analysis')).not.toBeInTheDocument();
    expect(within(topic).getByText('Unknown')).toBeInTheDocument();
    expect(within(topic).getByRole('heading', { name: 'Matched words and phrases' })).toBeInTheDocument();
    expect(within(topic).getByText('pool')).toBeInTheDocument();
    expect(screen.queryByText('AI claimed an excellent pool')).not.toBeInTheDocument();
  });

  it('keeps older string quotations unlabeled instead of borrowing the topic sentiment', () => {
    render(<ApartmentAnalysis reviewText="The pool is clean." analysis={{
      final_result: { method: 'ai_model', sentiment: 'positive', topics: [
        { name: 'Amenities', sentiment: 'positive', quotations: ['The pool is clean.'] },
      ] },
    }} />);

    const topic = screen.getByRole('region', { name: 'Amenities' });
    expect(within(topic).getByRole('region', { name: 'Unlabeled quotations' })).toHaveTextContent('The pool is clean.');
    expect(within(topic).queryByRole('region', { name: 'Positive' })).not.toBeInTheDocument();
  });

  it('presents a rating-only result without implying no issues occurred', () => {
    render(<ApartmentAnalysis reviewText="" analysis={{
      final_result: { method: 'ai_model', sentiment: 'positive', topics: [] },
    }} />);

    expect(screen.getByLabelText('Overall sentiment')).toHaveTextContent('Positive');
    expect(screen.getByText(/No written review was provided/)).toHaveTextContent('A rating alone does not establish whether there were issues.');
    expect(screen.queryAllByRole('heading', { level: 3 })).toHaveLength(0);
  });

  it('distinguishes no saved analysis from an unavailable saved payload and never exposes a candidate', () => {
    const { rerender } = render(<ApartmentAnalysis reviewText="A review" analysis={null} />);
    expect(screen.getByText('No saved analysis is available for this review.')).toBeInTheDocument();

    rerender(<ApartmentAnalysis reviewText="A review" analysis={{
      ai_attempt: { parsed_result: { sentiment: 'positive', topics: [] }, raw_output: 'Do not display this candidate' },
    }} />);
    expect(screen.getByText('The saved analysis is unavailable for display.')).toBeInTheDocument();
    expect(screen.queryByText('Positive')).not.toBeInTheDocument();
    expect(screen.queryByText('Do not display this candidate')).not.toBeInTheDocument();
  });

  it('does not guess a result when its saved method or quotation shape is unavailable', () => {
    const { rerender } = render(<ApartmentAnalysis reviewText="A review" analysis={{
      final_result: { sentiment: 'negative', topics: [] },
    }} />);
    expect(screen.getByText('The saved analysis is unavailable for display.')).toBeInTheDocument();

    rerender(<ApartmentAnalysis reviewText="A review" analysis={{
      final_result: { method: 'ai_model', sentiment: 'negative', topics: [
        { name: 'Amenities', sentiment: 'negative', quotations: [{ text: 'A review' }] },
      ] },
    }} />);
    expect(screen.getByText('The saved analysis is unavailable for display.')).toBeInTheDocument();
    expect(screen.queryByText('Negative')).not.toBeInTheDocument();
  });

  it('renders the exact saved quotation as plain text, preserving whitespace and escaping markup', () => {
    const quote = 'The pool  was clean.\n<img src=x onerror=alert(1)>';
    const { container } = render(<ApartmentAnalysis reviewText={quote} analysis={{
      final_result: { method: 'ai_model', sentiment: 'neutral', topics: [
        { name: 'Amenities', sentiment: 'neutral', quotations: [{ text: quote, sentiment: 'unknown' }] },
      ] },
    }} />);

    expect(container.querySelector('blockquote')?.textContent).toBe(quote);
    expect(container.querySelector('img')).toBeNull();
    expect(within(screen.getByRole('region', { name: 'Amenities' })).getByRole('region', { name: 'Unknown' })).toBeInTheDocument();
  });
});
