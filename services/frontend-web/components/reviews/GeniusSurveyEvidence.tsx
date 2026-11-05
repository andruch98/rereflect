'use client';

import { useEffect, useState } from 'react';
import type { ChatMessage } from '@/components/copilot/ChatArea';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { surveysAPI, surveyAnswerLabel, surveyType, surveyTypeLabel } from '@/lib/api/surveys';

interface OriginalAnswer { id: string; text: string; answer_label: string | null }
export interface SurveySource {
  survey_id: string;
  topic?: string;
  question_id?: string;
  title?: string;
  type_label?: string;
  questions?: OriginalAnswer[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

/** Use validated server metadata, never a link or identifier generated in Markdown. */
export function readSurveySources(metadata: ChatMessage['structured_data']): SurveySource[] {
  if (!metadata || metadata.kind !== 'ask_genius' || !Array.isArray(metadata.sources)) return [];
  return metadata.sources.flatMap((value: unknown) => {
    if (!isRecord(value) || value.source !== 'survey' || typeof value.survey_id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value.survey_id)) return [];
    const snapshot = isRecord(value.survey) ? value.survey : undefined;
    const questions = snapshot && Array.isArray(snapshot.questions) ? snapshot.questions.flatMap((q: unknown) =>
      isRecord(q) && typeof q.id === 'string' && typeof q.text === 'string'
        ? [{ id: q.id, text: q.text, answer_label: typeof q.answer_label === 'string' ? q.answer_label : null }] : []) : undefined;
    const type = surveyType(typeof snapshot?.event_type === 'string' ? snapshot.event_type : undefined,
      typeof snapshot?.template_id === 'string' ? snapshot.template_id : undefined);
    return [{ survey_id: value.survey_id, topic: typeof value.topic === 'string' ? value.topic : undefined,
      question_id: typeof value.question_id === 'string' ? value.question_id : undefined,
      title: typeof snapshot?.title === 'string' ? snapshot.title : undefined,
      type_label: typeof snapshot?.survey_type_label === 'string' ? snapshot.survey_type_label : type?.label, questions }];
  });
}

function SurveyDetail({ sources, publicSnapshot = false }: { sources: SurveySource[]; publicSnapshot?: boolean }) {
  const source = sources[0];
  const [legacy, setLegacy] = useState<{ questions: OriginalAnswer[]; title: string; type_label: string }>();
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [allAnswers, setAllAnswers] = useState(false);
  useEffect(() => {
    if (source.questions || publicSnapshot) return;
    let active = true;
    surveysAPI.get(source.survey_id).then(row => {
      if (row.status !== 'submitted') throw new Error('Submission unavailable');
      if (active) setLegacy({ title: row.questionnaire.title, type_label: surveyTypeLabel(row),
        questions: row.questionnaire.questions.map(q => ({ id: q.id, text: q.rendered_text || q.text,
          answer_label: surveyAnswerLabel(q, row.answers[q.id], row.questionnaire) })) });
    }).catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [source.survey_id, source.questions, attempt, publicSnapshot]);
  const questions = source.questions ?? legacy?.questions;
  if (!questions) return <div className="py-4 text-sm" role="status">{publicSnapshot ? 'The original answers were not included in this shared chat.' : failed ? <>
    These survey answers could not be loaded. <button type="button" className="underline" onClick={() => { setFailed(false); setAttempt(value => value + 1); }}>Reload answers</button>
  </> : 'Loading survey answers…'}</div>;
  const selectedIds = new Set(sources.flatMap(item => item.question_id ? [item.question_id] : []));
  const relevant = questions.filter(q => selectedIds.has(q.id));
  const ordered = relevant.length && !allAnswers ? relevant : [...relevant, ...questions.filter(q => !selectedIds.has(q.id))];
  const typeLabel = source.type_label || legacy?.type_label;
  return <section aria-label="Original survey submission" className="space-y-5 border-b py-5 last:border-0">
    <header className="space-y-1">{typeLabel && <p className="text-sm text-muted-foreground">{typeLabel}</p>}<h3 className="text-lg font-semibold">{source.title || legacy?.title || 'Survey submission'}</h3></header>
    <dl className="space-y-5">{ordered.map(q => <div key={q.id}>
      <dt className="mb-2 font-semibold">{q.text}</dt>
      <dd className="whitespace-pre-wrap break-words text-base leading-7">{q.answer_label || 'No answer provided'}</dd>
    </div>)}</dl>
    {relevant.length > 0 && relevant.length < questions.length && <button type="button" className="text-sm text-primary underline underline-offset-4" aria-expanded={allAnswers} onClick={() => setAllAnswers(value => !value)}>
      {allAnswers ? 'Show relevant answers only' : 'View all answers from this survey'}
    </button>}
  </section>;
}

export function SurveyCollection({ sources, topic, publicSnapshot = false }: { sources: SurveySource[]; topic?: string; publicSnapshot?: boolean }) {
  const [pages, setPages] = useState(1);
  const grouped = new Map<string, SurveySource[]>();
  for (const source of sources) grouped.set(source.survey_id, [...(grouped.get(source.survey_id) ?? []), source]);
  const records = [...grouped.values()];
  const shown = Math.min(pages * 50, records.length);
  return <div aria-label={topic ? `Survey answers for ${topic}` : 'Supporting survey answers'} className="my-2 space-y-3 text-base font-normal">
    {Array.from({ length: pages }, (_, page) => {
      const start = page * 50;
      const batch = records.slice(start, start + 50);
      return <div key={page}>
        {records.length > 50 && <p className="text-sm text-muted-foreground">Showing {start + 1}–{start + batch.length} of {records.length} survey responses.</p>}
        <Dialog>
          <DialogTrigger asChild><button type="button" className="rounded-sm font-medium text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
            {records.length === 1 ? 'View original answers' : `View answers from ${batch.length} surveys`}
          </button></DialogTrigger>
          <DialogContent className="max-h-[85dvh] w-[calc(100%-2rem)] max-w-3xl overflow-y-auto rounded-xl sm:p-7">
            <DialogHeader><DialogTitle className="text-xl">{topic || 'Survey answers'}</DialogTitle><DialogDescription>Original questions and submitted answers.</DialogDescription></DialogHeader>
            {batch.map(items => <SurveyDetail key={items[0].survey_id} sources={items} publicSnapshot={publicSnapshot} />)}
          </DialogContent>
        </Dialog>
      </div>;
    })}
    {shown < records.length && <button type="button" className="rounded-md border px-3 py-2 text-sm" onClick={() => setPages(value => value + 1)}>{records.length - shown <= 50 ? `Show remaining ${records.length - shown}` : 'Show next 50 survey responses'}</button>}
  </div>;
}
