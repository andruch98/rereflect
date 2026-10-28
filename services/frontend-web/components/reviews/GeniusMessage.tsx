'use client';

import { Children, isValidElement, type ReactNode, useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Check, ChevronDown, Copy } from 'lucide-react';
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
  topic?: string;
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
    return [{ review_id: value.review_id, topic: typeof value.topic === 'string' ? value.topic : undefined, excerpt: typeof value.excerpt === 'string' ? value.excerpt : undefined, excerpt_truncated: value.excerpt_truncated === true, review }];
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

function ReviewDetail({ source, publicSnapshot }: { source: Source; publicSnapshot: boolean }) {
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

  return <section className="space-y-3 border-b py-5 last:border-0" aria-label="Original review">

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
  </section>;
}

function uniqueReviews(sources: Source[]): Source[] {
  return [...new Map(sources.map(source => [source.review_id, source])).values()];
}

/** A page is a frozen subset of validated metadata, never a new model request. */
function ReviewCollection({ sources, publicSnapshot, topic }: { sources: Source[]; publicSnapshot: boolean; topic?: string }) {
  const [pages, setPages] = useState(1);
  const records = uniqueReviews(sources);
  const shown = Math.min(pages * 50, records.length);
  const remaining = records.length - shown;
  return <div aria-label={topic ? `Reviews for ${topic}` : 'Supporting reviews'} className="my-2 space-y-3 text-base font-normal">
    {Array.from({ length: pages }, (_, page) => {
      const start = page * 50;
      const batch = records.slice(start, start + 50);
      const label = records.length === 1 ? 'View review' : topic ? `View ${batch.length} reviews` : records.length <= 50 ? `View all ${batch.length} reviews` : `View ${batch.length} reviews`;
      return <div key={page} role={page ? 'article' : undefined} aria-label={page ? 'Additional reviews' : undefined} className={page ? 'border-t pt-3' : ''}>
        {records.length > 50 && <p className="mb-1 text-sm text-muted-foreground">{page === 0 ? `Found ${records.length} reviews. ` : ''}Showing {start + 1}–{start + batch.length} of {records.length} reviews.</p>}
        <Dialog>
          <DialogTrigger asChild><button type="button" className="rounded-sm font-medium text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">{label}</button></DialogTrigger>
          <DialogContent className="max-h-[85dvh] w-[calc(100%-2rem)] max-w-3xl overflow-y-auto rounded-xl sm:p-7">
            <DialogHeader><DialogTitle className="text-xl">{topic || (batch.length === 1 ? 'Review' : 'Reviews')}</DialogTitle><DialogDescription>{records.length > 50 ? `Reviews ${start + 1}–${start + batch.length} of ${records.length}. ` : ''}Original review content and expandable saved analysis.</DialogDescription></DialogHeader>
            {batch.map(source => <ReviewDetail key={source.review_id} source={source} publicSnapshot={publicSnapshot} />)}
          </DialogContent>
        </Dialog>
      </div>;
    })}
    {remaining > 0 && <button type="button" className="rounded-md border px-3 py-2 text-sm hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring" onClick={() => setPages(value => value + 1)}>{remaining <= 50 ? `Show remaining ${remaining}` : 'Show next 50 reviews'}</button>}
  </div>;
}

function textOf(children: ReactNode): string {
  return Children.toArray(children).map(child => typeof child === 'string' || typeof child === 'number' ? String(child) : isValidElement<{ children?: ReactNode }>(child) ? textOf(child.props.children) : '').join('');
}

/** Ask Genius does not inherit the general copilot's actions, HTML or navigation. */
export function GeniusMessage({ message, publicSnapshot = false }: { message: ChatMessage; publicSnapshot?: boolean }) {
  const [copiedContent, setCopiedContent] = useState<string>();
  const [copyError, setCopyError] = useState(false);
  const sources = useMemo(() => readSources(message.structured_data), [message.structured_data]);
  const assistant = message.role === 'assistant';
  const topicGroups = new Map<string, Source[]>();
  const ungrouped: Source[] = [];
  for (const source of sources) {
    if (source.topic) topicGroups.set(source.topic, [...(topicGroups.get(source.topic) ?? []), source]);
    else ungrouped.push(source);
  }
  const matchedTopics = new Set<string>();
  // Match exact topic labels at the start of Markdown list items; source text cannot
  // create links. Unmatched legacy metadata remains accessible under a labeled group.
  const topicFor = (text: string) => [...topicGroups.keys()].find(topic => text.trim().startsWith(`${topic}:`) || text.trim() === topic);
  const bulletLines = message.content.split('\n').filter(line => /^\s*(?:[-*+] |\d+\. )/.test(line));
  for (const line of bulletLines) {
    const topic = topicFor(line.replace(/^\s*(?:[-*+] |\d+\. )/, '').replace(/\*\*/g, '').trim());
    if (topic) matchedTopics.add(topic);
  }
  const content = assistant
    ? message.content.replace(/\[Review\s*#?\d+\]\(\/feedbacks\/\d+\)/gi, 'supporting review below')
    : message.content;
  const markdownComponents = useMemo(() => {
    const groups = new Map<string, Source[]>();
    for (const source of sources) if (source.topic) groups.set(source.topic, [...(groups.get(source.topic) ?? []), source]);
    return { a: ({ children }: { children?: ReactNode }) => <span>{children}</span>, img: () => null,
      li: ({ children }: { children?: ReactNode }) => {
        const text = textOf(children).trim();
        const topic = [...groups.keys()].find(name => text.startsWith(`${name}:`) || text === name);
        return <li>{children}{topic && <ReviewCollection sources={groups.get(topic)!} topic={topic} publicSnapshot={publicSnapshot} />}</li>;
      } };
  }, [sources, publicSnapshot]);
  const copied = copiedContent === content;
  useEffect(() => {
    if (copiedContent === undefined) return;
    const timer = setTimeout(() => setCopiedContent(undefined), 2000);
    return () => clearTimeout(timer);
  }, [copiedContent]);

  async function copyAnswer() {
    setCopyError(false);
    try {
      await navigator.clipboard.writeText(content);
      setCopiedContent(content);
    } catch {
      setCopyError(true);
    }
  }

  if (!assistant) return <div className="mb-7 flex justify-end"><div className="max-w-[90%] whitespace-pre-wrap break-words rounded-2xl rounded-tr-sm bg-muted px-5 py-3 text-base leading-7 text-foreground sm:text-[17px]">{content}</div></div>;

  return <article aria-label="Ask Genius answer" className="mb-8 space-y-4 text-foreground">
    <div className="break-words text-base leading-7 sm:text-[17px] [&_p]:mb-4 [&_p:last-child]:mb-0 [&_ul]:my-4 [&_ul]:list-disc [&_ul]:space-y-2 [&_ul]:pl-6 [&_ol]:my-4 [&_ol]:list-decimal [&_ol]:space-y-2 [&_ol]:pl-6 [&_li_p]:mb-1 [&_blockquote]:my-4 [&_blockquote]:border-l-2 [&_blockquote]:pl-4 [&_pre]:whitespace-pre-wrap [&_h1]:mb-3 [&_h1]:font-semibold [&_h2]:mb-3 [&_h2]:font-semibold [&_h3]:mb-3 [&_h3]:font-semibold">
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={markdownComponents} urlTransform={() => ''}>{content}</ReactMarkdown>
    </div>
    {[...topicGroups].filter(([topic]) => !matchedTopics.has(topic)).map(([topic, records]) => <section key={topic}><p className="font-semibold">{topic}</p><ReviewCollection sources={records} topic={topic} publicSnapshot={publicSnapshot} /></section>)}
    {!!ungrouped.length && <ReviewCollection sources={ungrouped} publicSnapshot={publicSnapshot} />}
    <div className="flex flex-wrap items-center gap-3">
      <Button type="button" variant="ghost" size="sm" className="h-8 gap-2 px-2 text-muted-foreground" onClick={() => { void copyAnswer(); }}>{copied ? <Check aria-hidden="true" className="h-4 w-4" /> : <Copy aria-hidden="true" className="h-4 w-4" />}{copied ? 'Copied' : 'Copy'}</Button>
      {copyError && <p role="status" className="text-xs text-muted-foreground">Could not copy. Select the answer text to copy it.</p>}
    </div>
  </article>;
}
