'use client';

import { useRef, useState } from 'react';
import { MoreHorizontal, Pencil, Pin, PinOff, Share2, SquarePen, Trash2 } from 'lucide-react';
import { askGeniusAPI, type GeniusConversation } from '@/lib/api/ask-genius';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';

interface Props {
  conversations: GeniusConversation[];
  selectedId?: string;
  disabled: boolean;
  loading: boolean;
  failed: boolean;
  onSelect: (id?: string) => void;
  onRefresh: () => void;
  onDeleted: (id: string) => void;
}

export function GeniusChatHistory({ conversations, selectedId, disabled, loading, failed, onSelect, onRefresh, onDeleted }: Props) {
  const [dialog, setDialog] = useState<{ action: 'rename' | 'delete'; chat: GeniusConversation }>();
  const [title, setTitle] = useState('');
  const [mutating, setMutating] = useState(false);
  const mutationRef = useRef(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [uncopiedLink, setUncopiedLink] = useState('');
  const locked = disabled || mutating;
  async function change(action: () => Promise<unknown>, success?: () => void) {
    if (disabled || mutationRef.current) return;
    mutationRef.current = true;
    setMutating(true); setError(''); setNotice(''); setUncopiedLink('');
    try { await action(); success?.(); onRefresh(); }
    catch { setError('This change could not be confirmed. Please try again.'); }
    finally { mutationRef.current = false; setMutating(false); }
  }
  async function share(chat: GeniusConversation) {
    await change(async () => {
      const shared = await askGeniusAPI.shareConversation(chat.public_id);
      const link = new URL(`/share/ask-genius/${encodeURIComponent(shared.token)}`, window.location.origin).href;
      try { await navigator.clipboard.writeText(link); setNotice('Link copied. Anyone with the link can view this chat.'); }
      catch { setUncopiedLink(link); setNotice('Link created. Anyone with the link can view this chat. Select and copy the link below.'); }
    });
  }
  const groups = [
    { title: 'Pinned', rows: conversations.filter(chat => chat.is_pinned) },
    { title: 'Your chats', rows: conversations.filter(chat => !chat.is_pinned) },
  ];
  return <aside aria-label="Chat history" className="flex max-h-56 min-h-0 flex-col rounded-xl border bg-card/30 p-3 lg:max-h-none">
    <Button variant="ghost" className="mb-5 w-full shrink-0 justify-start gap-3 text-base" onClick={() => onSelect()} disabled={locked}><SquarePen className="h-5 w-5" />New chat</Button>
    {loading ? <p role="status" className="px-2 text-sm text-muted-foreground">Loading chats…</p>
      : failed ? <div className="space-y-2 px-2"><p className="text-sm">Chats could not be loaded.</p><Button variant="outline" size="sm" onClick={onRefresh}>Reload chats</Button></div>
        : !conversations.length ? <p className="px-2 text-sm text-muted-foreground">Your chats will appear here.</p>
          : <div className="min-h-0 flex-1 overflow-y-auto">{groups.map(group => !!group.rows.length && <section key={group.title} aria-label={group.title} className="mb-5 space-y-2"><h2 className="px-2 text-xs font-medium text-muted-foreground">{group.title}</h2><ul className="space-y-1">{group.rows.map(chat => <li key={chat.public_id} className={`group flex items-center gap-0.5 rounded-lg px-1 ${selectedId === chat.public_id ? 'bg-muted' : 'hover:bg-muted/50'}`}>
            <button type="button" title={chat.title} disabled={locked} aria-current={selectedId === chat.public_id ? 'page' : undefined} onClick={() => onSelect(chat.public_id)} className="min-w-0 flex-1 truncate rounded-md px-2 py-3 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50">{chat.title}</button>
            <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="h-8 w-7 shrink-0" disabled={locked} aria-label={`Options for ${chat.title}`}><MoreHorizontal className="h-4 w-4" /></Button></DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="w-48 rounded-xl p-2">
                <DropdownMenuItem onSelect={() => { setError(''); setTitle(chat.title); setDialog({ action: 'rename', chat }); }}><Pencil className="mr-2 h-4 w-4" />Rename</DropdownMenuItem>
                <DropdownMenuItem onSelect={() => { void change(() => askGeniusAPI.updateConversation(chat.public_id, { is_pinned: !chat.is_pinned })); }}>{chat.is_pinned ? <PinOff className="mr-2 h-4 w-4" /> : <Pin className="mr-2 h-4 w-4" />}{chat.is_pinned ? 'Unpin' : 'Pin'}</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => { void share(chat); }}><Share2 className="mr-2 h-4 w-4" />Share</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-destructive focus:text-destructive" onSelect={() => { setError(''); setDialog({ action: 'delete', chat }); }}><Trash2 className="mr-2 h-4 w-4" />Delete</DropdownMenuItem>
              </DropdownMenuContent></DropdownMenu>
            <Button variant="ghost" size="icon" className={`h-8 w-7 shrink-0 ${chat.is_pinned ? 'text-foreground' : 'text-muted-foreground'}`} disabled={locked} aria-label={`${chat.is_pinned ? 'Unpin' : 'Pin'} ${chat.title}`} onClick={() => { void change(() => askGeniusAPI.updateConversation(chat.public_id, { is_pinned: !chat.is_pinned })); }}><Pin className={`h-4 w-4 ${chat.is_pinned ? 'fill-current' : ''}`} /></Button>
          </li>)}</ul></section>)}</div>}
    {notice && <p role="status" className="mt-3 rounded-lg border bg-muted/50 p-3 text-xs leading-relaxed">{notice}</p>}
    {uncopiedLink && <Input aria-label="Public chat link" value={uncopiedLink} readOnly onFocus={event => event.currentTarget.select()} className="mt-2 text-xs" />}
    {error && !dialog && <p role="alert" className="mt-3 text-xs text-destructive">{error}</p>}
    <Dialog open={!!dialog} onOpenChange={open => { if (!open && !mutating) setDialog(undefined); }}><DialogContent><DialogHeader><DialogTitle>{dialog?.action === 'rename' ? 'Rename chat' : 'Delete chat?'}</DialogTitle><DialogDescription>{dialog?.action === 'rename' ? 'Keep the existing name or choose your own.' : 'This removes the chat from your history and cannot be undone. Shared copies remain available.'}</DialogDescription></DialogHeader>
      <form onSubmit={event => { event.preventDefault(); if (!dialog) return; if (dialog.action === 'rename') { if (title.trim()) void change(() => askGeniusAPI.updateConversation(dialog.chat.public_id, { title: title.trim() }), () => setDialog(undefined)); } else { void change(() => askGeniusAPI.deleteConversation(dialog.chat.public_id), () => { onDeleted(dialog.chat.public_id); setDialog(undefined); }); } }} className="space-y-4">
        {dialog?.action === 'rename' && <Input aria-label="Chat name" value={title} maxLength={200} disabled={mutating} onChange={event => setTitle(event.target.value)} autoFocus />}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <DialogFooter><Button variant="outline" type="button" disabled={mutating} onClick={() => setDialog(undefined)}>Cancel</Button><Button type="submit" variant={dialog?.action === 'delete' ? 'destructive' : 'default'} disabled={locked || (dialog?.action === 'rename' && !title.trim())}>{mutating ? 'Saving…' : dialog?.action === 'rename' ? 'Save' : 'Delete chat'}</Button></DialogFooter>
      </form></DialogContent></Dialog>
  </aside>;
}
