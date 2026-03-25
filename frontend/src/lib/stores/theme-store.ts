// Input: 无（纯状态管理）
// Output: theme/stockColorScheme状态与切换方法
// Pos: 全局主题状态store，被ThemeProvider和Navbar消费
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

import { create } from 'zustand';

type Theme = 'light' | 'dark';
type StockColorScheme = 'cn' | 'us';

interface ThemeState {
  theme: Theme;
  stockColorScheme: StockColorScheme;
  toggleTheme: () => void;
  toggleColorScheme: () => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: 'dark',
  stockColorScheme: 'cn',
  toggleTheme: () => set((state) => ({ theme: state.theme === 'dark' ? 'light' : 'dark' })),
  toggleColorScheme: () => set((state) => ({ stockColorScheme: state.stockColorScheme === 'cn' ? 'us' : 'cn' })),
}));
