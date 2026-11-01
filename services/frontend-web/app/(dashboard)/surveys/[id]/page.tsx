import { SurveyDetail } from '@/components/surveys/SurveyDashboard';

export default async function SurveyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SurveyDetail key={id} id={id} />;
}
