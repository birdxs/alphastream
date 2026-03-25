// Input: 全局主题状态（theme-store）
// Output: 设置页面，含主题切换、涨跌颜色、系统信息
// Pos: /settings路由页面
// 一旦我被修改，请更新我的头部注释，以及所属文件夹的md。

"use client";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useThemeStore } from "@/lib/stores/theme-store";
import { useSettingsStore } from "@/lib/stores/settings-store";
import { Sun, Moon } from "lucide-react";

export default function SettingsPage() {
  const { theme, toggleTheme, stockColorScheme, toggleColorScheme } = useThemeStore();
  const { researchDepth, setResearchDepth, enableMemory, setEnableMemory } = useSettingsStore();

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">设置</h1>

      {/* 外观设置 */}
      <Card>
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
      <Card>
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
                  className="w-8 h-8 p-0 font-mono"
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
              className={enableMemory ? 'text-green-500 border-green-500/50' : 'text-muted-foreground'}
            >
              {enableMemory ? '已启用' : '已关闭'}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* 系统信息 */}
      <Card>
        <CardHeader><CardTitle className="text-sm">系统信息</CardTitle></CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <div className="flex justify-between"><span>前端版本</span><span className="font-mono">v2.3.0-ai-native</span></div>
          <div className="flex justify-between"><span>后端版本</span><span className="font-mono">v2.3.0</span></div>
          <div className="flex justify-between"><span>Agent数量</span><span>13个</span></div>
          <div className="flex justify-between"><span>技术栈</span><span>Next.js + Flask + LangGraph</span></div>
        </CardContent>
      </Card>
    </div>
  );
}
