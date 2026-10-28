import type { Metadata } from 'next';
import { SharedGeniusChat } from '@/components/reviews/SharedGeniusChat';

export const metadata: Metadata = {
  title: 'BoomSay — Shared Ask Genius chat',
  robots: { index: false, follow: false },
  referrer: 'no-referrer',
};

export default async function SharedGeniusPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <SharedGeniusChat token={token} />;
}
