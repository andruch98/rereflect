'use client';

import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, ChevronDown, ChevronRight, Copy } from 'lucide-react';
import type { ChatMessage } from '@/components/copilot/ChatArea';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { feedbackAPI } from '@/lib/api/feedback';
import { readSavedApartmentAnalysis } from '@/lib/apartment-analysis';
import { ApartmentAnalysis } from './ApartmentAnalysis';
import { ReviewAnalysisStatus, ReviewRating, ReviewSentiment } from './ReviewFields';

interface ReviewSnapshot {
  original_review: string;
  star_rating?: number | null;
  saved_analysis?: unknown;
}

interface Source {
  review_id: number;
  excerpt?: string;
  excerpt_truncated?: boolean;
  review?: ReviewSnapshot;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

/** Only server-provided source metadata can open a review. Markdown cannot. */
function readSources(metadata: ChatMessage['structured_data']): Source[] {
  if (!metadata || metadata.kind !== 'ask_genius' || !Array.isArray(metadata.sources)) return [];
  return metadata.sources.flatMap((value: unknown) => {
    if (!isRecord(value) || typeof value.review_id !== 'number' || !Number.isSafeInteger(value.review_id) || value.review_id <= 0) return [];
    const review = isRecord(value.review) && typeof value.review.original_review === 'string'
      ? { original_review: value.review.original_review,
        star_rating: typeof value.review.star_rating === 'number' ? value.review.star_rating : null,
        saved_analysis: value.review.saved_analysis } : undefined;
    return [{ review_id: value.review_id, excerpt: typeof value.excerpt === 'string' ? value.excerpt : undefined, excerpt_truncated: value.excerpt_truncated === true, review }];
  });
}

function savedAnalysisForDisplay(snapshot: unknown): unknown {
  if (!isRecord(snapshot) || snapshot.status === 'missing') return undefined;
  if (snapshot.status !== 'available') return {};
  // The server labels older string quotations as "unlabeled". Preserve that
  // meaning using the existing display reader's supported string form.
  const topics = Array.isArray(snapshot.topics) ? snapshot.topics.map(topic => {
    if (!isRecord(topic) || !Array.isArray(topic.quotations)) return topic;
    return { ...topic, quotations: topic.quotations.map(quote => isRecord(quote) && quote.sentiment === 'unlabeled' && typeof quote.text === 'string' ? quote.text : quote) };
  }) : snapshot.topics;
  return { final_result: { method: snapshot.method, sentiment: snapshot.sentiment, topics } };
}

function excerptOf(text: string): string {
  const trimmed = text.trim();
  return trimmed.length > 240 ? `${trimmed.slice(0, 237).trimEnd()}…` : trimmed;
}

function ReviewSource({ source, publicSnapshot }: { source: Source; publicSnapshot: boolean }) {
  const [legacy, setLegacy] = useState<{ review: ReviewSnapshot; analysis: unknown }>();
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [analysisOpen, setAnalysisOpen] = useState(false);

  useEffect(() => {
    // A public snapshot must never resolve an ID through the private review API.
    if (publicSnapshot || source.review) return;
    let active = true;
    feedbackAPI.get(source.review_id).then(review => {
      if (active) setLegacy({ review: { original_review: review.text, star_rating: review.star_rating }, analysis: review.apartment_analysis });
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [source.review_id, source.review, publicSnapshot, attempt]);

  const review = source.review ?? legacy?.review;
  const analysis = source.review ? savedAnalysisForDisplay(source.review.saved_analysis) : legacy?.analysis;
  const analysisState = readSavedApartmentAnalysis(analysis);
  const excerpt = source.excerpt?.trim()
    ? `${source.excerpt.trim()}${source.excerpt_truncated ? '…' : ''}`
    : review ? excerptOf(review.original_review) : '';
  if (!review) {
    return <div className="rounded-xl border bg-card px-4 py-3 text-sm text-muted-foreground">
      {excerpt && <p className="mb-2 whitespace-pre-wrap text-foreground">“{excerpt}”</p>}
      {publicSnapshot ? 'The full review was not included in this shared chat.' : failed
        ? <>This review could not be loaded. <button type="button" className="underline underline-offset-2" onClick={() => { setFailed(false); setAttempt(value => value + 1); }}>Reload review</button></>
        : <span role="status">Loading review…</span>}
    </div>;
  }

  return <Dialog onOpenChange={() => setAnalysisOpen(false)}>
    <DialogTrigger asChild>
      <button type="button" className="group flex w-full items-center gap-4 rounded-xl border bg-card px-4 py-3 text-left text-foreground transition-colors hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <span className="min-w-0 flex-1 space-y-2">
          <span className="block whitespace-pre-wrap break-words text-base leading-relaxed">{excerpt ? `“${excerpt}”` : 'Rating only — no written review'}</span>
          <span className="block text-xs font-semibold text-foreground">Open review + analysis</span>
        </span>
        <ChevronRight aria-hidden="true" className="h-5 w-5 shrink-0 text-muted-foreground" />
      </button>
    </DialogTrigger>
    <DialogContent className="max-h-[85dvh] w-[calc(100%-2rem)] max-w-3xl overflow-y-auto rounded-xl sm:p-7">
      <DialogHeader>
        <DialogTitle className="text-xl">Review</DialogTitle>
        <DialogDescription className="sr-only">Original review and its saved analysis.</DialogDescription>
      </DialogHeader>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <ReviewRating rating={review.star_rating} />
        {analysisState.status === 'available' && <ReviewSentiment sentiment={analysisState.result.sentiment} />}
      </div>
      <p className="whitespace-pre-wrap break-words py-3 text-base leading-7 sm:text-[17px]">{review.original_review.trim() || 'Rating only — no written review'}</p>
      <div className="border-t pt-4">
        <button type="button" aria-expanded={analysisOpen} className="flex w-full items-center justify-between gap-3 rounded-md py-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" onClick={() => setAnalysisOpen(value => !value)}>
          <span className="text-base font-semibold">Saved analysis</span>
          <span className="flex items-center gap-2"><ReviewAnalysisStatus analysis={analysis} /><ChevronDown aria-hidden="true" className={`h-4 w-4 transition-transform ${analysisOpen ? 'rotate-180' : ''}`} /></span>
        </button>
        {analysisOpen && <div className="mt-3"><ApartmentAnalysis analysis={analysis} reviewText={review.original_review} /></div>}
      </div>
    </DialogContent>
  </Dialog>;
}

/** Ask Genius does not inherit the general copilot's actions, HTML or navigation. */
export function GeniusMessage({ message, publicSnapshot = false }: { message: ChatMessage; publicSnapshot?: boolean }) {
  const [copiedContent, setCopiedContent] = useState<string>();
  const [copyError, setCopyError] = useState(false);
  const sources = readSources(message.structured_data);
  const assistant = message.role === 'assistant';
  const content = assistant
    ? message.content.replace(/\[Review\s*#?\d+\]\(\/feedbacks\/\d+\)/gi, 'supporting review below')
    : message.content;
  const copied = copiedContent === content;
  useEffect(() => {
    if (copiedContent === undefined) return;
    const timer = setTimeout(() => setCopiedContent(undefined), 2000);
    return () => clearTimeout(timer);
  }, [copiedContent]);

  async function copyAnswer() {
    setCopyError(false);
    try {
      const excerpts = sources.flatMap(source => source.excerpt ? [`“${source.excerpt}${source.excerpt_truncated ? '…' : ''}”`] : []);
      await navigator.clipboard.writeText([content, ...excerpts].join('\n\n'));
      setCopiedContent(content);
    } catch {
      setCopyError(true);
    }
  }

  if (!assistant) return <div className="mb-7 flex justify-end"><div className="max-w-[90%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-sm bg-muted px-5 py-3 text-base leading-7 text-foreground sm:text-[17px]">{content}</div></div>;

  return <article aria-label="Ask Genius answer" className="mb-8 space-y-4 text-foreground">
    <div className="break-words text-base leading-7 sm:text-[17px] [&_p]:mb-4 [&_p:last-child]:mb-0 [&_ul]:my-4 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-6 [&_ol]:my-4 [&_ol]:list-decimal [&_ol]:space-y-2 [&_ol]:pl-6 [&_li_p]:mb-1 [&_blockquote]:my-4 [&_blockquote]:border-l-2 [&_blockquote]:pl-4 [&_pre]:whitespace-pre-wrap [&_h1]:mb-3 [&_h1]:font-semibold [&_h2]:mb-3 [&_h2]:font-semibold [&_h3]:mb-3 [&_h3]:font-semibold">
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={{ a: ({ children }) => <span>{children}</span>, img: () => null }} urlTransform={() => ''}>{content}</ReactMarkdown>
    </div>
    {!!sources.length && <div aria-label="Supporting reviews" className="space-y-3">{sources.map((source, index) => <ReviewSource key={`${source.review_id}-${index}`} source={source} publicSnapshot={publicSnapshot} />)}</div>}
    <div className="flex flex-wrap items-center gap-3">
      <Button type="button" variant="ghost" size="sm" className="h-8 gap-2 px-2 text-muted-foreground" onClick={() => { void copyAnswer(); }}>{copied ? <Check aria-hidden="true" className="h-4 w-4" /> : <Copy aria-hidden="true" className="h-4 w-4" />}{copied ? 'Copied' : 'Copy'}</Button>
      {copyError && <p role="status" className="text-xs text-muted-foreground">Could not copy. Select the answer text to copy it.</p>}
    </div>
  </article>;
}
