/**
 * Input: 原始数字
 * Output: 金融格式化字符串
 * Pos: lib/utils/format.ts - 全局数据格式化工具
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

/** 格式化金融数字（千位分隔符 + 指定小数位） */
export function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value === undefined || value === null || isNaN(value)) return '--';
  return value.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** 格式化价格（保留2位小数） */
export function formatPrice(price: number | string | undefined): string {
  if (price === undefined || price === null) return '--';
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (isNaN(num)) return '--';
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** 格式化百分比（+X.XX% / -X.XX% / 0.00%） */
export function formatPercent(value: number | string | null | undefined, decimals = 2): string {
  if (value === undefined || value === null) return '--';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '--';
  if (num > 0) return `+${num.toFixed(decimals)}%`;
  if (num < 0) return `${num.toFixed(decimals)}%`;
  return `${num.toFixed(decimals)}%`;
}

/** 格式化价格变动（带颜色class） */
export function formatChange(value: number | null | undefined): { text: string; className: string } {
  if (value === undefined || value === null || isNaN(value)) return { text: '--', className: '' };
  if (value > 0) return { text: `+${value.toFixed(2)}%`, className: 'stock-up' };
  if (value < 0) return { text: `${value.toFixed(2)}%`, className: 'stock-down' };
  return { text: '0.00%', className: '' };
}

/** 格式化大数字（万/亿） */
export function formatLargeNumber(num: number | undefined): string {
  if (num === undefined || num === null) return '--';
  const abs = Math.abs(num);
  if (abs >= 1e8) return `${(num / 1e8).toFixed(2)}亿`;
  if (abs >= 1e4) return `${(num / 1e4).toFixed(2)}万`;
  return num.toFixed(2);
}

/** 格式化成交量 */
export function formatVolume(vol: number | undefined): string {
  if (vol === undefined || vol === null) return '--';
  if (vol >= 1e8) return `${(vol / 1e8).toFixed(1)}亿`;
  if (vol >= 1e4) return `${(vol / 1e4).toFixed(0)}万`;
  return vol.toString();
}

/** 格式化日期时间 */
export function formatDateTime(dateStr: string | undefined): string {
  if (!dateStr) return '--';
  try {
    const date = new Date(dateStr);
    return date.toLocaleString('zh-CN', {
      month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
    });
  } catch {
    return dateStr;
  }
}

/** 涨跌色CSS类 */
export function getPriceColorClass(value: number | undefined): string {
  if (value === undefined || value === 0) return 'text-muted-foreground';
  return value > 0 ? 'stock-up' : 'stock-down';
}
