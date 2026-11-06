import { surveyDate, type SurveyInstance } from '@/lib/api/surveys';

export function invitationStatus(invitation: SurveyInstance['invitation']) {
  switch (invitation?.status) {
    case 'suppressed_opt_out': return 'Invitation suppressed — opted out';
    case 'suppressed_disabled': return 'Invitation skipped — survey disabled';
    case 'suppressed_submitted': return 'Invitation skipped — already submitted';
    case 'scheduled': return invitation?.is_simulated ? 'Invitation simulation scheduled' : 'Invitation scheduled';
    case 'provider_accepted': return invitation?.is_simulated ? 'Simulated invitation — no email sent' : 'Email accepted for sending';
    case 'email_test_accepted': return 'Test email sent';
    case 'email_test_reserved': return 'Test email sending not confirmed';
    case 'email_test_failed': return 'Test email send failed';
    case 'provider_failed': return 'Email send failed';
    default: return invitation?.is_simulated ? 'Simulated invitation — no email sent' : 'Sending history unavailable';
  }
}

export function SurveyStatus({ survey }: { survey: SurveyInstance }) {
  return <div className="space-y-1"><span className="capitalize">{survey.status === 'pending' ? 'Awaiting response' : survey.status}</span><p className="text-xs text-muted-foreground">{invitationStatus(survey.invitation)}</p></div>;
}

export function ReviewedBy({ survey }: { survey: SurveyInstance }) {
  return <div className="space-y-1"><p className="font-medium">Reviewed{survey.reviewed_by && <> by {survey.reviewed_by}</>}</p>
    <time className="text-xs text-muted-foreground" dateTime={survey.reviewed_at || undefined}>{surveyDate(survey.reviewed_at)}</time></div>;
}
