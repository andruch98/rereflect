import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import React from 'react';

// ── next/navigation ──────────────────────────────────────────────────────────
const navigation = vi.hoisted(() => ({ pathname: '/dashboard' }));
vi.mock('next/navigation', () => ({
  usePathname: () => navigation.pathname,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

// ── next/link — render as plain <a> ─────────────────────────────────────────
vi.mock('next/link', () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode; [k: string]: unknown }) => (
    <a href={href} {...rest}>{children}</a>
  ),
}));

// ── Logo ─────────────────────────────────────────────────────────────────────
vi.mock('@/components/Logo', () => ({
  Logo: () => <span>Logo</span>,
}));

// ── Sidebar UI — lightweight pass-throughs ───────────────────────────────────
vi.mock('@/components/ui/sidebar', () => ({
  Sidebar: ({ children }: { children: React.ReactNode }) => <nav data-testid="sidebar">{children}</nav>,
  SidebarContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarGroup: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarGroupContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarGroupLabel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarMenu: ({ children }: { children: React.ReactNode }) => <ul>{children}</ul>,
  SidebarMenuButton: ({ children, isActive }: { children: React.ReactNode; isActive?: boolean }) => <div data-active={isActive}>{children}</div>,
  SidebarMenuItem: ({ children }: { children: React.ReactNode }) => <li>{children}</li>,
}));

// ── Collapsible — always-open pass-through ────────────────────────────────────
vi.mock('@/components/ui/collapsible', () => ({
  Collapsible: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CollapsibleContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CollapsibleTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// ── DropdownMenu — pass-through ───────────────────────────────────────────────
vi.mock('@/components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
    <button onClick={onClick}>{children}</button>
  ),
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

// ── authAPI — mock getMe ──────────────────────────────────────────────────────
const mockGetMe = vi.fn();
vi.mock('@/lib/api/auth', () => ({
  authAPI: {
    getMe: () => mockGetMe(),
    logout: vi.fn(),
  },
}));

import { AppSidebar } from '@/components/AppSidebar';

const makeUser = (role: 'owner' | 'admin' | 'member') => ({
  id: 1,
  email: `${role}@test.com`,
  role,
  plan: 'pro',
  organization_id: 1,
  is_system_admin: false,
});

beforeEach(() => {
  vi.clearAllMocks();
  navigation.pathname = '/dashboard';
});

describe('AppSidebar — Surveys active route', () => {
  it.each([
    ['/surveys', true, false],
    ['/surveys/898d2883-c5bb-47af-82ff-e8a64014da25', true, false],
    ['/customers', false, true],
    ['/customers/resident%40example.invalid', false, true],
    ['/surveys-other', false, false],
  ])('marks Surveys and Customers independently on %s', async (pathname, surveysActive, customersActive) => {
    navigation.pathname = pathname;
    mockGetMe.mockResolvedValue(makeUser('member'));
    render(<AppSidebar />);
    await waitFor(() => expect(screen.getByRole('link', { name: /Preferences/i })).toBeInTheDocument());
    expect(screen.getByRole('link', { name: 'Surveys' }).closest('[data-active]'))
      .toHaveAttribute('data-active', String(surveysActive));
    expect(screen.getByRole('link', { name: 'Customers' }).closest('[data-active]'))
      .toHaveAttribute('data-active', String(customersActive));
  });
});

describe('AppSidebar — Usage Events nav entry', () => {
  it('shows "Usage Events" link for admin users', async () => {
    mockGetMe.mockResolvedValue(makeUser('admin'));
    render(<AppSidebar />);
    await waitFor(() => {
      expect(screen.getByRole('link', { name: /Usage Events/i })).toBeInTheDocument();
    });
  });

  it('shows "Usage Events" link for owner users', async () => {
    mockGetMe.mockResolvedValue(makeUser('owner'));
    render(<AppSidebar />);
    await waitFor(() => {
      expect(screen.getByRole('link', { name: /Usage Events/i })).toBeInTheDocument();
    });
  });

  it('hides "Usage Events" link for member users', async () => {
    mockGetMe.mockResolvedValue(makeUser('member'));
    render(<AppSidebar />);
    // Wait for the user to load, then assert the link is absent
    await waitFor(() => {
      // Confirm the user loaded by checking a non-gated link is present
      expect(screen.getByRole('link', { name: /Preferences/i })).toBeInTheDocument();
    });
    expect(screen.queryByRole('link', { name: /Usage Events/i })).not.toBeInTheDocument();
  });

  it('"Usage Events" link points to /settings/usage-events', async () => {
    mockGetMe.mockResolvedValue(makeUser('admin'));
    render(<AppSidebar />);
    await waitFor(() => {
      const link = screen.getByRole('link', { name: /Usage Events/i });
      expect(link).toHaveAttribute('href', '/settings/usage-events');
    });
  });

  it('does not show "Usage Events" before user loads (null user)', () => {
    // getMe never resolves — user stays null
    mockGetMe.mockReturnValue(new Promise(() => {}));
    render(<AppSidebar />);
    expect(screen.queryByRole('link', { name: /Usage Events/i })).not.toBeInTheDocument();
  });

  it('hides "Workflow" settings link for member users but keeps "Playbooks" (read-only list)', async () => {
    mockGetMe.mockResolvedValue(makeUser('member'));
    const { container } = render(<AppSidebar />);
    await waitFor(() => {
      expect(screen.getByRole('link', { name: /Playbooks/i })).toBeInTheDocument();
    });
    expect(container.querySelector('a[href="/settings/workflow"]')).toBeNull();
  });

  it('shows "Workflow" settings link for admin users', async () => {
    mockGetMe.mockResolvedValue(makeUser('admin'));
    const { container } = render(<AppSidebar />);
    await waitFor(() => {
      expect(container.querySelector('a[href="/settings/workflow"]')).not.toBeNull();
    });
  });
});
