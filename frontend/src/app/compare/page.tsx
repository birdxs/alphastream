// Input: 用户输入的多个股票代码
// Output: 多股票对比页面UI，含标签管理、快速对比表格、AI分析入口，Dark Glassmorphism风格
// Pos: src/app/compare/page.tsx - 多股票对比路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, X, BarChart3 } from "lucide-react";
import { GlassCard } from "@/components/common/glass-card";
import { getStockName } from "@/lib/utils/stock-code";
import Link from "next/link";

export default function ComparePage() {
  const [codes, setCodes] = useState<string[]>(["600519", "000858"]);
  const [newCode, setNewCode] = useState("");

  const addCode = () => {
    if (newCode && /^\d{6}$/.test(newCode) && !codes.includes(newCode) && codes.length < 4) {
      setCodes([...codes, newCode]);
      setNewCode("");
    }
  };

  const removeCode = (code: string) => {
    setCodes(codes.filter(c => c !== code));
  };

  const TAG_COLORS = ['bg-[#3737CC]', 'bg-[#46BEA3]', 'bg-[#FF8767]', 'bg-[#6B5EE4]'];

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BarChart3 className="h-6 w-6" />
          多股票对比
        </h1>
        <div className="flex gap-2">
          <Input
            value={newCode}
            onChange={e => setNewCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
            placeholder="添加代码"
            className="w-28 bg-white/[0.04] border-white/[0.1]"
            maxLength={6}
            onKeyDown={e => e.key === 'Enter' && addCode()}
          />
          <Button size="sm" onClick={addCode} disabled={codes.length >= 4} className="bg-white/[0.08] border border-white/[0.12] hover:bg-white/[0.15] text-foreground">
            <Plus className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* 对比股票标签 */}
      <div className="flex gap-2 flex-wrap">
        {codes.map((code, i) => (
          <div key={code} className="flex items-center gap-1.5 bg-white/[0.06] border border-white/[0.1] rounded-full px-3 py-1.5">
            <div className={`w-2 h-2 rounded-full ${TAG_COLORS[i]}`} />
            <Link href={`/stock/${code}`} className="font-mono text-sm hover:text-[#6B5EE4] transition-colors">{code}</Link>
            <span className="text-xs text-white/40">{getStockName(code)}</span>
            <button onClick={() => removeCode(code)} className="ml-1 text-white/30 hover:text-white/70 transition-colors">
              <X className="h-3 w-3" />
            </button>
          </div>
        ))}
      </div>

      {/* AI对比分析入口 */}
      <GlassCard padding="lg" glow="brand">
        <div className="text-center space-y-4">
          <p className="text-white/50">选择2-4只股票，点击下方按钮启动AI对比分析</p>
          <Link href={`/?stock=${codes[0]}&message=对比分析${codes.map(c => c + getStockName(c)).join('和')}`}>
            <Button size="lg" className="gap-2 bg-[#3737CC] hover:bg-[#4545DD] text-white" disabled={codes.length < 2}>
              启动AI对比分析
            </Button>
          </Link>
          <p className="text-xs text-white/30">
            AI将从技术面、基本面、资金面、风险等维度综合对比
          </p>
        </div>
      </GlassCard>

      {/* 基础对比表格 */}
      {codes.length >= 2 && (
        <GlassCard padding="lg">
          <h2 className="text-sm font-semibold mb-4">快速对比</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.08]">
                  <th className="text-left py-2.5 px-3 text-white/40 text-xs font-medium">指标</th>
                  {codes.map(code => (
                    <th key={code} className="text-right py-2.5 px-3 font-mono text-xs font-medium">{code}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {['名称', '行业', '市值', 'PE(TTM)', 'PB', 'ROE'].map(metric => (
                  <tr key={metric} className="border-b border-white/[0.04] hover:bg-white/[0.03] transition-colors">
                    <td className="py-2.5 px-3 text-white/40">{metric}</td>
                    {codes.map(code => (
                      <td key={code} className="text-right py-2.5 px-3 font-mono">
                        {metric === '名称' ? getStockName(code) : '--'}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-white/25 mt-3 text-center">
            详细数据请通过AI对比分析获取
          </p>
        </GlassCard>
      )}
    </div>
  );
}
