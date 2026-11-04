import type { Metadata } from 'next';
import { ResidentSurvey } from '@/components/surveys/ResidentSurvey';

export const metadata: Metadata = {
  title: 'Resident survey — BoomSay',
  robots: { index: false, follow: false },
  referrer: 'no-referrer',
};

export default async function ResidentSurveyPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <ResidentSurvey key={token} token={token} />;
}
