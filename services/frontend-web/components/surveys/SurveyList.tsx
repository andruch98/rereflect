'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { SURVEY_TYPES, surveysAPI, surveyDate, surveyType, surveyTypeLabel, type SurveyCounts, type SurveyEventType, type SurveyInstance, type SurveyView } from '@/lib/api/surveys';
import { defaultSurveyFilters, surveyHref, surveyViews, type SurveyFilters } from '@/lib/survey-list-filters';
import { SurveyStatus, ReviewedBy } from './SurveyStatus';

const metricViews = ['sent', 'submitted', 'needs_review'] as const;
const controlStyle = 'h-10 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function SurveyTotals({ counts, selected, onSelect }: {
  counts?: SurveyCounts; selected: SurveyView; onSelect: (view: SurveyView) => void;
}) {
  return <div role="group" aria-label="Survey totals for the selected dates and type" className="grid grid-cols-3 gap-2 sm:gap-4">
    {metricViews.map(view => <button key={view} type="button" aria-label={surveyViews[view] + ' ' + (counts?.[view] ?? 'unavailable')} aria-pressed={view === selected} onClick={() => onSelect(view === selected ? 'all' : view)}
      className="flex min-w-0 flex-col items-start justify-between gap-1 rounded-xl border bg-card p-3 text-left hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring aria-pressed:border-primary aria-pressed:bg-muted sm:p-4">
      <span className="text-sm font-medium">{surveyViews[view]}</span>
      <span className="text-2xl font-semibold tabular-nums">{counts?.[view] ?? '—'}</span>
    </button>)}
  </div>;
}

function EmptyList({ filters }: { filters: SurveyFilters }) {
  const messages = {
    sent: 'No confirmed invitations in this view.',
    submitted: 'No responses received in this view.',
    needs_review: 'No responses are waiting for review in this view.',
    reviewed: 'No responses have been marked reviewed in this view.',
    all: filters.startDate || filters.endDate ? 'No survey activity in this date range.' :
      filters.eventType ? 'No surveys of this type yet.' : 'No surveys yet.',
  };
  return <p className="rounded-xl border p-6 text-muted-foreground">{messages[filters.view]}</p>;
}

function SurveyRows({ surveys, filters }: { surveys: SurveyInstance[]; filters: SurveyFilters }) {
  return <div className="overflow-hidden rounded-xl border bg-card">
    <table className="block w-full text-left text-sm md:table"><caption className="sr-only">Surveys for your community</caption>
      <thead className="sr-only border-b bg-muted/50 md:not-sr-only md:table-header-group">
        <tr>{['Resident', 'Survey type', 'Status', 'Manager review', 'Answers'].map(label =>
          <th key={label} scope="col" className="px-4 py-3 font-medium">{label}</th>)}</tr>
      </thead>
      <tbody className="block divide-y md:table-row-group">{surveys.map(survey => {
        const detail = surveyHref(filters, survey.public_id);
        const typeLabel = surveyTypeLabel(survey);
        const ticket = surveyType(survey.context.event_type, survey.questionnaire.id)?.eventType === 'maintenance_completed' && survey.context.ticket_id;
        const reasons = survey.attention_reasons || [];
        return <tr key={survey.public_id} className="grid grid-cols-2 gap-x-3 gap-y-3 p-4 md:table-row">
          <td className="min-w-0 break-words align-top md:px-4 md:py-4">
            <span className="font-medium">{survey.context.resident_name || 'Unknown resident'}</span>
            {survey.context.unit_number && <p className="mt-1 text-xs text-muted-foreground">Unit {survey.context.unit_number}</p>}
          </td>
          <td className="min-w-0 break-words align-top md:px-4 md:py-4"><span>{typeLabel}</span>{ticket && <p className="mt-1 text-xs text-muted-foreground">Ticket {ticket}</p>}</td>
          <td className="min-w-0 align-top md:px-4 md:py-4">
            <SurveyStatus survey={survey} />
            {filters.view === 'sent' ? <p className="mt-1 text-xs text-muted-foreground">{survey.invitation?.sent_at ? 'Sent ' + surveyDate(survey.invitation.sent_at) : 'Send date unavailable'}</p> :
              survey.submitted_at && <p className="mt-1 text-xs text-muted-foreground"><time dateTime={survey.submitted_at}>{surveyDate(survey.submitted_at)}</time></p>}
          </td>
          <td className="min-w-0 break-words align-top md:px-4 md:py-4">
            {survey.reviewed_at ? <ReviewedBy survey={survey} /> :
              reasons.length ? <p className="text-sm font-semibold">Needs review</p> : <span className="text-muted-foreground">{survey.status === 'submitted' ? 'No flags' : '—'}</span>}
            {!!reasons.length && <div className="mt-2 space-y-3">
              {reasons.map(reason => <Link key={reason.question_id} href={detail + '#answer-' + encodeURIComponent(reason.question_id)} className="block text-sm underline decoration-muted-foreground underline-offset-4 hover:text-primary">
                {reason.label} <span className="font-medium">{reason.answer}</span>
              </Link>)}
            </div>}
          </td>
          <td className="col-span-2 align-top md:px-4 md:py-4"><Link href={detail} className="whitespace-nowrap text-primary underline underline-offset-4">
            View answers{' '}<span className="sr-only">for {typeLabel} — {survey.context.resident_name || survey.context.unit_number || 'resident'}{ticket ? ' — ticket ' + ticket : ''}</span>
          </Link></td>
        </tr>;
      })}</tbody>
    </table>
  </div>;
}

export function SurveyDashboard({ initialFilters = defaultSurveyFilters }: { initialFilters?: SurveyFilters }) {
  const { user } = useAuth();
  const [filters, setFilters] = useState(initialFilters);
  const { page, eventType, view, startDate, endDate } = filters;
  const invalidDates = !!(startDate && endDate && startDate > endDate);
  const result = useQuery({
    queryKey: ['surveys', user?.organization_id, user?.id, filters],
    queryFn: () => surveysAPI.list(page, 50, eventType || undefined, {
      ...(startDate && { start_date: startDate }), ...(endDate && { end_date: endDate }), ...(view !== 'all' && { view }),
    }),
    enabled: !!user && !invalidDates, retry: false,
  });
  function change(patch: Partial<SurveyFilters>) {
    const next = { ...filters, page: 1, ...patch };
    setFilters(next);
    window.history.replaceState(window.history.state, '', surveyHref(next));
  }

  return <main className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6">
    <header className="space-y-2"><h1 className="text-3xl font-semibold">Surveys</h1><p className="text-muted-foreground">Survey invitations and resident responses.</p></header>
    <div className="grid grid-cols-2 items-end gap-3 sm:flex sm:flex-wrap">
      <label htmlFor="survey-type" className="col-span-2 space-y-1 text-sm font-medium sm:min-w-52">
        <span className="block">Survey type</span>
        <select id="survey-type" className={controlStyle} value={eventType} onChange={e => change({ eventType: e.target.value as SurveyEventType | '' })}>
          <option value="">All surveys</option>{SURVEY_TYPES.map(type => <option key={type.eventType} value={type.eventType}>{type.label}</option>)}
        </select>
      </label>
      <label className="min-w-0 space-y-1 text-sm font-medium"><span className="block">From</span>
        <input type="date" value={startDate} max={endDate || undefined} aria-invalid={invalidDates} onChange={e => change({ startDate: e.target.value })} className={controlStyle} /></label>
      <label className="min-w-0 space-y-1 text-sm font-medium"><span className="block">Through</span>
        <input type="date" value={endDate} min={startDate || undefined} aria-invalid={invalidDates} onChange={e => change({ endDate: e.target.value })} className={controlStyle} /></label>
      {(eventType || startDate || endDate || view !== 'all') && <Button variant="ghost" onClick={() => change(defaultSurveyFilters)}>Clear filters</Button>}
    </div>
    {(startDate || endDate) && !invalidDates && <p className="text-xs text-muted-foreground">Date filters use Eastern time. Invitations use the send date and responses use the submission date.</p>}
    {invalidDates && <p role="alert" className="text-sm text-destructive">Choose an end date on or after the start date.</p>}
    <SurveyTotals counts={!invalidDates ? result.data?.counts : undefined} selected={view} onSelect={newView => change({ view: newView })} />
    <section aria-label="Survey activity" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Survey activity</h2>
        <label className="flex items-center gap-2 text-sm">Show
          <select className={controlStyle} value={view} onChange={e => change({ view: e.target.value as SurveyView })}>
            {Object.entries(surveyViews).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
      </div>
      {view === 'sent' && <p className="text-sm text-muted-foreground">Counts email accepted for sending to residents. Test emails and simulations are excluded.</p>}
      {view === 'needs_review' && !!result.data?.surveys.length && !invalidDates && <p className="text-sm text-muted-foreground">Open a flagged answer to review the resident’s feedback.</p>}
      {invalidDates ? null : result.isError ? <div role="alert" className="space-y-3 rounded-xl border p-6"><p>Surveys could not be loaded for your community.</p><Button variant="outline" onClick={() => result.refetch()}>Try again</Button></div>
        : result.isPending ? <div role="status" aria-label="Loading surveys" className="space-y-3"><Skeleton className="h-12 w-full" /><Skeleton className="h-32 w-full" /></div>
        : <>
          {result.data.surveys.length ? <SurveyRows surveys={result.data.surveys} filters={filters} /> :
            page > 1 ? <div className="rounded-xl border p-6"><p>This page has no more surveys.</p><Button variant="link" onClick={() => change({ page: 1 })}>Return to first page</Button></div> : <EmptyList filters={filters} />}
          {(result.data.total > 0 || page > 1) && <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <p>{result.data.total} survey{result.data.total === 1 ? '' : 's'}</p>
            <div className="flex items-center gap-3">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => change({ page: page - 1 })}>Previous</Button>
              <span>Page {page}</span><Button variant="outline" size="sm" disabled={page * 50 >= result.data.total} onClick={() => change({ page: page + 1 })}>Next</Button>
            </div>
          </div>}
        </>}
    </section>
  </main>;
}
