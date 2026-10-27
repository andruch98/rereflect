'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import type { ColumnDef, SortingState } from '@tanstack/react-table';
import { ArrowUpDown, Inbox } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { feedbackAPI, type FeedbackItem, type FeedbackFilters } from '@/lib/api/feedback';
import { DataTable } from '@/components/shared/data-table';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ReviewRating, ReviewSentiment, ReviewAnalysisStatus, reviewSourceLabel } from './ReviewFields';

const columns: ColumnDef<FeedbackItem>[] = [
  { accessorKey: 'id', header: ({ column }) => <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>Review <ArrowUpDown className="ml-2 h-4 w-4" aria-hidden="true" /></Button>,
    cell: ({ row }) => <Link className="font-medium underline underline-offset-4" href={`/feedbacks/${row.original.id}`}>Review #{row.original.id}</Link> },
  { accessorKey: 'star_rating', header: ({ column }) => <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>Stars <ArrowUpDown className="ml-2 h-4 w-4" aria-hidden="true" /></Button>,
    cell: ({ row }) => <ReviewRating rating={row.original.star_rating} /> },
  { accessorKey: 'text', header: 'Review text', cell: ({ row }) => <p className="max-w-xl whitespace-pre-wrap break-words line-clamp-3">{row.original.text.trim() ? row.original.text : row.original.star_rating != null ? 'Rating only — no written review' : 'No written review'}</p> },
  { accessorKey: 'source', header: 'Source', cell: ({ row }) => reviewSourceLabel(row.original.source) },
  { accessorKey: 'sentiment_label', header: ({ column }) => <Button variant="ghost" onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}>Overall sentiment <ArrowUpDown className="ml-2 h-4 w-4" aria-hidden="true" /></Button>,
    cell: ({ row }) => <ReviewSentiment sentiment={row.original.sentiment_label} /> },
  { id: 'analysis', header: 'Analysis', cell: ({ row }) => <ReviewAnalysisStatus analysis={row.original.apartment_analysis} /> },
];

export function ReviewsInbox() {
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [sentiment, setSentiment] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [sorting, setSorting] = useState<SortingState>([]);

  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedSearch(search); setPage(1); }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const filters: FeedbackFilters = {
    search: debouncedSearch || undefined, sentiment: sentiment || undefined,
    sort_by: sorting[0]?.id || 'id', sort_order: sorting[0]?.desc ? 'desc' : 'asc',
  };
  const query = useQuery({
    // Scope the browser cache as well as retaining the API's authenticated organization filter.
    queryKey: ['boomsay-reviews', user?.organization_id, user?.id, page, pageSize, filters],
    queryFn: () => feedbackAPI.list(page, pageSize, filters),
    enabled: !!user,
    // Preserve search focus and sort controls between requests, but never across accounts.
    placeholderData: (previous, previousQuery) =>
      previousQuery?.queryKey[1] === user?.organization_id && previousQuery?.queryKey[2] === user?.id
        ? previous : undefined,
  });

  return <main className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div><h1 className="text-3xl font-semibold">Reviews</h1><p className="mt-1 text-muted-foreground">Original reviews and their saved analyses.</p></div>
      <Button variant="outline" onClick={() => query.refetch()} disabled={!user || query.isFetching}>Refresh</Button>
    </div>
    <label className="flex w-fit items-center gap-3 text-sm">Overall sentiment
      <select aria-label="Filter by overall sentiment" value={sentiment} onChange={e => { setSentiment(e.target.value); setPage(1); }} className="rounded-md border border-input bg-background px-3 py-2">
        <option value="">All sentiments</option>
        {['positive', 'negative', 'mixed', 'neutral', 'unknown'].map(value => <option key={value} value={value}>{value.charAt(0).toUpperCase() + value.slice(1)}</option>)}
      </select>
    </label>
    {query.isError ? <Alert variant="destructive"><AlertDescription>Reviews could not be loaded. Please try Refresh.</AlertDescription></Alert>
      : query.isPending ? <p role="status">Loading reviews…</p>
      : <DataTable columns={columns} data={query.data.items} searchQuery={search} onSearchChange={setSearch}
        searchPlaceholder="Search review text…" isSearching={search !== debouncedSearch || query.isFetching}
        emptyIcon={Inbox} emptyTitle="No reviews found" emptyDescription="Try adjusting your search or sentiment filter."
        totalCount={query.data.total} serverSide pageCount={Math.max(1, query.data.total_pages)} currentPage={page} pageSize={pageSize}
        onPageChange={setPage} onPageSizeChange={size => { setPageSize(size); setPage(1); }}
        onSortingChange={next => { setSorting(next); setPage(1); }} getRowId={row => String(row.id)} />}
  </main>;
}
