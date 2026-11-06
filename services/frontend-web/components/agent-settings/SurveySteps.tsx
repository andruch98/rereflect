import { SURVEY_TYPES } from '@/lib/api/surveys';
import type { SurveySettings } from '@/lib/api/agent-settings';
import { SummaryRows, type SettingStep } from './SettingsFlow';

const delays = [0, 24, 48, 72];
const selectStyle = 'rounded-md border border-input bg-background p-2 text-sm disabled:opacity-50';
const delayLabel = (hours: number) => hours === 0 ? 'At the event' : `${hours} hours later`;

function Schedule({ values, update }: { values: SurveySettings; update?: (values: SurveySettings) => void }) {
  return <ul className="divide-y">
    {SURVEY_TYPES.map(({ eventType, label, dateLabel }) => {
      const timing = values.schedule[eventType];
      const setTiming = (change: Partial<typeof timing>) => update?.({ ...values,
        schedule: { ...values.schedule, [eventType]: { ...timing, ...change } } });
      return <li key={eventType} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 py-3 first:pt-0 last:pb-0">
        <div><p className="text-sm font-medium">{label}</p><p className="text-sm text-muted-foreground">{dateLabel}</p></div>
        {update ? <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="inline-flex items-center gap-1.5"><input type="checkbox" checked={timing.enabled}
            aria-label={`Enable ${label} survey`} onChange={e => setTiming({ enabled: e.target.checked })} />{timing.enabled ? 'On' : 'Off'}</label>
          <select aria-label={`Invitation timing for ${label}`} className={selectStyle} disabled={!timing.enabled}
            value={timing.delay_hours} onChange={e => setTiming({ delay_hours: Number(e.target.value) })}>
            {delays.map(hours => <option key={hours} value={hours}>{delayLabel(hours)}</option>)}
          </select>
        </div> : <p className="text-sm">{timing.enabled ? delayLabel(timing.delay_hours) : 'Off'}</p>}
      </li>;
    })}
  </ul>;
}

export const surveySteps: SettingStep<SurveySettings>[] = [
  {
    title: 'Survey schedule',
    help: 'Choose which surveys to offer and when each invitation is due after its event.',
    summary: values => <Schedule values={values} />,
    edit: (values, update) => <Schedule values={values} update={update} />,
  },
  {
    title: 'Email reminder',
    help: 'Choose whether to schedule one reminder for residents who have not submitted their survey.',
    summary: v => <SummaryRows rows={[['Reminder', v.reminder_hours ? `Once, ${v.reminder_hours} hours after the invitation` : 'Off']]} />,
    edit: (v, update) => <label className="block space-y-1 text-sm"><span>When to remind</span>
      <select className={`block ${selectStyle}`} value={v.reminder_hours ?? ''} onChange={e => update({ ...v,
        reminder_hours: e.target.value ? Number(e.target.value) : null })}>
        <option value="">Off</option>
        {[24, 48, 72].map(hours => <option value={hours} key={hours}>{hours} hours after the invitation</option>)}
      </select></label>,
  },
  {
    title: 'Responses needing review',
    help: 'Choose which responses to highlight on the Surveys dashboard. Resident requests for follow-up are always included.',
    summary: v => <SummaryRows rows={[
      ['Follow-up requests', 'Always included'], ['Ratings of 1 or 2', v.flag_low_ratings ? 'Included' : 'Off'],
      ['Open move-in or maintenance issues', v.flag_unresolved ? 'Included' : 'Off'],
    ]} />,
    edit: (v, update) => <div className="space-y-3 text-sm">
      <p>Follow-up requests are always included, even if the resident gave a high rating.</p>
      <label className="flex items-center gap-2"><input type="checkbox" checked={v.flag_low_ratings}
        onChange={e => update({ ...v, flag_low_ratings: e.target.checked })} />Include ratings of 1 or 2</label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={v.flag_unresolved}
        onChange={e => update({ ...v, flag_unresolved: e.target.checked })} />Include open move-in issues and partially resolved or unresolved maintenance issues</label>
    </div>,
  },
];
