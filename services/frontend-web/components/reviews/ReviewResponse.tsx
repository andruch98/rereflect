'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { useAuth } from '@/contexts/AuthContext';
import { reviewRepliesAPI, type ReviewReply } from '@/lib/api/review-replies';
import { replyStatusLabels } from '@/lib/review-response-status';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

type Edit = { text: string; version: number };
type Action = { kind: 'draft' } | { kind: 'save'; edit: Edit } | { kind: 'approve'; version: number };

function actionError(error: unknown) {
  if (isAxiosError(error)) {
    if (error.response?.status === 409) return 'This reply or its settings changed. Review the latest version before continuing.';
    if (error.response?.status === 403) return 'Your account cannot change this reply.';
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }
  return 'The change could not be confirmed. Refresh the reply before trying again.';
}

function timestamp(value: string) {
  return <time dateTime={value}>{new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })}</time>;
}

export function ReviewResponse({ id }: { id: number }) {
  const { user } = useAuth();
  const client = useQueryClient();
  const queryKey = ['boomsay-review-reply', user?.organization_id, user?.id, id];
  const query = useQuery({ queryKey, queryFn: () => reviewRepliesAPI.get(id), enabled: !!user });
  const [edit, setEdit] = useState<Edit | null>(null);
  const mutation = useMutation({
    mutationFn: async (action: Action): Promise<ReviewReply> => {
      if (action.kind === 'save') return reviewRepliesAPI.save(id, action.edit.version, action.edit.text.trim());
      if (action.kind === 'approve') return reviewRepliesAPI.approve(id, action.version);
      return reviewRepliesAPI.draft(id);
    },
    onSuccess: reply => {
      client.setQueryData(queryKey, reply);
      setEdit(null);
      void client.invalidateQueries({ queryKey: ['boomsay-reviews', user?.organization_id, user?.id] });
    },
    onError: () => { void query.refetch(); },
  });

  useEffect(() => {
    if (window.location.hash === '#response') document.getElementById('response')?.scrollIntoView?.();
  }, [id]);

  const reply = query.data;
  const busy = mutation.isPending;
  const canManage = user?.role === 'owner' || user?.role === 'admin';
  const staleEdit = edit && reply && edit.version !== reply.version;
  return <Card id="response" className="scroll-mt-4" aria-labelledby="response-title">
    <CardHeader><CardTitle><h2 id="response-title">BoomSay response</h2></CardTitle></CardHeader>
    <CardContent className="space-y-4">
      {query.isError && <div role="alert">The response could not be loaded. <Button variant="link" onClick={() => query.refetch()}>Try again</Button></div>}
      {query.isPending && <p role="status">Loading response…</p>}
      {reply && <>
        <p role="status" className="text-sm font-medium">{replyStatusLabels[reply.status]}</p>
        {reply.uses_previous_settings && (reply.status === 'pending_approval' || reply.status === 'approved') && <p className="rounded-md border border-border bg-muted px-3 py-2 text-sm">
          This reply uses earlier community settings. Check the wording before {reply.status === 'pending_approval' ? 'approving it' : 'publication'}.
        </p>}
        {reply.generation_method === 'example' && <p className="text-sm text-muted-foreground">Draft source · Built-in example</p>}
        {reply.text && (!edit || !canManage) && <p className="whitespace-pre-wrap break-words leading-relaxed">{reply.text}</p>}
        {reply.status === 'pending_approval' && reply.reason && <p className="text-sm"><strong>Why this needs approval</strong> · {reply.reason}</p>}
        {reply.approved_at && <p className="text-sm text-muted-foreground">Approved{reply.approved_by && <> by {reply.approved_by}</>} · {timestamp(reply.approved_at)}</p>}
        {reply.status === 'published' && reply.published_at && <p className="text-sm text-muted-foreground">Published · {timestamp(reply.published_at)}</p>}
        {reply.status === 'approved' && !reply.publishing_connected && <p className="text-sm">This approved reply is saved in BoomSay. Publishing is waiting for a connected review platform.</p>}
        {reply.status === 'failed' && reply.error && <p role="alert">{reply.error}</p>}
        {!reply.settings_confirmed && ['not_drafted', 'failed'].includes(reply.status) && <p className="text-sm">
          {canManage
            ? <><Link href="/agent-settings" className="font-medium text-primary underline underline-offset-4">Set up review responses</Link> to draft replies for this community.</>
            : 'Ask your community admin to confirm review response settings before creating drafts.'}
        </p>}
        {!canManage && reply.settings_confirmed && reply.status !== 'published' && <p className="text-sm text-muted-foreground">A community admin or owner can manage this reply.</p>}
        {canManage && reply.settings_confirmed && ['not_drafted', 'failed'].includes(reply.status) && <Button disabled={busy} onClick={() => mutation.mutate({ kind: 'draft' })}>
          {busy ? 'Creating draft…' : reply.status === 'failed' ? 'Retry draft' : 'Create draft'}
        </Button>}
        {canManage && reply.status === 'pending_approval' && !edit && !reply.publishing_connected && <p className="text-sm text-muted-foreground">Approval saves your decision. A connected review platform is required to publish.</p>}
        {canManage && ['pending_approval', 'approved'].includes(reply.status) && !edit && <div className="flex flex-wrap gap-2">
          {reply.status === 'pending_approval' && <Button disabled={busy} onClick={() => mutation.mutate({ kind: 'approve', version: reply.version })}>{busy ? 'Approving…' : 'Approve reply'}</Button>}
          <Button variant="outline" disabled={busy} onClick={() => { mutation.reset(); setEdit({ text: reply.text || '', version: reply.version }); }}>{reply.status === 'approved' ? 'Edit approved reply' : 'Edit draft'}</Button>
        </div>}
        {canManage && edit && <div className="space-y-3">
          <label htmlFor="reply-draft" className="block text-sm font-medium">Edit this reply</label>
          {reply.status === 'approved' && <p className="text-sm text-muted-foreground">Saving your edit returns this reply to Needs approval.</p>}
          <Textarea maxLength={4500} id="reply-draft" rows={5} value={edit.text} onChange={e => setEdit({ ...edit, text: e.target.value })} disabled={busy} autoFocus />
          {staleEdit && <p className="text-sm">Another change was saved while you were editing. Copy any wording you want to keep, then cancel to see the updated reply.</p>}
          <div className="flex flex-wrap gap-2">
            <Button disabled={busy || !!staleEdit || !edit.text.trim()} onClick={() => mutation.mutate({ kind: 'save', edit })}>{busy ? 'Saving…' : 'Save draft'}</Button>
            <Button variant="outline" disabled={busy} onClick={() => { setEdit(null); mutation.reset(); }}>Cancel</Button>
          </div>
        </div>}
      </>}
      {mutation.isError && <p role="alert">{actionError(mutation.error)}</p>}
    </CardContent>
  </Card>;
}
