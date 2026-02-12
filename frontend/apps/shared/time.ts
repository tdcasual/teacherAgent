export const nowTime = () =>
  new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });

export const timeFromIso = (iso?: string) => {
  if (!iso) return nowTime();
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return nowTime();
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
};

export const formatSessionUpdatedLabel = (ts?: string) => {
  if (!ts) return '';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return '';
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.floor((today.getTime() - target.getTime()) / (24 * 60 * 60 * 1000));
  if (diffDays <= 0) return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
  if (diffDays === 1) return '昨天';
  if (diffDays < 7) {
    const names = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
    return names[d.getDay()] || '';
  }
  return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }).replace('/', '-');
};
