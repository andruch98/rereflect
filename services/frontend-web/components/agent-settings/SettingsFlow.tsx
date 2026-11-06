'use client';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Pencil } from 'lucide-react';
import { isAxiosError } from 'axios';
import { settingsError } from '@/lib/api/agent-settings';
import { Button } from '@/components/ui/button';
import type { SettingSection } from '@/lib/api/agent-settings';

export interface SettingStep<T> {
  title: string;
  help: string;
  summary: (values: T) => ReactNode;
  edit: (values: T, update: (values: T) => void) => ReactNode;
}

export function SummaryRows({ rows }: { rows: [string, string][] }) {
  return <dl className="space-y-2 text-sm">
    {rows.map(([label, value]) => <div key={label} className="grid gap-1 sm:grid-cols-[11rem_1fr] sm:gap-4">
      <dt className="text-muted-foreground">{label}</dt><dd className="whitespace-pre-line break-words">{value || 'None specified'}</dd>
    </div>)}
  </dl>;
}

export function SettingsFlow<T>({ section, canEdit, steps, onSave, onRefresh, preview }: {
  section: SettingSection<T>; canEdit: boolean; steps: SettingStep<T>[];
  onSave: (version: number, value: T) => Promise<void>; onRefresh: () => Promise<void>;
  preview?: (values: T, onReady?: (ready: boolean) => void) => ReactNode;
}) {
  const [form, setForm] = useState<{ values: T; version: number } | null>(null);
  const [step, setStep] = useState(0);
  const [editStart, setEditStart] = useState<{ values: T; fromSummary: boolean } | null>(null);
  const [editing, setEditing] = useState(false);
  const [openPreview, setOpenPreview] = useState(false);
  const [previewReady, setPreviewReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState(false);
  const [notice, setNotice] = useState('');
  const heading = useRef<HTMLHeadingElement>(null);
  const didNavigate = useRef(false);
  const values = form?.values ?? section.values;
  const finalStep = step === steps.length;
  const currentView = !canEdit || (section.configured && form?.version !== 0);

  useEffect(() => {
    if (didNavigate.current) heading.current?.focus();
  }, [step, editing, section.configured]);

  function changeStep(index: number) {
    didNavigate.current = true;
    setEditing(false);
    setPreviewReady(false);
    setStep(index);
    setError('');
    if (!form) setForm({ values: section.values, version: section.version });
  }
  function edit(index: number) {
    setEditStart({ values, fromSummary: finalStep });
    changeStep(index);
    setNotice('');
    setOpenPreview(false);
    setEditing(true);
  }
  function cancelEdit() {
    if (currentView) {
      setForm(null);
      setConflict(false);
    } else if (editStart) {
      setForm({ values: editStart.values, version: form?.version ?? section.version });
      if (editStart.fromSummary) setStep(steps.length);
    }
    setEditing(false);
    setError('');
  }
  function changeValues(next: T) {
    setForm({ values: next, version: form?.version ?? section.version });
    setError('');
  }
  async function save() {
    setSaving(true);
    setError('');
    try {
      await onSave(form?.version ?? section.version, values);
      setForm(null);
      setEditing(false);
      setStep(0);
      setNotice('Settings saved.');
    } catch (e) {
      const status = isAxiosError(e) ? e.response?.status : undefined;
      if (status === 409) {
        setConflict(true);
        setError('A teammate changed these settings. Load their changes before editing again.');
      } else {
        setError(settingsError(e, 'Could not save. Your choices are still here.'));
      }
    } finally {
      setSaving(false);
    }
  }
  async function refresh() {
    try {
      await onRefresh();
      setForm(null); setConflict(false); setEditing(false); setError(''); setStep(0);
    } catch {
      setError('Could not load the latest settings. Please try again.');
    }
  }

  const rows = <div className="divide-y rounded-xl border bg-card">
    {steps.map((item, i) => <section key={item.title} className="space-y-3 p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <h3 className="font-semibold">{item.title}</h3>
        {canEdit && <Button type="button" disabled={saving || conflict} variant="ghost" size="sm" aria-label={`Edit ${item.title}`} onClick={() => edit(i)}>
          <Pencil aria-hidden="true" /> Edit</Button>}
      </div>
      {item.summary(values)}
    </section>)}
  </div>;
  return <div className="space-y-4">
    {notice && <p role="status" className="text-sm">{notice}</p>}
    {currentView && !editing ? <>
      <h2 ref={heading} tabIndex={-1} className="text-xl font-semibold">{section.configured ? 'Current settings' : 'Proposed settings'}</h2>
      {!canEdit && <p className="text-sm text-muted-foreground">{section.configured ? 'Only a community manager can edit these settings.' : 'Setup is awaiting confirmation by a community manager.'}</p>}
      {rows}
      {preview && canEdit && <><Button variant="outline" onClick={() => setOpenPreview(!openPreview)} aria-expanded={openPreview}>{openPreview ? 'Hide sample replies' : 'Preview sample replies'}</Button>{openPreview && preview(values)}</>}
    </> : <>
      {!currentView && <p className="text-sm text-muted-foreground">Step {step + 1} of {steps.length + 1} · Save at the final step</p>}
      <form onSubmit={event => {
        event.preventDefault();
        if (conflict || saving || (finalStep && preview && !previewReady)) return;
        if (currentView || finalStep) { void save(); return; }
        changeStep(editing && editStart?.fromSummary ? steps.length : step + 1);
      }} className="space-y-4">
        <div>
          <h2 ref={heading} tabIndex={-1} className="text-xl font-semibold">{finalStep ? 'Review and confirm' : steps[step].title}</h2>
          <p className="mt-1 text-sm text-muted-foreground">{finalStep ? 'Confirm these choices to finish setup for this community.' : steps[step].help}</p>
        </div>
        {finalStep ? <>{rows}{preview?.(values, setPreviewReady)}</>
          : <fieldset disabled={saving || conflict} className="space-y-4 rounded-xl border bg-card p-4 sm:p-5">{editing
            ? steps[step].edit(values, changeValues)
            : <>{steps[step].summary(values)}<Button type="button" variant="outline" size="sm" onClick={() => edit(step)} aria-label={`Edit ${steps[step].title}`}><Pencil aria-hidden="true" /> Edit</Button></>}</fieldset>}
        {error && <div role="alert" className="text-sm text-destructive">{error}{conflict && <Button type="button" variant="link" onClick={() => void refresh()}>Load latest settings</Button>}</div>}
        <div className="flex flex-wrap items-center gap-2">
          {editing ? <Button type="button" disabled={saving || conflict} variant="outline" onClick={cancelEdit}>Cancel edit</Button>
            : step > 0 && <Button type="button" disabled={saving || conflict} variant="outline" onClick={() => changeStep(step - 1)}>Back</Button>}
          <Button type="submit" disabled={saving || conflict || (finalStep && !!preview && !previewReady)}>{saving ? 'Saving…' : currentView ? 'Save changes' : finalStep ? 'Confirm settings' : editing && editStart?.fromSummary ? 'Return to summary' : 'Confirm and continue'}</Button>
        </div>
      </form>
    </>}
  </div>;
}
