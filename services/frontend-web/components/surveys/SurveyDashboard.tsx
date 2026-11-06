'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { surveysAPI, surveyAnswerLabel, surveyDate, surveyType, surveyTypeLabel } from '@/lib/api/surveys';
import { defaultSurveyFilters, surveyHref, type SurveyFilters } from '@/lib/survey-list-filters';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { invitationStatus, ReviewedBy, SurveyStatus } from './SurveyStatus';

export { SurveyDashboard } from './SurveyList';

export function SurveyDetail({ id, listFilters = defaultSurveyFilters }: { id: string; listFilters?: SurveyFilters }) {
  const { user } = useAuth();
  const detailKey = ['survey', user?.organization_id, user?.id, id];
  const result = useQuery({ queryKey: detailKey, queryFn: () => surveysAPI.get(id), enabled: !!user, retry: false });
  const survey = result.data;
  const cache = useQueryClient();
  const review = useMutation({
    mutationFn: async () => {
      const saved = await surveysAPI.markReviewed(id);
      if (!saved.reviewed_at || saved.public_id !== id) throw new Error('Review was not confirmed');
      return saved;
    },
    onSuccess: saved => {
      cache.setQueryData(detailKey, saved);
      void cache.invalidateQueries({ queryKey: ['surveys', user?.organization_id, user?.id] });
    },
  });
  // Next can navigate to a question before its API response has rendered the target.
  const loadedId = survey?.public_id;
  useEffect(() => {
    if (loadedId && window.location.hash) {
      const target = document.getElementById(window.location.hash.slice(1));
      target?.scrollIntoView?.({ block: 'start' });
      target?.focus({ preventScroll: true });
    }
  }, [loadedId]);
  const type = survey && surveyType(survey.context.event_type, survey.questionnaire.id);
  const isMaintenance = type?.eventType === 'maintenance_completed';
  return <main className="mx-auto w-full max-w-4xl space-y-6 p-4 sm:p-6">
    <Link href={surveyHref(listFilters)} className="text-sm text-primary underline underline-offset-4">Back to Surveys</Link>
    {result.isError ? <div role="alert" className="space-y-3 rounded-xl border p-6"><p>This survey could not be loaded or is unavailable to your account.</p><Button variant="outline" onClick={() => result.refetch()}>Try again</Button></div>
      : !survey ? <div role="status" aria-label="Loading survey" className="space-y-3"><Skeleton className="h-10 w-2/3" /><Skeleton className="h-48 w-full" /></div>
        : <>
          <header className="space-y-3"><h1 className="text-2xl font-semibold">{survey.questionnaire.title}</h1><SurveyStatus survey={survey} /></header>
          <section aria-label={isMaintenance ? 'Maintenance context' : 'Survey context'} className="rounded-xl border bg-card p-5"><dl className="grid gap-4 text-sm sm:grid-cols-2">{[
            ['Survey type', surveyTypeLabel(survey)], ['Resident', survey.context.resident_name], ['Unit', survey.context.unit_number],
            ...(isMaintenance ? [['Maintenance ticket', survey.context.ticket_id], ['Request', survey.context.request_description], ['Ticket marked completed', surveyDate(survey.context.ticket_completed_at || survey.context.event_occurred_at)]] : [[type?.dateLabel || 'Survey event', surveyDate(survey.context.event_occurred_at)]]),
            ['Survey submitted', surveyDate(survey.submitted_at)],
            ...(isMaintenance && survey.context.employee_name ? [['Employee / vendor', survey.context.employee_name]] : []),
          ].map(([label, value]) => <div key={label}><dt className="text-muted-foreground">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words font-medium">{value || '—'}</dd></div>)}</dl></section>
          <section id="original-answers" tabIndex={-1} aria-label="Original questions and answers" className="space-y-6 rounded-xl border bg-card p-5 sm:p-6">
            <h2 className="text-xl font-semibold">Original questions and answers</h2>
            {survey.status !== 'submitted' && <p className="text-sm text-muted-foreground">This survey has not been submitted. Any saved draft below is incomplete resident feedback.</p>}
            {survey.questionnaire.questions.map(question => {
              const flagged = survey.attention_reasons?.some(reason => reason.question_id === question.id);
              return <div key={question.id} id={'answer-' + question.id} tabIndex={-1} className="scroll-mt-4 space-y-2 border-b pb-5 last:border-0 last:pb-0 target:rounded-md target:bg-muted/50 target:p-3">
                {flagged && <span className="text-xs font-semibold text-amber-900 dark:text-amber-300">Flagged answer</span>}
                <h3 className="font-medium leading-7">{question.rendered_text || question.text}{!question.required && <> <span className="ml-1 text-sm font-normal text-muted-foreground">(optional)</span></>}</h3>
                <p className="whitespace-pre-wrap break-words leading-7">{surveyAnswerLabel(question, (survey.status === 'submitted' ? survey.answers : survey.draft_answers)[question.id], survey.questionnaire)}</p>
              </div>;
            })}
            <p className="text-xs text-muted-foreground">Template {survey.questionnaire.id}, version {survey.questionnaire.version}. Rating scale: {Object.entries(survey.questionnaire.rating_labels).map(([value, label]) => `${value} ${label}`).join(' · ')}</p>
          </section>
          {survey.status === 'submitted' && <section aria-label="Manager review" className="space-y-3 rounded-xl border bg-card p-5">
            <h2 className="text-xl font-semibold">Manager review</h2>
            {survey.reviewed_at ? <div role="status"><ReviewedBy survey={survey} /></div> :
              <>
                <p className="text-sm text-muted-foreground">{survey.attention_reasons?.length ? 'The flagged answers above need a manager’s review.' : 'This response has no flagged answers.'} Marking it reviewed records who read it. Resident answers stay as submitted.</p>
                {survey.can_mark_reviewed !== false && (user?.role === 'owner' || user?.role === 'admin') ?
                  <Button disabled={review.isPending} onClick={() => review.mutate()}>{review.isPending ? 'Saving…' : 'Mark reviewed'}</Button> :
                  <p className="text-sm">A community administrator or owner can mark this response reviewed.</p>}
                {review.isError && <p role="alert" className="text-sm text-destructive">The review could not be confirmed. Try marking it reviewed again.</p>}
              </>}
          </section>}
          {survey.invitation && <section aria-label={survey.invitation.is_simulated ? 'Simulated invitation' : 'Invitation'} className="space-y-3 rounded-xl border bg-card p-5"><h2 className="text-xl font-semibold">{survey.invitation.is_simulated ? 'Simulated invitation' : 'Invitation'}</h2><p className="text-sm text-muted-foreground">{invitationStatus(survey.invitation)}</p><dl className="space-y-3 text-sm">
            {[
              ['Scheduled for', survey.invitation.scheduled_for],
              ['Email accepted', survey.invitation.sent_at],
              ['Reminder simulated', survey.invitation.reminder_simulated_at],
              ['Reminder simulation scheduled for', survey.invitation.reminder_simulated_at ? null : survey.invitation.reminder_due_at],
            ].map(([label, date]) => date && <div key={label}><dt className="text-muted-foreground">{label}</dt><dd>{surveyDate(date)}</dd></div>)}
            <div><dt className="text-muted-foreground">Recipient</dt><dd className="break-words">{survey.invitation.recipient}</dd></div><div><dt className="text-muted-foreground">Subject</dt><dd>{survey.invitation.subject}</dd></div></dl><pre className="whitespace-pre-wrap break-words rounded-lg bg-muted p-4 font-sans text-sm leading-6">{survey.invitation.text}</pre><a href={survey.invitation.survey_url} target="_blank" rel="noreferrer" className="inline-block text-sm text-primary underline underline-offset-4">Open resident survey</a></section>}
        </>}
  </main>;
}
