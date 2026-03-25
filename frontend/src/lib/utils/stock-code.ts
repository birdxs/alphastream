/**
 * Input: 股票代码字符串
 * Output: 验证结果、市场类型推断
 * Pos: lib/utils/stock-code.ts - 股票代码解析验证
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */

/** 验证A股代码格式 */
export function isValidAShareCode(code: string): boolean {
  return /^\d{6}$/.test(code);
}

/** 从代码推断市场 */
export function inferMarket(code: string): 'sh' | 'sz' | 'unknown' {
  if (code.startsWith('6')) return 'sh';
  if (code.startsWith('0') || code.startsWith('3')) return 'sz';
  return 'unknown';
}

/** 从文本中提取股票代码 */
export function extractStockCodes(text: string): string[] {
  const matches = text.match(/\b\d{6}\b/g);
  return matches ? [...new Set(matches)] : [];
}

/** 常见股票代码->名称映射 */
export const COMMON_STOCKS: Record<string, string> = {
  '600519': '贵州茅台',
  '000001': '平安银行',
  '000858': '五粮液',
  '601318': '中国平安',
  '600036': '招商银行',
  '000333': '美的集团',
  '600276': '恒瑞医药',
  '002594': '比亚迪',
  '601012': '隆基绿能',
  '600900': '长江电力',
};

/** 获取股票名称（优先本地缓存） */
export function getStockName(code: string): string {
  return COMMON_STOCKS[code] || code;
}
