export const replyStatusLabels = {
  not_drafted: 'No draft',
  pending_approval: 'Needs approval',
  approved: 'Approved · awaiting publication',
  published: 'Published',
  failed: 'Draft failed',
} as const;

export type ReplyStatus = keyof typeof replyStatusLabels;

export function readReplyFilter(value: unknown): ReplyStatus | '' {
  return typeof value === 'string' && Object.hasOwn(replyStatusLabels, value) ? value as ReplyStatus : '';
}

export function replyFilterQuery(status: ReplyStatus | '') {
  return status ? `?response_status=${status}` : '';
}
