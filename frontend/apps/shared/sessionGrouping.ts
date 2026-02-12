export type SessionGroupInfo = { key: 'today' | 'yesterday' | 'week' | 'older'; label: string };

export const sessionGroupFromIso = (updatedAt?: string): SessionGroupInfo => {
  if (!updatedAt) return { key: 'older', label: '更早' };
  const date = new Date(updatedAt);
  if (Number.isNaN(date.getTime())) return { key: 'older', label: '更早' };
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const target = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
  const diffDays = Math.floor((today - target) / (24 * 60 * 60 * 1000));
  if (diffDays <= 0) return { key: 'today', label: '今天' };
  if (diffDays === 1) return { key: 'yesterday', label: '昨天' };
  if (diffDays <= 7) return { key: 'week', label: '近 7 天' };
  return { key: 'older', label: '更早' };
};

export const sessionGroupOrder: Record<string, number> = {
  today: 0,
  yesterday: 1,
  week: 2,
  older: 3,
};
