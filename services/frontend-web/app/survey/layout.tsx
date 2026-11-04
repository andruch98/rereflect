import type { Metadata } from 'next';

export const metadata: Metadata = {
  robots: { index: false, follow: false },
  referrer: 'no-referrer',
};

export default function SurveyLayout({ children }: { children: React.ReactNode }) {
  return children;
}
