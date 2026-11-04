'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { surveysAPI, surveyAnswerLabel, surveyDate, type SurveyInstance } from '@/lib/api/surveys';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

function SurveyStatus({ survey }: { survey: SurveyInstance }) {
  return <div className="space-y-1"><span className="capitalize">{survey.status === 'pending' ? 'Awaiting response' : survey.status}</span><p className="text-xs text-muted-foreground">{survey.invitation?.status === 'suppressed_opt_out' ? 'Invitation suppressed — opted out' : survey.invitation?.is_simulated ? 'Simulated invitation — no email sent' : 'No invitation recorded'}</p></div>;
}

export function SurveyDashboard() {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const result = useQuery({ queryKey: ['surveys', user?.organization_id, user?.id, page], queryFn: () => surveysAPI.list(page), enabled: !!user, retry: false });
  return <main className="mx-auto w-full max-w-7xl space-y-6 p-4 sm:p-6">
    <header className="space-y-2"><h1 className="text-3xl font-semibold">Surveys</h1><p className="text-muted-foreground">Maintenance survey invitations and resident responses.</p></header>
    {result.isError ? <div role="alert" className="space-y-3 rounded-xl border p-6"><p>Surveys could not be loaded for your community.</p><Button variant="outline" onClick={() => result.refetch()}>Try again</Button></div>
      : result.isPending ? <div role="status" aria-label="Loading surveys" className="space-y-3"><Skeleton className="h-12 w-full" /><Skeleton className="h-32 w-full" /></div>
        : !result.data.surveys.length ? <p className="rounded-xl border p-6 text-muted-foreground">No maintenance surveys yet.</p>
          : <>
            <div className="overflow-x-auto rounded-xl border"><table className="w-full min-w-[48rem] text-left text-sm"><caption className="sr-only">Maintenance surveys for your community</caption><thead className="border-b bg-muted/50"><tr>{['Resident', 'Unit', 'Maintenance ticket', 'Status', 'Submitted', 'Answers'].map(label => <th key={label} scope="col" className="px-4 py-3 font-medium">{label}</th>)}</tr></thead><tbody className="divide-y">{result.data.surveys.map(survey => <tr key={survey.public_id}><td className="px-4 py-4">{survey.context.resident_name || '—'}</td><td className="px-4 py-4">{survey.context.unit_number || '—'}</td><td className="px-4 py-4">{survey.context.ticket_id}</td><td className="px-4 py-4"><SurveyStatus survey={survey} /></td><td className="px-4 py-4">{surveyDate(survey.submitted_at)}</td><td className="px-4 py-4"><Link href={`/surveys/${encodeURIComponent(survey.public_id)}`} className="whitespace-nowrap text-primary underline underline-offset-4">View answers<span className="sr-only"> for ticket {survey.context.ticket_id}</span></Link></td></tr>)}</tbody></table></div>
            <div className="flex flex-wrap items-center justify-between gap-3 text-sm"><p>{result.data.total} survey{result.data.total === 1 ? '' : 's'}</p><div className="flex items-center gap-3"><Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>Previous</Button><span>Page {page}</span><Button variant="outline" size="sm" disabled={page * 50 >= result.data.total} onClick={() => setPage(value => value + 1)}>Next</Button></div></div>
          </>}
  </main>;
}

export function SurveyDetail({ id }: { id: string }) {
  const { user } = useAuth();
  const result = useQuery({ queryKey: ['survey', user?.organization_id, user?.id, id], queryFn: () => surveysAPI.get(id), enabled: !!user, retry: false });
  const survey = result.data;
  return <main className="mx-auto w-full max-w-4xl space-y-6 p-4 sm:p-6">
    <Link href="/surveys" className="text-sm text-primary underline underline-offset-4">Back to Surveys</Link>
    {result.isError ? <div role="alert" className="space-y-3 rounded-xl border p-6"><p>This survey could not be loaded or is unavailable to your account.</p><Button variant="outline" onClick={() => result.refetch()}>Try again</Button></div>
      : !survey ? <div role="status" aria-label="Loading survey" className="space-y-3"><Skeleton className="h-10 w-2/3" /><Skeleton className="h-48 w-full" /></div>
        : <>
          <header className="space-y-3"><h1 className="text-2xl font-semibold">{survey.questionnaire.title}</h1><SurveyStatus survey={survey} /></header>
          <section aria-label="Maintenance context" className="rounded-xl border bg-card p-5"><dl className="grid gap-4 text-sm sm:grid-cols-2">{[
            ['Resident', survey.context.resident_name], ['Unit', survey.context.unit_number], ['Maintenance ticket', survey.context.ticket_id], ['Request', survey.context.request_description], ['Ticket marked completed', surveyDate(survey.context.ticket_completed_at)], ['Survey submitted', surveyDate(survey.submitted_at)],
            ...(survey.context.employee_name ? [['Employee / vendor', survey.context.employee_name]] : []),
          ].map(([label, value]) => <div key={label}><dt className="text-muted-foreground">{label}</dt><dd className="mt-1 whitespace-pre-wrap break-words font-medium">{value || '—'}</dd></div>)}</dl></section>
          <section aria-label="Original questions and answers" className="space-y-6 rounded-xl border bg-card p-5 sm:p-6"><h2 className="text-xl font-semibold">Original questions and answers</h2>{survey.status !== 'submitted' && <p className="text-sm text-muted-foreground">This survey has not been submitted. Any saved draft below is incomplete resident feedback.</p>}{survey.questionnaire.questions.map(question => <div key={question.id} className="space-y-2 border-b pb-5 last:border-0 last:pb-0"><h3 className="font-medium leading-7">{question.rendered_text || question.text}{!question.required && <span className="ml-1 text-sm font-normal text-muted-foreground">(optional)</span>}</h3><p className="whitespace-pre-wrap break-words leading-7">{surveyAnswerLabel(question, (survey.status === 'submitted' ? survey.answers : survey.draft_answers)[question.id], survey.questionnaire)}</p></div>)}<p className="text-xs text-muted-foreground">Template {survey.questionnaire.id}, version {survey.questionnaire.version}. Rating scale: {Object.entries(survey.questionnaire.rating_labels).map(([value, label]) => `${value} ${label}`).join(' · ')}</p></section>
          {survey.invitation && <section aria-label="Simulated invitation" className="space-y-3 rounded-xl border bg-card p-5"><h2 className="text-xl font-semibold">{survey.invitation.is_simulated ? 'Simulated invitation' : 'Invitation'}</h2><p className="text-sm text-muted-foreground">{survey.invitation.status === 'suppressed_opt_out' ? 'The invitation was suppressed because this recipient opted out.' : 'No email was sent. This preview uses the actual private resident survey link.'}</p><dl className="space-y-3 text-sm"><div><dt className="text-muted-foreground">Recipient</dt><dd className="break-words">{survey.invitation.recipient}</dd></div><div><dt className="text-muted-foreground">Subject</dt><dd>{survey.invitation.subject}</dd></div></dl><pre className="whitespace-pre-wrap break-words rounded-lg bg-muted p-4 font-sans text-sm leading-6">{survey.invitation.text}</pre><a href={survey.invitation.survey_url} target="_blank" rel="noreferrer" className="inline-block text-sm text-primary underline underline-offset-4">Open resident survey</a></section>}
        </>}
  </main>;
}
