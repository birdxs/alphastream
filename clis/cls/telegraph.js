// Input: CLI参数 (limit 默认50)
// Output: 结构化JSON数组 [{time, title, content, tags, isImportant}]
// Pos: OpenCLI自建适配器 (财联社电报流) - 供 app/adapters/opencli_bridge.py 调用
// 一旦修改请更新 clis/README.md
//
// 权威源（2026-04-15 12:30 +08:00 检索）：
// - https://www.cls.cn/telegraph (电报流页面 DOM: .telegraph-content-box)
// - https://github.com/jackwener/OpenCLI/pull/1025 (hot-rank 模板)
// - https://github.com/jackwener/OpenCLI (目录约定)
//
// [NEW-FILE:#20260415-15]

'use strict';

module.exports = {
  name: 'cls/telegraph',
  description: '财联社电报实时流抓取 - 输出 time/title/content/tags/isImportant',
  strategy: 'COOKIE',
  args: [
    { name: 'limit', required: false, default: 50, description: '返回条数上限' },
  ],

  async run(ctx) {
    const { page, logger, args } = ctx;
    const limit = parseInt(args.limit, 10) || 50;

    const url = 'https://www.cls.cn/telegraph';
    logger && logger.info(`[cls/telegraph] navigate -> ${url}`);

    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
    await page.waitForSelector('.telegraph-content-box, .telegraph-list, .b-time', { timeout: 15000 });

    const items = await page.evaluate((maxN) => {
      const nodes = document.querySelectorAll(
        '.telegraph-content-box, .telegraph-list-item, .subject-interest-list .item'
      );
      const out = [];
      for (let i = 0; i < nodes.length && out.length < maxN; i++) {
        const n = nodes[i];
        const time = (n.querySelector('.telegraph-time-box, .b-time, .time') || {}).innerText || '';
        const titleEl = n.querySelector('strong, .c-de0422, .telegraph-content-title');
        const title = titleEl ? (titleEl.innerText || '').trim() : '';
        const contentEl = n.querySelector('.telegraph-content, .content, p');
        const content = contentEl ? (contentEl.innerText || '').trim() : '';
        const tagNodes = n.querySelectorAll('.label-item, .telegraph-label, a.label');
        const tags = Array.from(tagNodes).map((t) => (t.innerText || '').trim()).filter(Boolean);
        const isImportant = !!n.querySelector('.c-de0422, .red-text, [class*="important"]') ||
          /【重要】|重磅|突发/.test(title + content);
        out.push({ time: time.trim(), title, content, tags, isImportant });
      }
      return out;
    }, limit);

    logger && logger.info(`[cls/telegraph] parsed=${items.length}`);
    return items;
  },
};
