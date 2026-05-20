/**
 * Input: 用户输入的搜索关键词(股票代码/名称)
 * Output: 匹配的股票列表下拉 + 选中回调(code, name)
 * Pos: components/common/stock-search.tsx - 股票搜索组件
 * 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。
 */
"use client";
import { useState, useEffect, useRef, useMemo } from "react";
import { Search } from "lucide-react";
import { COMMON_STOCKS } from "@/lib/utils/stock-code";

interface Props {
  onSelect: (code: string, name: string) => void;
  placeholder?: string;
}

export function StockSearch({ onSelect, placeholder = "搜索股票代码或名称..." }: Props) {
  const [query, setQuery] = useState("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // 搜索逻辑（useMemo 计算，避免 set-state-in-effect）
  const results = useMemo(() => {
    if (!query.trim()) return [];
    const q = query.toLowerCase();
    return Object.entries(COMMON_STOCKS)
      .filter(([code, name]) => code.includes(q) || name.toLowerCase().includes(q))
      .map(([code, name]) => ({ code, name }))
      .slice(0, 8);
  }, [query]);
  const isOpen = dropdownOpen && results.length > 0;

  // 点击外部关闭
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <div className="flex items-center gap-2 bg-muted/50 rounded-lg px-3 py-2 border border-border/50 focus-within:border-primary/50 focus-within:ring-2 focus-within:ring-primary/20 transition-all">
        <Search className="h-4 w-4 text-muted-foreground shrink-0" />
        <input
          type="text"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setDropdownOpen(true); }}
          placeholder={placeholder}
          className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-muted-foreground/50"
          onFocus={() => query && setDropdownOpen(true)}
        />
        {query && (
          <button onClick={() => { setQuery(''); setDropdownOpen(false); }} className="text-muted-foreground hover:text-foreground">
            ✕
          </button>
        )}
      </div>

      {/* 搜索结果下拉 */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1 bg-popover border rounded-lg shadow-lg overflow-hidden z-50 animate-fade-in">
          {results.map((item) => (
            <button
              key={item.code}
              className="w-full flex items-center justify-between px-3 py-2 hover:bg-accent transition-colors text-sm"
              onClick={() => {
                onSelect(item.code, item.name);
                setQuery('');
                setDropdownOpen(false);
              }}
            >
              <span className="font-mono text-primary">{item.code}</span>
              <span className="text-muted-foreground">{item.name}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
