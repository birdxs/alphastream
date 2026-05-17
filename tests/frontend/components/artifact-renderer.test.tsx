// Input: ArtifactRenderer 组件 — 多种 artifact_type 分支
// Output: vitest 用例 — 验证 5+ 已知类型 + unknown 兜底不白屏
// Pos: tests/frontend/components/ — FE-03 关键组件测试

import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import React from 'react';

// 替换 ArtifactCard 容器（其内部动态 import html2canvas，jsdom 无法解析）
vi.mock('@/components/artifacts/artifact-card', () => ({
  ArtifactCard: ({ title, children }: { title?: string; children?: React.ReactNode }) => (
    <div data-testid="artifact-card">
      <div>{title}</div>
      <div>{children}</div>
    </div>
  ),
}));
// 避免 next/dynamic 加载真实图表（jsdom 无 echarts canvas）
vi.mock('next/dynamic', () => ({
  default: () => () => <div data-testid="dynamic-stub" />,
}));

import { ArtifactRenderer } from '@/components/chat/artifact-renderer';
import type { Artifact } from '@/lib/types';

const make = (type: string, title: string, data: Record<string, unknown> = {}): Artifact =>
  ({
    type: 'artifact',
    artifact_type: type as Artifact['artifact_type'],
    title,
    data,
  });

describe('ArtifactRenderer 组件', () => {
  afterEach(() => cleanup());

  it('decision_card 命中渲染', () => {
    const art = make('decision_card', '投资决策', {
      action: 'BUY',
      confidence: 0.8,
      reasoning: '基本面良好',
      risk_score: 30,
    });
    render(<ArtifactRenderer artifact={art} />);
    expect(screen.getByText('投资决策')).toBeTruthy();
  });

  it('news_feed 命中渲染', () => {
    const art = make('news_feed', '新闻列表', {
      news: [
        { title: '利好新闻', source: '财联社', published_at: '2026-05-17', sentiment: 'positive' },
      ],
    });
    render(<ArtifactRenderer artifact={art} />);
    expect(screen.getByText('新闻列表')).toBeTruthy();
  });

  it('risk_gauge 命中渲染', () => {
    const art = make('risk_gauge', '风险评分', { score: 45, level: 'medium' });
    render(<ArtifactRenderer artifact={art} />);
    expect(screen.getByText('风险评分')).toBeTruthy();
  });

  it('candlestick_chart 命中渲染', () => {
    const art = make('candlestick_chart', 'K线图', {
      ohlc: [{ date: '2026-05-17', open: 10, high: 11, low: 9, close: 10.5 }],
    });
    render(<ArtifactRenderer artifact={art} />);
    expect(screen.getByText('K线图')).toBeTruthy();
  });

  it('search_results 命中渲染', () => {
    const art = make('search_results', '搜索结果', {
      results: [{ title: 'r1', url: 'http://x', snippet: 's' }],
    });
    render(<ArtifactRenderer artifact={art} />);
    expect(screen.getByText('搜索结果')).toBeTruthy();
  });

  it('unknown artifact_type 兜底 — 不白屏', () => {
    const art = make('this_type_does_not_exist', '未知类型');
    const { container } = render(<ArtifactRenderer artifact={art} />);
    // 关键：容器非空 + 不抛错
    expect(container.firstChild).toBeTruthy();
    expect(container.textContent).not.toBe('');
  });
});
