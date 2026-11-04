import { SurveyUnsubscribe } from '@/components/surveys/SurveyUnsubscribe';

export default async function SurveyUnsubscribePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <SurveyUnsubscribe key={token} token={token} />;
}
