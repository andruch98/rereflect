'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { MessageSquare, Plus, Send, Sparkles } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { askGeniusAPI } from '@/lib/api/ask-genius';
import { MessageBubble } from '@/components/copilot/MessageBubble';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Textarea } from '@/components/ui/textarea';
import type { ChatMessage } from '@/components/copilot/ChatArea';

const STARTERS = [
  'What do residents praise?',
  'What complaints mention staff?',
  'How many reviews are positive or negative?',
  'What information is missing from these reviews?',
];

function isDefiniteFailure(error: unknown): boolean {
  return isAxiosError(error) && error.response?.status === 502 &&
    error.response?.data?.detail?.code === 'ask_genius_failed';
}

function questionError(error: unknown): string {
  const status = isAxiosError(error) ? error.response?.status : undefined;
  if (status === 409) return 'This question is still being processed. Wait a moment before trying again.';
  if (status === 503) return 'Ask Genius is not ready yet. Check the setup status and try again.';
  if (isDefiniteFailure(error)) return 'This answer could not be completed. Send the question again to start a new attempt.';
  if (status === 403 || status === 404) return 'This conversation is not available to your account.';
  if (status === 422) return 'This question could not be processed within the current limits. Try a shorter question or start a new conversation.';
  return 'The answer could not be completed. Your question is still here; you can try again.';
}

/** A fresh keyed session prevents an account change from reusing private chat state. */
export function AskGenius() {
  const { user } = useAuth();
  if (!user) return <p role="status" className="p-6">Loading your account…</p>;
  return <GeniusSession key={`${user.organization_id}:${user.id}`} organizationId={user.organization_id} userId={user.id} />;
}

function GeniusSession({ organizationId, userId }: { organizationId: number; userId: number }) {
  const queryClient = useQueryClient();
  const scope = ['ask-genius', organizationId, userId];
  const [conversationId, setConversationId] = useState<string>();
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [completed, setCompleted] = useState<{ id: string; messages: ChatMessage[] }>();
  const request = useRef<{ question: string; conversationId?: string; id: string } | undefined>(undefined);
  const busyRef = useRef(false);
  const answerEnd = useRef<HTMLDivElement>(null);
  const status = useQuery({ queryKey: [...scope, 'status'], queryFn: askGeniusAPI.status, retry: false });
  const history = useQuery({ queryKey: [...scope, 'history'], queryFn: askGeniusAPI.conversations, retry: false });
  const detail = useQuery({
    queryKey: [...scope, 'conversation', conversationId],
    queryFn: () => askGeniusAPI.conversation(conversationId!),
    enabled: !!conversationId,
    retry: false,
  });
  const messages = completed && completed.id === conversationId ? completed.messages : detail.data?.messages || [];
  const ready = status.data?.ready === true && !status.isError;
  const loadingConversation = !!conversationId && detail.isPending && completed?.id !== conversationId;
  const canSend = ready && !busy && !loadingConversation && !detail.isError;
  useEffect(() => { if (messages.length || busy) answerEnd.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }); }, [messages.length, busy]);

  function selectConversation(id?: string) {
    if (busyRef.current) return;
    setConversationId(id);
    setCompleted(undefined);
    setError('');
    setInput('');
    request.current = undefined;
  }

  async function send() {
    const question = input.trim();
    if (!canSend || busyRef.current || !question || question.length > 2000) return;
    busyRef.current = true;
    setBusy(true);
    setError('');
    if (request.current?.question !== question || request.current.conversationId !== conversationId) {
      request.current = { question, conversationId, id: crypto.randomUUID() };
    }
    try {
      const answer = await askGeniusAPI.ask(question, request.current.id, conversationId);
      const previous = messages;
      const createdAt = new Date().toISOString();
      const updated = [...previous,
        { id: `user-${request.current.id}`, role: 'user' as const, content: question, structured_data: null, created_at: createdAt },
        { id: answer.message_id, role: 'assistant' as const, content: answer.answer,
          structured_data: Array.isArray(answer.structured_data) ? { structured_data: answer.structured_data } : answer.structured_data || null, created_at: createdAt },
      ];
      setCompleted({ id: answer.conversation_id, messages: updated });
      setConversationId(answer.conversation_id);
      setInput('');
      request.current = undefined;
      void queryClient.invalidateQueries({ queryKey: [...scope, 'history'] });
      void queryClient.invalidateQueries({ queryKey: [...scope, 'conversation', answer.conversation_id] });
    } catch (caught) {
      setError(questionError(caught));
      // Only the app's persisted failure marker permits a new attempt. A proxy
      // 502 or network failure may hide a successful result: replay the same ID.
      if (isDefiniteFailure(caught)) request.current = undefined;
      void queryClient.invalidateQueries({ queryKey: [...scope, 'history'] });
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  return <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
    <header className="mb-6 space-y-1"><h1 className="text-3xl font-semibold">Ask Genius</h1><p className="text-muted-foreground">Ask questions about this community’s saved reviews and analyses.</p></header>
    <div className="grid min-h-[32rem] gap-6 lg:grid-cols-[15rem_minmax(0,1fr)]">
      <aside aria-label="Conversation history" className="space-y-4 rounded-xl border p-4">
        <Button variant="outline" className="w-full" onClick={() => selectConversation()} disabled={busy}><Plus className="mr-2 h-4 w-4" />New conversation</Button>
        <h2 className="text-sm font-medium">Your conversations</h2>
        {history.isPending ? <p role="status" className="text-sm text-muted-foreground">Loading history…</p>
          : history.isError ? <div className="space-y-2"><p className="text-sm">History could not be loaded.</p><Button variant="outline" size="sm" onClick={() => history.refetch()}>Reload history</Button></div>
            : !history.data?.conversations.length ? <p className="text-sm text-muted-foreground">Your conversations will appear here.</p>
              : <ul className="max-h-48 space-y-1 overflow-auto lg:max-h-[32rem]">{history.data.conversations.map(conversation => <li key={conversation.public_id}><button type="button" disabled={busy} aria-current={conversationId === conversation.public_id ? 'page' : undefined} onClick={() => selectConversation(conversation.public_id)} className={`flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm disabled:opacity-50 ${conversationId === conversation.public_id ? 'bg-muted' : 'hover:bg-muted/50'}`}><MessageSquare aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" /><span className="break-words">{conversation.title}</span></button></li>)}</ul>}
      </aside>
      <section aria-label="Ask Genius conversation" className="flex min-w-0 flex-col rounded-xl border bg-background">
        <div className="min-h-64 flex-1 space-y-4 p-4 sm:p-6">
          {status.isPending ? <p role="status" className="text-sm text-muted-foreground">Checking Ask Genius…</p>
            : status.isError ? <Alert><AlertDescription>Ask Genius could not be reached. <button type="button" className="underline" onClick={() => status.refetch()}>Check again</button></AlertDescription></Alert>
              : !ready ? <Alert><AlertDescription>Ask Genius setup is not complete yet. You can read saved conversations; new questions will be available once setup is complete. <button type="button" className="underline" onClick={() => status.refetch()}>Check again</button></AlertDescription></Alert> : null}
          {loadingConversation ? <p role="status">Loading conversation…</p>
            : detail.isError ? <Alert variant="destructive"><AlertDescription>This conversation could not be loaded. <button type="button" className="underline" onClick={() => detail.refetch()}>Try again</button></AlertDescription></Alert>
              : <>
                {messages.length ? <div aria-live="polite">{messages.map(message => <MessageBubble key={message.id} message={message} answerOnly />)}</div>
                  : <div className="mx-auto max-w-xl space-y-5 py-6"><Sparkles className="h-8 w-8 text-primary" aria-hidden="true" /><h2 className="text-xl font-medium">What would you like to know?</h2><div className="grid gap-2 sm:grid-cols-2">{STARTERS.map(question => <button type="button" key={question} onClick={() => setInput(question)} disabled={!ready || busy} className="rounded-xl border p-3 text-left text-sm hover:bg-muted disabled:opacity-50">{question}</button>)}</div></div>}
              </>}
          {busy && <p role="status" className="text-sm text-muted-foreground">Preparing your answer…</p>}
          {error && <Alert variant="destructive"><AlertDescription role="alert">{error}</AlertDescription></Alert>}
          <div ref={answerEnd} />
        </div>
        <form className="space-y-2 border-t p-4" onSubmit={event => { event.preventDefault(); void send(); }}>
          <label htmlFor="genius-question" className="sr-only">Your question</label>
          <div className="flex items-end gap-2"><Textarea id="genius-question" placeholder="Ask about this community’s reviews…" value={input} maxLength={2000} rows={2} disabled={!ready || busy || loadingConversation} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(); } }} /><Button type="submit" disabled={!canSend || !input.trim()} aria-label="Send question"><Send className="h-4 w-4" /></Button></div>
          <p className="text-xs text-muted-foreground">Answers use saved reviews and analyses. Responses, surveys and staff tasks are not connected yet.</p>
        </form>
      </section>
    </div>
  </main>;
}
