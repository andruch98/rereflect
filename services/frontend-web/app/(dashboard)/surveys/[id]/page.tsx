import { SurveyDetail } from '@/components/surveys/SurveyDashboard';
import { readSurveyFilters, type SurveySearchParams } from '@/lib/survey-list-filters';

export default async function SurveyDetailPage({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<SurveySearchParams>;
}) {
  const [{ id }, search] = await Promise.all([params, searchParams]);
  return <SurveyDetail key={id} id={id} listFilters={readSurveyFilters(search)} />;
}
