'use client';

import { useQuery } from '@tanstack/react-query';
import { askGeniusAPI } from '@/lib/api/ask-genius';
import { Button } from '@/components/ui/button';
import { BoomSayLogo } from './BoomSayLogo';
import { GeniusMessage } from './GeniusMessage';

export function SharedGeniusChat({ token }: { token: string }) {
  const query = useQuery({ queryKey: ['ask-genius-public-snapshot', token], queryFn: () => askGeniusAPI.shared(token), retry: false });
  return <main className="min-h-dvh bg-background px-4 py-6 text-foreground sm:px-8">
    <header className="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-4 border-b pb-5">
      <BoomSayLogo /><p className="text-sm text-muted-foreground">Ask Genius · Shared chat</p>
    </header>
    <div className="mx-auto w-full max-w-3xl py-8 sm:py-12">
      {query.isPending ? <p role="status">Loading shared chat…</p>
        : query.isError ? <section role="alert" className="space-y-4 rounded-xl border p-6"><h1 className="text-xl font-semibold">This shared chat is unavailable</h1><p>Check the link and try again.</p><Button variant="outline" onClick={() => { void query.refetch(); }}>Try again</Button></section>
          : <><div className="mb-9 space-y-3 border-b pb-6"><h1 className="break-words text-2xl font-semibold sm:text-3xl">{query.data.title}</h1><p className="text-sm text-muted-foreground">A read-only copy of this chat. Later messages are not included.</p></div>
            {query.data.messages.map(message => <GeniusMessage key={message.id} message={message} publicSnapshot />)}
          </>}
    </div>
  </main>;
}
