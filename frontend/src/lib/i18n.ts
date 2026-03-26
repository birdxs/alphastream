// Input: locale key
// Output: 翻译后的字符串
// Pos: lib/i18n.ts - 国际化基础骨架
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

type Locale = 'zh' | 'en';

const translations: Record<Locale, Record<string, string>> = {
  zh: {
    'nav.chat': '对话',
    'nav.dashboard': '看板',
    'nav.screener': '选股',
    'nav.search': '搜索股票...',
    'chat.welcome.title': 'AI金融分析助手',
    'chat.welcome.subtitle': '13个智能Agent协同 · 实时市场数据 · 大师级投研视角',
    'chat.input.placeholder': '输入股票代码或分析问题...',
    'chat.send': '发送',
    'chat.stop': '停止生成',
    'chat.new': '+ 新对话',
    'market.realtime': '实时数据待接入',
    'artifact.workspace': 'AI智能分析工作区',
    'artifact.hint': 'AI将为您生成交互式分析组件',
    'dashboard.title': '投资看板',
    'screener.title': '选股器',
    'stock.analyze': 'AI分析',
    'stock.watchlist': '自选',
    'common.loading': '加载中...',
    'common.error': '加载失败',
    'common.retry': '重试',
    'common.nodata': '暂无数据',
  },
  en: {
    'nav.chat': 'Chat',
    'nav.dashboard': 'Dashboard',
    'nav.screener': 'Screener',
    'nav.search': 'Search stocks...',
    'chat.welcome.title': 'AI Financial Analyst',
    'chat.welcome.subtitle': '13 AI Agents · Real-time Data · Expert Insights',
    'chat.input.placeholder': 'Enter stock code or analysis question...',
    'chat.send': 'Send',
    'chat.stop': 'Stop',
    'chat.new': '+ New Chat',
    'market.realtime': 'Real-time data pending',
    'artifact.workspace': 'AI Analysis Workspace',
    'artifact.hint': 'AI will generate interactive analysis components',
    'dashboard.title': 'Dashboard',
    'screener.title': 'Screener',
    'stock.analyze': 'AI Analyze',
    'stock.watchlist': 'Watchlist',
    'common.loading': 'Loading...',
    'common.error': 'Failed to load',
    'common.retry': 'Retry',
    'common.nodata': 'No data',
  }
};

let currentLocale: Locale = 'zh';

export function setLocale(locale: Locale) { currentLocale = locale; }
export function getLocale(): Locale { return currentLocale; }
export function t(key: string): string {
  return translations[currentLocale]?.[key] || translations.zh[key] || key;
}
export type { Locale };
