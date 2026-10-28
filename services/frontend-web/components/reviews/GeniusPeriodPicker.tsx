'use client';

import { Button } from '@/components/ui/button';
import { GENIUS_PERIODS, periodLabel, validPeriod } from '@/lib/ask-genius-options';
import type { GeniusPeriod, GeniusPeriodPreset, GeniusStatus } from '@/lib/api/ask-genius';

const inputClass = 'h-11 min-w-0 rounded-lg border border-input bg-background px-3 text-base shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50';

interface Props {
  period: GeniusPeriod | null;
  highlightRequired: boolean;
  defaultPeriod: GeniusPeriod | null;
  coverage?: GeniusStatus['date_coverage'];
  disabled: boolean;
  saving: boolean;
  notice: string;
  error: string;
  onChange: (period: GeniusPeriod | null) => void;
  onSave: (period: GeniusPeriod | null) => void;
}

export function GeniusPeriodPicker({ period, highlightRequired, defaultPeriod, coverage, disabled, saving, notice, error, onChange, onSave }: Props) {
  const valid = validPeriod(period);
  const needsPeriod = highlightRequired && !valid;
  const isDefault = !!period && !!defaultPeriod && period.preset === defaultPeriod.preset && period.start_date === defaultPeriod.start_date && period.end_date === defaultPeriod.end_date;
  const undated = coverage?.undated_reviews ?? 0;
  return <div className="shrink-0 space-y-2 border-b p-4">
    <div className="flex flex-wrap items-end gap-2">
      <div className="flex min-w-0 flex-1 flex-col gap-1 sm:min-w-64 sm:flex-none">
        <label htmlFor="genius-period" className="text-sm font-medium">Time period</label>
        <select id="genius-period" value={period?.preset ?? ''} disabled={disabled || saving} aria-describedby="genius-period-help" aria-invalid={needsPeriod || undefined} className={`${inputClass} border-primary/70 font-medium${needsPeriod ? ' ring-2 ring-primary' : ''}`} onChange={event => onChange(event.target.value ? { preset: event.target.value as GeniusPeriodPreset } : null)}>
          <option value="">Choose a period</option>
          {GENIUS_PERIODS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </div>
      <Button type="button" size="sm" variant="ghost" className="text-muted-foreground" disabled={disabled || saving || !valid || isDefault} onClick={() => onSave(period)}>{saving ? 'Saving…' : 'Save as my default'}</Button>
      {defaultPeriod && <Button type="button" size="sm" variant="ghost" disabled={disabled || saving} onClick={() => onSave(null)}>Remove default</Button>}
    </div>
    {period?.preset === 'custom' && <div className="flex flex-wrap gap-2">
      <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs sm:flex-none">From<input aria-label="Period start date" type="date" value={period.start_date ?? ''} disabled={disabled || saving} max={period.end_date || undefined} className={inputClass} onChange={event => onChange({ ...period, start_date: event.target.value })} /></label>
      <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs sm:flex-none">Through<input aria-label="Period end date" type="date" value={period.end_date ?? ''} disabled={disabled || saving} min={period.start_date || undefined} className={inputClass} onChange={event => onChange({ ...period, end_date: event.target.value })} /></label>
    </div>}
    <p id="genius-period-help" className={period?.preset === 'custom' && !valid || defaultPeriod ? 'text-xs text-muted-foreground' : 'sr-only'}>{period?.preset === 'custom' && !valid ? 'Choose a valid start and end date before asking.' : !period ? 'Choose a time period before sending. A default is saved only when you ask.' : defaultPeriod ? `Default: ${periodLabel(defaultPeriod)}. Changes here apply to this chat.` : 'This period applies to this chat. Save as my default to use it for new chats.'}</p>
    {undated > 0 && <p className="text-xs text-muted-foreground" data-testid="date-coverage-notice">
      {`${undated} ${undated === 1 ? 'review has' : 'reviews have'} no posting date.`}
      {' '}{period?.preset === 'all_time' ? 'Included in all available history.' : 'Excluded from date filters.'}
      {period?.preset !== 'all_time' && <> <button type="button" disabled={disabled || saving} className="underline underline-offset-2 disabled:opacity-50" onClick={() => onChange({ preset: 'all_time' })}>Use all available history</button>.</>}
    </p>}
    {notice && <p role="status" className="text-xs text-muted-foreground">{notice}</p>}
    {error && <p role="alert" className="text-xs text-destructive">{error}</p>}
  </div>;
}
