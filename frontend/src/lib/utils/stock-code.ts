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
  '000002': '万科A',
  '600030': '中信证券',
  '601166': '兴业银行',
  '600887': '伊利股份',
  '000651': '格力电器',
  '601398': '工商银行',
  '601288': '农业银行',
  '600000': '浦发银行',
  '601857': '中国石油',
  '600028': '中国石化',
  '300750': '宁德时代',
  '002415': '海康威视',
  '600809': '山西汾酒',
  '000568': '泸州老窖',
  '002304': '洋河股份',
  '300059': '东方财富',
  '600570': '恒生电子',
  '688981': '中芯国际',
  '688195': '腾景科技',
  '601888': '中国中免',
  '002714': '牧原股份',
  '600585': '海螺水泥',
  '601668': '中国建筑',
  '000725': '京东方A',
  '002475': '立讯精密',
  '300760': '迈瑞医疗',
  '603259': '药明康德',
  '002032': '苏泊尔',
  '601919': '中远海控',
  '600031': '三一重工',
};

/** 获取股票名称（优先本地缓存） */
export function getStockName(code: string): string {
  return COMMON_STOCKS[code] || code;
}
