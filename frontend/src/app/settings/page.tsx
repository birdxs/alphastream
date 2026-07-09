// Input: 全局主题状态（theme-store）
// Output: 设置页面，含主题切换、涨跌颜色、系统信息
// Pos: /settings路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { useEffect } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useThemeStore } from "@/lib/stores/theme-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { Sun, Moon, Trash2, Database, Brain, Tag } from "lucide-react";
import { useToast } from "@/components/common/toast-provider";

export default function SettingsPage() {
  useEffect(() => {
    document.title = "设置 - AI金融分析";
  }, []);

  const { theme, toggleTheme, stockColorScheme, toggleColorScheme } = useThemeStore();
  const { researchDepth, setResearchDepth, enableMemory, setEnableMemory } = useSettingsStore();
  const { toast } = useToast();

  const handleClearCache = () => {
    try {
      // 选择性清理项目相关 localStorage，不波及其他应用数据
      localStorage.removeItem('watchlist-store');
      localStorage.removeItem('portfolio-store');
      localStorage.removeItem('chat-store');
      localStorage.removeItem('theme');
      toast("缓存已清除，页面即将刷新", "success");
      setTimeout(() => window.location.reload(), 1000);
    } catch {
      toast("清除缓存失败", "error");
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>

      {/* 外观设置 */}
      <Card className="glass-card">
        <CardHeader><CardTitle className="text-sm">外观</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">主题模式</p>
              <p className="text-xs text-muted-foreground">选择亮色或暗色主题</p>
            </div>
            <Button variant="outline" onClick={toggleTheme} className="gap-2">
              {theme === 'dark' ? <><Moon className="h-4 w-4" />暗色</> : <><Sun className="h-4 w-4" />亮色</>}
            </Button>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">涨跌颜色</p>
              <p className="text-xs text-muted-foreground">
                {stockColorScheme === 'cn' ? '中国标准：红涨绿跌' : '国际标准：绿涨红跌'}
              </p>
            </div>
            <Button variant="outline" onClick={toggleColorScheme} className="gap-2">
              <span>{stockColorScheme === 'cn' ? '红涨绿跌' : '绿涨红跌'}</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 分析设置 */}
      <Card className="glass-card">
        <CardHeader><CardTitle className="text-sm">分析参数</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">默认研究深度</p>
              <p className="text-xs text-muted-foreground">1-5级，越高分析越全面但耗时更长</p>
            </div>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((d) => (
                <Button
                  key={d}
                  variant={researchDepth === d ? "default" : "outline"}
                  size="sm"
                  className={`w-8 h-8 p-0 font-mono ${researchDepth === d ? 'bg-[var(--brand-primary,#3737CC)] hover:bg-[var(--brand-primary-light,#4F4FE6)]' : ''}`}
                  onClick={() => setResearchDepth(d)}
                >
                  {d}
                </Button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="font-medium text-sm">语义记忆</p>
              <p className="text-xs text-muted-foreground">Agent是否参考历史分析记录</p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setEnableMemory(!enableMemory)}
              className={enableMemory ? 'text-[var(--brand-primary-light,#4F4FE6)] border-[var(--brand-primary,#3737CC)]/50 bg-[var(--brand-primary,#3737CC)]/10' : 'text-muted-foreground'}
            >
              {enableMemory ? '已启用' : '已关闭'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 系统信息 */}
      <Card className="glass-card">
        <CardHeader><CardTitle className="text-sm">系统信息</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Brain className="h-4 w-4 opacity-60" />
              <span>AI模型</span>
            </div>
            <span className="font-mono text-xs">DeepSeek / OpenAI GPT</span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Database className="h-4 w-4 opacity-60" />
              <span>数据源</span>
            </div>
            <span className="font-mono text-xs">akshare &middot; 东方财富</span>
          </div>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-muted-foreground">
              <Tag className="h-4 w-4 opacity-60" />
              <span>版本号</span>
            </div>
            <span className="font-mono text-xs">StockAnal v1.0</span>
          </div>
          <div className="flex justify-between text-muted-foreground"><span>Agent数量</span><span>13个</span></div>
          <div className="flex justify-between text-muted-foreground"><span>技术栈</span><span>Next.js + Flask + LangGraph</span></div>
          <div className="pt-2 border-t border-foreground/[0.06] dark:border-white/[0.06]">
            <Button
              variant="outline"
              size="sm"
              className="w-full gap-2 text-[#FF8767] border-[#FF8767]/30 hover:bg-[#FF8767]/10 hover:border-[#FF8767]/50"
              onClick={handleClearCache}
            >
              <Trash2 className="h-3.5 w-3.5" />
              清除缓存
            </Button>
          </div>
        </CardContent>
      </Card>
      {/* 关于 */}
      <Card className="glass-card">
        <CardHeader><CardTitle className="text-sm">关于</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-muted-foreground">
            AI-Native 智能金融分析平台，基于多Agent协作系统，提供专业级投资决策支持。
          </p>
          <div className="flex flex-wrap gap-1.5 mt-2">
            {['Next.js', 'React', 'TradingView', 'LangGraph', 'Flask', 'OpenAI'].map(tech => (
              <span key={tech} className="px-2 py-0.5 bg-[var(--glass-bg)] border border-[var(--glass-border)] rounded-full text-[10px]">{tech}</span>
            ))}
          </div>
          <p className="text-[10px] text-muted-foreground/50 mt-2">
            AI生成的内容仅供参考，不构成投资建议。投资有风险，入市需谨慎。
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
