import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import { agentSettingsAPI, settingsError, type HoldTopic, type ReviewSettings } from '@/lib/api/agent-settings';
import { SummaryRows, type SettingStep } from './SettingsFlow';

const tones = { warm: 'Warm and personal', professional: 'Friendly and professional', concise: 'Brief and direct' };
const topics = { safety: 'Safety', billing: 'Billing', legal: 'Legal issues', staff_allegations: 'Staff allegations' };
const selectStyle = 'block rounded-md border border-input bg-background p-2 text-sm';
const threshold = (rating: number) => rating === 0 ? 'No rating threshold' : `${rating} star${rating === 1 ? '' : 's'} or below`;

export const reviewSteps: SettingStep<ReviewSettings>[] = [
  {
    title: 'Community details',
    help: 'Choose the community facts and contact details BoomSay may use in public replies.',
    summary: v => <SummaryRows rows={[
      ['Public community name', v.community_name], ['Approved facts', v.facts],
      ['Public email', v.public_email], ['Public phone', v.public_phone],
    ]} />,
    edit: (v, update) => <div className="space-y-4 text-sm">
      <label className="block space-y-1"><span>Public community name</span><Input required maxLength={200} value={v.community_name}
        onChange={e => update({ ...v, community_name: e.target.value })} /></label>
      <label className="block space-y-1"><span>Approved facts (optional)</span><Textarea maxLength={1500}
        placeholder="For example, office hours or how residents can reach the leasing team."
        value={v.facts} onChange={e => update({ ...v, facts: e.target.value })} /></label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-1"><span>Public email (optional)</span><Input type="email" maxLength={254} value={v.public_email}
          onChange={e => update({ ...v, public_email: e.target.value })} /></label>
        <label className="space-y-1"><span>Public phone (optional)</span><Input type="tel" maxLength={48} value={v.public_phone}
          onChange={e => update({ ...v, public_phone: e.target.value })} /></label>
      </div>
    </div>,
  },
  {
    title: 'Reply style',
    help: 'Choose how replies should sound and how BoomSay should handle praise and complaints.',
    summary: v => <SummaryRows rows={[
      ['Tone', tones[v.tone]], ['Signature', v.signature], ['For praise', v.praise_guidance], ['For complaints', v.complaint_guidance],
    ]} />,
    edit: (v, update) => <div className="space-y-4 text-sm">
      <label className="block space-y-1"><span>Tone</span><select className={selectStyle} value={v.tone}
        onChange={e => update({ ...v, tone: e.target.value as ReviewSettings['tone'] })}>
        {Object.entries(tones).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label>
      <label className="block space-y-1"><span>Signature (optional)</span><Input maxLength={160} value={v.signature}
        onChange={e => update({ ...v, signature: e.target.value })} /></label>
      <label className="block space-y-1"><span>For praise (optional)</span><Textarea maxLength={500} value={v.praise_guidance}
        placeholder="For example, thank the resident for the specific detail they mentioned."
        onChange={e => update({ ...v, praise_guidance: e.target.value })} /></label>
      <label className="block space-y-1"><span>For complaints (optional)</span><Textarea maxLength={500} value={v.complaint_guidance}
        placeholder="For example, invite the resident to contact the office privately."
        onChange={e => update({ ...v, complaint_guidance: e.target.value })} /></label>
    </div>,
  },
  {
    title: 'Reply approval',
    help: 'Decide which replies you want to check before publication.',
    summary: v => <SummaryRows rows={v.mode === 'approval' ? [['Approval', 'A manager approves every reply']] : [
      ['Approval', 'BoomSay approves eligible replies automatically'], ['Hold for a manager', threshold(v.hold_at_or_below)],
      ['Always hold these topics', v.hold_topics.map(t => topics[t]).join(', ')],
    ]} />,
    edit: (v, update) => <div className="space-y-4 text-sm">
      <fieldset className="space-y-2"><legend className="mb-2 font-medium">Who approves replies?</legend>
        {(['approval', 'automatic'] as const).map(mode => <label key={mode} className="flex items-center gap-2">
          <input type="radio" name="reply-approval" checked={v.mode === mode} onChange={() => update({ ...v, mode })} />
          {mode === 'approval' ? 'A manager approves every reply' : 'BoomSay approves eligible replies automatically'}
        </label>)}
      </fieldset>
      {v.mode === 'automatic' && <>
        <label className="block space-y-1"><span>Hold reviews with these ratings</span><select className={selectStyle} value={v.hold_at_or_below}
          onChange={e => update({ ...v, hold_at_or_below: Number(e.target.value) })}>
          {[0, 1, 2, 3, 4, 5].map(rating => <option key={rating} value={rating}>{threshold(rating)}</option>)}</select></label>
        <fieldset><legend className="mb-2 font-medium">Hold these topics at any rating</legend><div className="grid gap-2 sm:grid-cols-2">
          {(Object.keys(topics) as HoldTopic[]).map(topic => <label key={topic} className="flex items-center gap-2">
            <input type="checkbox" checked={v.hold_topics.includes(topic)} onChange={e => update({ ...v,
              hold_topics: e.target.checked ? [...v.hold_topics, topic] : v.hold_topics.filter(t => t !== topic) })} />{topics[topic]}</label>)}
        </div></fieldset>
      </>}
    </div>,
  },
];

export function ReviewSamples({ values, onReady }: { values: ReviewSettings; onReady?: (ready: boolean) => void }) {
  const { user } = useAuth();
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['review-reply-samples', user?.organization_id, user?.id, values],
    queryFn: () => agentSettingsAPI.preview(values), retry: false, staleTime: Infinity,
  });
  useEffect(() => { onReady?.(!!data?.examples.length); }, [data, onReady]);
  return <section className="space-y-3 rounded-xl border bg-card p-4 sm:p-5">
    <h3 className="font-semibold">Sample replies</h3>
    <p className="text-sm text-muted-foreground">These fictional reviews show what would happen with your choices. Samples stay private.</p>
    {isPending && <p role="status" className="text-sm">Preparing sample replies…</p>}
    {isError && <div role="alert" className="space-y-2 text-sm"><p>{settingsError(error, 'Could not load the sample replies.')}</p>
      <Button type="button" variant="outline" size="sm" onClick={() => void refetch()}>Try preview again</Button></div>}
    {data && <>
      {data.examples.some(sample => sample.generation_method === 'example') &&
        <p className="text-sm text-muted-foreground">Local templates preview tone, signature and approval rules. A connected AI writer can also use your facts and writing guidance.</p>}
      {data.examples.map(sample => <article key={sample.review_text} className="space-y-2 border-t pt-4 text-sm">
        <p className="font-medium">{sample.star_rating}-star review</p><blockquote>{sample.review_text}</blockquote>
        <div className="rounded-md bg-muted p-3">
          <p className="mb-1 font-medium">{sample.generation_method === 'example' ? 'Example reply · local template' : 'Sample AI reply'}</p>
          <p className="whitespace-pre-line">{sample.text}</p>
        </div>
        <p><strong>{sample.status === 'approved' ? 'Would be approved automatically' : 'Would need manager approval'}</strong>{sample.reason && ` · ${sample.reason}`}</p>
      </article>)}
      {!data.publishing_connected && <p className="text-sm text-muted-foreground">Publishing is disconnected. Approved replies stay in Reviews until a publishing channel is connected.</p>}
    </>}
  </section>;
}
