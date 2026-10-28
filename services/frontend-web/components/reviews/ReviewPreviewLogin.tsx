'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { authAPI } from '@/lib/api/auth';
import { BoomSayLogo } from './BoomSayLogo';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardHeader } from '@/components/ui/card';

export function ReviewPreviewLogin() {
  const router = useRouter();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {
      const result = await authAPI.login({ email, password });
      login(result.access_token); router.push('/feedbacks');
    } catch { setError('Sign-in failed. Check your credentials and try again.'); }
    finally { setBusy(false); }
  }
  return <main className="flex min-h-screen items-center justify-center bg-background px-4">
    <Card className="w-full max-w-md"><CardHeader className="items-center gap-6 pt-8"><BoomSayLogo /><h1 className="text-2xl font-semibold">Sign in</h1></CardHeader>
      <CardContent><form onSubmit={submit} className="space-y-5">
        <div className="space-y-2"><Label htmlFor="email">Email</Label><Input id="email" type="email" autoComplete="username" required value={email} onChange={e => setEmail(e.target.value)} /></div>
        <div className="space-y-2"><Label htmlFor="password">Password</Label><Input id="password" type="password" autoComplete="current-password" required value={password} onChange={e => setPassword(e.target.value)} /></div>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <Button className="w-full" disabled={busy} type="submit">{busy ? 'Signing in…' : 'Sign in'}</Button>
      </form></CardContent>
    </Card>
  </main>;
}
