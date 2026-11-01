'use client';

import { useRef, useState } from 'react';
import { surveysAPI } from '@/lib/api/surveys';
import { Button } from '@/components/ui/button';

export function SurveyUnsubscribe({ token }: { token: string }) {
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(false);
  const lock = useRef(false);
  async function unsubscribe() {
    if (lock.current || done) return;
    lock.current = true; setBusy(true); setError(false);
    try {
      const result = await surveysAPI.unsubscribe(token);
      if (result.status !== 'unsubscribed') throw new Error('Unsubscribe not confirmed');
      setDone(true);
    } catch { setError(true); }
    finally { lock.current = false; setBusy(false); }
  }
  return <main className="mx-auto max-w-xl space-y-5 px-4 py-12"><h1 className="text-2xl font-semibold">Survey email preferences</h1>{done ? <p role="status">Future survey invitations for this community are stopped. You can still complete your existing survey.</p> : <><p>Stop future survey invitations for this community? Your existing answers will be preserved.</p>{error && <p role="alert" className="text-destructive">Your preference could not be saved. Check the complete link and try again.</p>}<Button disabled={busy} onClick={() => { void unsubscribe(); }}>{busy ? 'Saving…' : 'Stop survey invitations'}</Button></>}</main>;
}
