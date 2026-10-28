'use client';
import { useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useAuth } from '@/contexts/AuthContext';
import apiClient from '@/lib/api-client';
import { BoomSayLogo } from './BoomSayLogo';
import { Button } from '@/components/ui/button';
import { Sidebar, SidebarProvider, SidebarHeader, SidebarContent, SidebarFooter, SidebarInset, SidebarTrigger, SidebarMenu, SidebarMenuItem, SidebarMenuButton } from '@/components/ui/sidebar';
import { MessageSquare, LogOut, Sparkles } from 'lucide-react';

export function ReviewPreviewLayout({ children }: { children: React.ReactNode }) {
  const { user, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const allowed = pathname === '/ask-genius' || pathname === '/feedbacks' || /^\/feedbacks\/\d+$/.test(pathname);
  useEffect(() => { if (!allowed) router.replace('/ask-genius'); }, [allowed, router]);
  const community = useQuery({
    queryKey: ['review-preview-community', user?.organization_id, user?.id],
    queryFn: async () => (await apiClient.get<{ organization_id: number; name: string }>('/api/v1/feedback/preview-community')).data,
    enabled: !!user, retry: false,
  });
  return <SidebarProvider>
    <Sidebar collapsible="icon">
      <SidebarHeader className="px-4 py-6">
        <Link href="/ask-genius" aria-label="BoomSay home" className="group-data-[collapsible=icon]:hidden"><BoomSayLogo /></Link>
        <Link href="/ask-genius" aria-label="BoomSay home" className="hidden group-data-[collapsible=icon]:block"><BoomSayLogo mark /></Link>
      </SidebarHeader>
      <SidebarContent className="px-2"><SidebarMenu>
        <SidebarMenuItem><SidebarMenuButton asChild isActive={pathname === '/ask-genius'} tooltip="Ask Genius"><Link href="/ask-genius"><Sparkles /><span>Ask Genius</span></Link></SidebarMenuButton></SidebarMenuItem>
        <SidebarMenuItem><SidebarMenuButton asChild isActive={pathname.startsWith('/feedbacks')} tooltip="Reviews"><Link href="/feedbacks"><MessageSquare /><span>Reviews</span></Link></SidebarMenuButton></SidebarMenuItem>
      </SidebarMenu></SidebarContent>
      <SidebarFooter><SidebarMenu><SidebarMenuItem><SidebarMenuButton onClick={logout} tooltip="Sign out"><LogOut /><span>Sign out</span></SidebarMenuButton></SidebarMenuItem></SidebarMenu></SidebarFooter>
    </Sidebar>
    <SidebarInset>
      <header className="flex h-16 items-center gap-4 border-b px-4"><SidebarTrigger /><span className="font-medium">{community.data?.name || 'Community access'}</span></header>
      {community.isError ? <div role="alert" className="space-y-3 p-6"><p>The test community could not be loaded. Your account must be connected to the configured Lake House preview.</p><Button variant="outline" onClick={() => community.refetch()}>Try again</Button></div>
        : !community.data ? <p role="status" className="p-6">Loading community…</p>
          : allowed ? children : <p role="status" className="p-6">Opening Ask Genius…</p>}
    </SidebarInset>
  </SidebarProvider>;
}
