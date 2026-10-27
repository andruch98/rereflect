'use client';

import { Button } from '@/components/ui/button';
import { GENIUS_PERIODS, periodLabel, validPeriod } from '@/lib/ask-genius-options';
import type { GeniusPeriod, GeniusPeriodPreset, GeniusStatus } from '@/lib/api/ask-genius';

const inputClass = 'h-9 min-w-0 rounded-md border border-input bg-background px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50';

interface Props {
  period: GeniusPeriod | null;
  defaultPeriod: GeniusPeriod | null;
  coverage?: GeniusStatus['date_coverage'];
  disabled: boolean;
  saving: boolean;
  notice: string;
  error: string;
  onChange: (period: GeniusPeriod | null) => void;
  onSave: (period: GeniusPeriod | null) => void;
}

export function GeniusPeriodPicker({ period, defaultPeriod, coverage, disabled, saving, notice, error, onChange, onSave }: Props) {
  const valid = validPeriod(period);
  const isDefault = !!period && !!defaultPeriod && period.preset === defaultPeriod.preset && period.start_date === defaultPeriod.start_date && period.end_date === defaultPeriod.end_date;
  const undated = coverage?.undated_reviews ?? 0;
  return <div className="shrink-0 space-y-2 border-b p-4">
    <div className="flex flex-wrap items-end gap-2">
      <div className="flex min-w-0 flex-1 flex-col gap-1 sm:min-w-52 sm:flex-none">
        <label htmlFor="genius-period" className="text-sm font-medium">Time period</label>
        <select id="genius-period" value={period?.preset ?? ''} disabled={disabled || saving} aria-describedby="genius-period-help" className={inputClass} onChange={event => onChange(event.target.value ? { preset: event.target.value as GeniusPeriodPreset } : null)}>
          <option value="">Choose a period</option>
          {GENIUS_PERIODS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </div>
      <Button type="button" size="sm" variant="outline" disabled={disabled || saving || !valid || isDefault} onClick={() => onSave(period)}>{saving ? 'Saving…' : 'Save as my default'}</Button>
      {defaultPeriod && <Button type="button" size="sm" variant="ghost" disabled={disabled || saving} onClick={() => onSave(null)}>Remove default</Button>}
    </div>
    {period?.preset === 'custom' && <div className="flex flex-wrap gap-2">
      <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs sm:flex-none">From<input aria-label="Period start date" type="date" value={period.start_date ?? ''} disabled={disabled || saving} max={period.end_date || undefined} className={inputClass} onChange={event => onChange({ ...period, start_date: event.target.value })} /></label>
      <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs sm:flex-none">Through<input aria-label="Period end date" type="date" value={period.end_date ?? ''} disabled={disabled || saving} min={period.start_date || undefined} className={inputClass} onChange={event => onChange({ ...period, end_date: event.target.value })} /></label>
    </div>}
    <p id="genius-period-help" className="text-xs text-muted-foreground">{period?.preset === 'custom' && !valid ? 'Choose a valid start and end date before asking.' : !period ? 'Choose a period before starting. Nothing is saved as your default until you ask.' : defaultPeriod ? `Your saved default: ${periodLabel(defaultPeriod)}. Changing this selection applies to this conversation.` : 'This period applies to this conversation. Save it only if you want it used for new conversations.'}</p>
    {undated > 0 && <p className="text-xs text-muted-foreground" data-testid="date-coverage-notice">
      {coverage?.dated_reviews === 0 ? `All ${undated} saved reviews are missing their original posting dates.` : `${undated} of ${coverage?.total_reviews} saved reviews are missing their original posting dates.`}
      {' '}{period?.preset === 'all_time' ? 'They are included in all available history; time-based comparisons are unavailable for those reviews.' : 'They cannot be included in a date-filtered answer.'}
      {period?.preset !== 'all_time' && <> <button type="button" disabled={disabled || saving} className="underline underline-offset-2 disabled:opacity-50" onClick={() => onChange({ preset: 'all_time' })}>Use all available history</button>.</>}
    </p>}
    {notice && <p role="status" className="text-xs text-muted-foreground">{notice}</p>}
    {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
  </div>;
}
