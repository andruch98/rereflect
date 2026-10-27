'use client';

import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { MessageSquare, Plus, Send, Sparkles } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { askGeniusAPI } from '@/lib/api/ask-genius';
import type { GeniusPeriod, GeniusStatus } from '@/lib/api/ask-genius';
import { GENIUS_QUESTION_GROUPS, GENIUS_STARTERS, periodLabel, validPeriod } from '@/lib/ask-genius-options';
import { GeniusPeriodPicker } from './GeniusPeriodPicker';
import { MessageBubble } from '@/components/copilot/MessageBubble';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Textarea } from '@/components/ui/textarea';
import type { ChatMessage } from '@/components/copilot/ChatArea';

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
  if (status === 422) {
    const detail = isAxiosError(error) ? error.response?.data?.detail : undefined;
    if (typeof detail === 'string' && detail.trim()) return detail;
    return 'Check the selected period and question. Ask Genius needs a valid period and a question within its current limits.';
  }
  return 'The answer could not be completed. Your question is still here; you can try again.';
}

// This only enables submitting an explicit preference request before selection.
// The server independently validates intent, dates, ownership and persistence.
function asksToChangeDefault(value: string): boolean {
  const text = value.trim();
  const command = text.replace(/[.!?]+$/, '').trim()
    .replace(/^(?:please\s+|(?:can|could|would)\s+you\s+(?:please\s+)?)/i, '')
    .replace(/\s*,?\s*(?:going\s+forward|from\s+now\s+on)$/i, '');
  return /^(?:(?:use|save|set|make)\b.+\bdefault\b|(?:remove|clear|forget|reset|delete)\b.+\bdefault\b)/i.test(command) ||
    (!text.endsWith('?') && /\bis my default(?:\s+(?:period|timeframe))?$/i.test(command));
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
  const [selectedPeriod, setSelectedPeriod] = useState<GeniusPeriod | null>();
  const [savingPreference, setSavingPreference] = useState(false);
  const [preferenceNotice, setPreferenceNotice] = useState('');
  const [preferenceError, setPreferenceError] = useState('');
  const [browseQuestions, setBrowseQuestions] = useState(false);
  const [completed, setCompleted] = useState<{ id: string; messages: ChatMessage[]; period: GeniusPeriod | null }>();
  const request = useRef<{ question: string; conversationId?: string; periodKey: string; id: string } | undefined>(undefined);
  const busyRef = useRef(false);
  const preferenceBusy = useRef(false);
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
  const storedPeriod = conversationId ? (completed?.id === conversationId ? completed.period : detail.data?.period ?? null) : status.data?.default_period ?? null;
  const period = selectedPeriod === undefined ? storedPeriod : selectedPeriod;
  const periodKey = JSON.stringify(period);
  const ready = status.data?.ready === true && !status.isError;
  const loadingConversation = !!conversationId && detail.isPending && completed?.id !== conversationId;
  const canInteract = ready && !busy && !savingPreference && !loadingConversation && !detail.isError;
  const canChooseQuestion = canInteract && validPeriod(period);
  const canSend = canInteract && (validPeriod(period) || asksToChangeDefault(input));
  const availableSources = status.data?.available_sources ?? [];
  useEffect(() => { if (messages.length || busy) answerEnd.current?.scrollIntoView?.({ behavior: 'smooth', block: 'nearest' }); }, [messages.length, busy]);

  function selectConversation(id?: string) {
    if (busyRef.current || preferenceBusy.current) return;
    setConversationId(id);
    setCompleted(undefined);
    setError('');
    setInput('');
    setSelectedPeriod(undefined);
    setPreferenceNotice('');
    setPreferenceError('');
    setBrowseQuestions(false);
    request.current = undefined;
  }

  function changePeriod(value: GeniusPeriod | null) {
    if (busyRef.current || preferenceBusy.current) return;
    setSelectedPeriod(value);
    setError('');
    setPreferenceNotice('');
    request.current = undefined;
  }

  async function saveDefaultPeriod(value: GeniusPeriod | null) {
    if (busyRef.current || preferenceBusy.current || (value && !validPeriod(value))) return;
    preferenceBusy.current = true;
    setSavingPreference(true);
    setPreferenceNotice('');
    setPreferenceError('');
    try {
      const saved = await askGeniusAPI.saveDefaultPeriod(value);
      // Keep the current conversation's period when removing a future default.
      if (selectedPeriod === undefined) setSelectedPeriod(period);
      queryClient.setQueryData<GeniusStatus>([...scope, 'status'], previous => previous ? { ...previous, default_period: saved.default_period } : previous);
      setPreferenceNotice(saved.default_period ? `${periodLabel(saved.default_period)} saved as your default for new conversations.` : 'Default removed. Choose a period when starting a new conversation.');
    } catch {
      setPreferenceError('Your default change could not be confirmed. Try again.');
    } finally {
      preferenceBusy.current = false;
      setSavingPreference(false);
    }
  }

  async function send() {
    const question = input.trim();
    if (!canSend || busyRef.current || !question || question.length > 2000) return;
    busyRef.current = true;
    setBusy(true);
    setError('');
    if (request.current?.question !== question || request.current.conversationId !== conversationId || request.current.periodKey !== periodKey) {
      request.current = { question, conversationId, periodKey, id: crypto.randomUUID() };
    }
    try {
      const answer = await askGeniusAPI.ask(question, request.current.id, conversationId, validPeriod(period) ? period : undefined);
      const previous = messages;
      const createdAt = new Date().toISOString();
      const updated = [...previous,
        { id: `user-${request.current.id}`, role: 'user' as const, content: question, structured_data: null, created_at: createdAt },
        { id: answer.message_id, role: 'assistant' as const, content: answer.answer,
          structured_data: Array.isArray(answer.structured_data) ? { structured_data: answer.structured_data } : answer.structured_data || null, created_at: createdAt },
      ];
      setCompleted({ id: answer.conversation_id, messages: updated, period: answer.period });
      setConversationId(answer.conversation_id);
      setSelectedPeriod(answer.period);
      if (answer.preference_updated) {
        queryClient.setQueryData<GeniusStatus>([...scope, 'status'], previous => previous ? { ...previous, default_period: answer.default_period } : previous);
      }
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

  return <main className="flex h-[calc(100dvh-4rem)] min-h-[30rem] w-full min-w-0 flex-col px-4 py-4 sm:px-6">
    <header className="mb-4 shrink-0 space-y-1"><h1 className="text-3xl font-semibold">Ask Genius</h1><p className="text-muted-foreground">Ask questions about this community’s saved reviews and analysis.</p></header>
    <div className="grid min-h-0 flex-1 grid-rows-[auto_minmax(0,1fr)] gap-4 lg:grid-cols-[16rem_minmax(0,1fr)] lg:grid-rows-1">
      <aside aria-label="Conversation history" className="flex max-h-44 min-h-0 flex-col gap-3 rounded-xl border p-4 lg:max-h-none">
        <Button variant="outline" className="w-full shrink-0" onClick={() => selectConversation()} disabled={busy || savingPreference}><Plus className="mr-2 h-4 w-4" />New conversation</Button>
        <h2 className="shrink-0 text-sm font-medium">Your conversations</h2>
        {history.isPending ? <p role="status" className="text-sm text-muted-foreground">Loading history…</p>
          : history.isError ? <div className="space-y-2"><p className="text-sm">History could not be loaded.</p><Button variant="outline" size="sm" onClick={() => history.refetch()}>Reload history</Button></div>
            : !history.data?.conversations.length ? <p className="text-sm text-muted-foreground">Your conversations will appear here.</p>
              : <ul className="min-h-0 flex-1 space-y-1 overflow-auto">{history.data.conversations.map(conversation => <li key={conversation.public_id}><button type="button" disabled={busy || savingPreference} aria-current={conversationId === conversation.public_id ? 'page' : undefined} onClick={() => selectConversation(conversation.public_id)} className={`flex w-full items-start gap-2 rounded-lg px-2 py-2 text-left text-sm disabled:opacity-50 ${conversationId === conversation.public_id ? 'bg-muted' : 'hover:bg-muted/50'}`}><MessageSquare aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" /><span className="break-words">{conversation.title}</span></button></li>)}</ul>}
      </aside>
      <section aria-label="Ask Genius conversation" className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-xl border bg-background">
        <GeniusPeriodPicker period={period} defaultPeriod={status.data?.default_period ?? null} coverage={status.data?.date_coverage} disabled={status.isPending || status.isError || busy || loadingConversation} saving={savingPreference} notice={preferenceNotice} error={preferenceError} onChange={changePeriod} onSave={value => { void saveDefaultPeriod(value); }} />
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overflow-x-hidden p-4 sm:p-6">
          {status.isPending ? <p role="status" className="text-sm text-muted-foreground">Checking Ask Genius…</p>
            : status.isError ? <Alert><AlertDescription>Ask Genius could not be reached. <button type="button" className="underline" onClick={() => status.refetch()}>Check again</button></AlertDescription></Alert>
              : !ready ? <Alert><AlertDescription>Ask Genius setup is not complete yet. You can read saved conversations; new questions will be available once setup is complete. <button type="button" className="underline" onClick={() => status.refetch()}>Check again</button></AlertDescription></Alert> : null}
          {loadingConversation ? <p role="status">Loading conversation…</p>
            : detail.isError ? <Alert variant="destructive"><AlertDescription>This conversation could not be loaded. <button type="button" className="underline" onClick={() => detail.refetch()}>Try again</button></AlertDescription></Alert>
              : <>
                {messages.length ? <div aria-live="polite">{messages.map(message => <MessageBubble key={message.id} message={message} answerOnly />)}</div>
                  : <div className="mx-auto w-full max-w-3xl space-y-5 py-4 sm:py-6">
                    <Sparkles className="h-8 w-8 text-primary" aria-hidden="true" /><h2 className="text-xl font-medium">What would you like to know?</h2>
                    <div className="grid gap-2 sm:grid-cols-2">{GENIUS_STARTERS.filter(starter => starter.sources.every(source => availableSources.includes(source))).map(({ question }) => <button type="button" key={question} onClick={() => setInput(question)} disabled={!canChooseQuestion} className="rounded-xl border p-4 text-left text-sm hover:bg-muted disabled:opacity-50">{question}</button>)}</div>
                    <Button type="button" variant="outline" aria-expanded={browseQuestions} aria-controls="genius-question-library" disabled={!canInteract} onClick={() => setBrowseQuestions(value => !value)}>Browse more questions</Button>
                    {browseQuestions && <div id="genius-question-library" className="grid gap-4 sm:grid-cols-2">{GENIUS_QUESTION_GROUPS.filter(group => availableSources.includes(group.source)).map(group => <section key={group.source} className="space-y-2" aria-label={`${group.title} questions`}><h3 className="text-sm font-semibold">{group.title}</h3><ul className="space-y-2">{group.questions.map(question => <li key={question}><button type="button" disabled={!canChooseQuestion} onClick={() => setInput(question)} className="w-full rounded-lg border px-3 py-2 text-left text-sm hover:bg-muted disabled:opacity-50">{question}</button></li>)}</ul></section>)}</div>}
                  </div>}
              </>}
          {busy && <p role="status" className="text-sm text-muted-foreground">Preparing your answer…</p>}
          {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}
          <div ref={answerEnd} />
        </div>
        <form className="shrink-0 space-y-2 border-t p-4" onSubmit={event => { event.preventDefault(); void send(); }}>
          <label htmlFor="genius-question" className="sr-only">Your question</label>
          <div className="flex items-end gap-2"><Textarea id="genius-question" placeholder={validPeriod(period) ? 'Ask about this community’s reviews…' : 'Choose a period above, then ask your question…'} value={input} maxLength={2000} rows={2} disabled={!canInteract} onChange={event => setInput(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void send(); } }} /><Button type="submit" disabled={!canSend || !input.trim()} aria-label="Send question"><Send className="h-4 w-4" /></Button></div>
          <p className="text-xs text-muted-foreground">Answers use saved reviews and analysis. Surveys and management responses are not connected yet.</p>
        </form>
      </section>
    </div>
  </main>;
}
