import type { GeniusPeriod, GeniusPeriodPreset } from '@/lib/api/ask-genius';

export const GENIUS_PERIODS: { value: GeniusPeriodPreset; label: string }[] = [
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'last_14_days', label: 'Last 14 days' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'last_month', label: 'Last calendar month' },
  { value: 'last_quarter', label: 'Last calendar quarter' },
  { value: 'last_6_months', label: 'Last 6 months' },
  { value: 'year_to_date', label: 'Year to date' },
  { value: 'all_time', label: 'All available history' },
  { value: 'custom', label: 'Custom dates' },
];

export function periodLabel(period: GeniusPeriod | null | undefined): string {
  if (!period) return 'Choose a period';
  if (period.preset === 'custom' && period.start_date && period.end_date) return `${period.start_date} to ${period.end_date}`;
  return GENIUS_PERIODS.find(option => option.value === period.preset)?.label ?? 'Choose a period';
}

export function validPeriod(period: GeniusPeriod | null | undefined): period is GeniusPeriod {
  if (!period || !GENIUS_PERIODS.some(option => option.value === period.preset)) return false;
  if (period.preset !== 'custom') return true;
  const isDate = (value?: string) => {
    if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const date = new Date(`${value}T00:00:00Z`);
    return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value;
  };
  return isDate(period.start_date) && isDate(period.end_date) && period.start_date! <= period.end_date!;
}

export const GENIUS_STARTERS = [
  { question: 'Which topics came up most often in reviews during this period?', sources: ['reviews', 'analysis'] },
  { question: 'What were the main complaints in reviews during this period?', sources: ['reviews', 'analysis'] },
  { question: 'What did residents praise in reviews during this period?', sources: ['reviews', 'analysis'] },
  { question: 'How many reviews did we receive at each star rating during this period?', sources: ['reviews'] },
];

// Curated suggestions are local UI content. Browsing or choosing one never calls a model.
export const GENIUS_QUESTION_GROUPS = [
  { source: 'reviews', title: 'Reviews', questions: [
    'How many written reviews did we receive during this period?',
    'Show me the one- and two-star reviews from this period.',
    'How many reviews in this period contained only a star rating?',
  ] },
  { source: 'analysis', title: 'Analysis', questions: [
    'Which topics had negative feedback in reviews during this period?',
    'What did reviews say about maintenance during this period?',
    'What did reviews say about staff during this period?',
  ] },
  { source: 'surveys', title: 'Surveys', questions: [
    'How many survey responses did we receive during this period?',
    'What concerns appeared in survey answers during this period?',
  ] },
  { source: 'management_responses', title: 'Management responses', questions: [
    'What follow-ups did we promise residents in management responses during this period?',
  ] },
];
