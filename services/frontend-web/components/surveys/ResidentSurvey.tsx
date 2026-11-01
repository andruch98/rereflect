'use client';

import { useEffect, useRef, useState } from 'react';
import { isAxiosError } from 'axios';
import { surveysAPI, type SurveyAnswers, type SurveyInstance, type SurveyQuestion } from '@/lib/api/surveys';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { BoomSayLogo } from '@/components/reviews/BoomSayLogo';

function saveError(error: unknown): string {
  const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
  return typeof detail === 'string' && detail.length <= 500 ? detail : 'Your answers could not be saved. Please try again.';
}

export function ResidentSurvey({ token }: { token: string }) {
  const [survey, setSurvey] = useState<SurveyInstance>();
  const [loadError, setLoadError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    surveysAPI.resident(token).then(value => { if (active) setSurvey(value); }).catch(() => { if (active) setLoadError(true); });
    return () => { active = false; };
  }, [token, attempt]);
  return <main className="mx-auto min-h-dvh max-w-2xl px-4 py-8 sm:px-6 sm:py-12">
    <div className="mb-8"><BoomSayLogo /></div>
    {loadError ? <div role="alert" className="space-y-3 rounded-xl border p-6"><p>This survey could not be loaded. Check that you opened the complete private link.</p><Button variant="outline" onClick={() => { setLoadError(false); setAttempt(value => value + 1); }}>Try again</Button></div>
      : !survey ? <p role="status">Loading your survey…</p>
        : <ResidentSurveyForm key={survey.public_id} token={token} initial={survey} />}
  </main>;
}

function ResidentSurveyForm({ token, initial }: { token: string; initial: SurveyInstance }) {
  const [survey, setSurvey] = useState(initial);
  const [answers, setAnswers] = useState<SurveyAnswers>(initial.draft_answers || {});
  const [saving, setSaving] = useState<'saved' | 'unsaved' | 'saving' | 'error'>('saved');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const latestAnswers = useRef(answers);
  const revision = useRef(0);
  const queue = useRef(Promise.resolve());
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const mounted = useRef(true);
  const completed = useRef(initial.status === 'submitted' && !!initial.submitted_at);
  const submitLock = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; clearTimeout(timer.current); };
  }, []);

  function enqueueDraft(value: SurveyAnswers, version: number) {
    queue.current = queue.current.then(async () => {
      if (completed.current) return;
      if (mounted.current) setSaving('saving');
      try {
        const saved = await surveysAPI.saveDraft(token, value);
        if (!mounted.current) return;
        if (saved.status === 'submitted' && saved.submitted_at) {
          completed.current = true;
          setSurvey(saved);
        }
        if (version === revision.current) { setSaving('saved'); setError(''); }
      } catch (caught) {
        if (mounted.current) { setSaving('error'); setError(saveError(caught)); }
      }
    });
    return queue.current;
  }

  function change(question: SurveyQuestion, value: string | number) {
    if (completed.current || submitLock.current) return;
    const updated = { ...latestAnswers.current, [question.id]: value };
    latestAnswers.current = updated;
    setAnswers(updated);
    revision.current += 1;
    const version = revision.current;
    setSaving('unsaved');
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { void enqueueDraft(updated, version); }, question.type === 'text' ? 500 : 100);
  }

  async function submit() {
    if (submitLock.current || completed.current) return;
    submitLock.current = true;
    setSubmitting(true);
    setError('');
    clearTimeout(timer.current);
    try {
      await queue.current;
      const result = await surveysAPI.submit(token, latestAnswers.current);
      if (result.status !== 'submitted' || !result.submitted_at) throw new Error('Submission was not confirmed');
      completed.current = true;
      if (mounted.current) setSurvey(result);
    } catch (caught) {
      if (mounted.current) { setError(saveError(caught)); setSaving('error'); }
    } finally {
      submitLock.current = false;
      if (mounted.current) setSubmitting(false);
    }
  }

  if (survey.status === 'submitted' && survey.submitted_at) return <section className="space-y-4 rounded-xl border bg-card p-6 sm:p-8" aria-label="Survey confirmation"><h1 className="text-2xl font-semibold">Thank you for your feedback</h1><p>Your maintenance survey has been submitted.</p></section>;

  return <section className="space-y-6">
    <header className="space-y-3"><h1 className="text-2xl font-semibold sm:text-3xl">{survey.questionnaire.title}</h1><p className="text-muted-foreground">{survey.context.community_name}</p><p className="rounded-lg bg-muted p-4 text-sm leading-6">Maintenance request: {survey.context.request_description}<br />Ticket: {survey.context.ticket_id}</p></header>
    <form className="space-y-8" onSubmit={event => { event.preventDefault(); void submit(); }}>
      {survey.questionnaire.questions.map(question => <fieldset key={question.id} disabled={submitting} className="space-y-3">
        <legend className="mb-3 text-base font-medium leading-7">{question.rendered_text || question.text}{!question.required && <span className="ml-1 font-normal text-muted-foreground">(optional)</span>}</legend>
        {question.type === 'text' ? <Textarea aria-label={question.rendered_text || question.text} rows={5} maxLength={question.max_length} value={String(answers[question.id] ?? '')} onChange={event => change(question, event.target.value)} className="text-base" />
          : <div className="grid gap-2">{(question.type === 'rating' ? [...Object.entries(survey.questionnaire.rating_labels).map(([value, label]) => ({ value: Number(value), label: `${value} — ${label}` })), ...(question.special_options ?? [])] : question.options ?? []).map(option => <label key={option.value} className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-lg border px-4 py-3 text-sm ${answers[question.id] === option.value ? 'border-primary bg-primary/5' : 'hover:bg-muted'}`}>
            <input type="radio" name={question.id} value={option.value} checked={answers[question.id] === option.value} required={question.required} onChange={() => change(question, option.value)} className="h-4 w-4 accent-primary" /><span>{option.label}</span>
          </label>)}</div>}
        {question.type === 'text' && question.max_length && <p className="text-right text-xs text-muted-foreground">{String(answers[question.id] ?? '').length}/{question.max_length}</p>}
      </fieldset>)}
      <div className="space-y-4 border-t pt-6">
        {error && <p role="alert" className="text-sm text-destructive">{error} Your survey has not been confirmed as submitted.</p>}
        <p role="status" className="text-sm text-muted-foreground">{submitting ? 'Submitting…' : saving === 'saving' ? 'Saving draft…' : saving === 'saved' ? 'Draft saved. You can return using this private link.' : saving === 'unsaved' ? 'Changes waiting to save…' : 'Draft save could not be confirmed.'}</p>
        <div className="flex flex-wrap gap-3"><Button type="submit" disabled={submitting}>{submitting ? 'Submitting…' : 'Submit survey'}</Button><Button type="button" variant="outline" disabled={submitting || saving === 'saving'} onClick={() => { clearTimeout(timer.current); void enqueueDraft(latestAnswers.current, revision.current); }}>Save draft</Button></div>
      </div>
    </form>
  </section>;
}
