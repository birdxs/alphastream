/**
 * Input: 原始数字/字符串
 * Output: 格式化的显示文本
 * Pos: lib/utils/format.ts - 金融数据格式化工具函数
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

/** 格式化价格（保留2位小数） */
export function formatPrice(price: number | string | undefined): string {
  if (price === undefined || price === null) return '--';
  const num = typeof price === 'string' ? parseFloat(price) : price;
  if (isNaN(num)) return '--';
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** 格式化百分比（+/- 符号） */
export function formatPercent(value: number | string | undefined, decimals = 2): string {
  if (value === undefined || value === null) return '--';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  if (isNaN(num)) return '--';
  if (num > 0) return `\u25B2 +${num.toFixed(decimals)}%`;
  if (num < 0) return `\u25BC ${num.toFixed(decimals)}%`;
  return `${num.toFixed(decimals)}%`;
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
