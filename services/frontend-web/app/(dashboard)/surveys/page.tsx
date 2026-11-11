import { SurveyDashboard } from '@/components/surveys/SurveyDashboard';
import { readSurveyFilters, type SurveySearchParams } from '@/lib/survey-list-filters';

export default async function SurveysPage({ searchParams }: { searchParams: Promise<SurveySearchParams> }) {
  return <SurveyDashboard initialFilters={readSurveyFilters(await searchParams)} />;
}
