// Input: CLI参数 (code 如 600519, pages 默认1)
// Output: 结构化JSON数组 [{rank, title, author, time, reads, replies, url}]
// Pos: OpenCLI自建适配器 (东方财富股吧) - 供 app/adapters/opencli_bridge.py 调用
// 一旦修改请更新 clis/README.md
//
// 权威源（2026-04-15 12:30 +08:00 检索）：
// - https://github.com/jackwener/OpenCLI/pull/1025 (hot-rank adapter 参考)
// - https://guba.eastmoney.com/list,600519.html (股吧列表 DOM: table.default_list tr)
// - https://github.com/jackwener/OpenCLI (目录约定)
//
// [NEW-FILE:#20260415-14]

'use strict';

module.exports = {
  name: 'eastmoney/guba',
  description: '东方财富股吧帖子列表抓取 - 输出 rank/title/author/time/reads/replies/url',
  strategy: 'COOKIE',
  args: [
    { name: 'code', required: true, example: '600519', description: '6位A股代码' },
    { name: 'pages', required: false, default: 1, description: '抓取页数(每页约80条)' },
  ],

  async run(ctx) {
    const { page, logger, args } = ctx;
    const code = (args.code || '').trim();
    const pages = Math.max(1, parseInt(args.pages, 10) || 1);

    if (!code || !/^\d{6}$/.test(code)) {
      throw new Error('eastmoney/guba: code 参数必须是6位数字股票代码');
    }

    const all = [];
    let rank = 0;
    for (let p = 1; p <= pages; p++) {
      const url = p === 1
        ? `https://guba.eastmoney.com/list,${code}.html`
        : `https://guba.eastmoney.com/list,${code},f_${p}.html`;
      logger && logger.info(`[eastmoney/guba] navigate -> ${url}`);

      await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
      await page.waitForSelector('.default_list, table.default_list, .articleh', { timeout: 15000 });

      const rows = await page.evaluate(() => {
        const nodes = document.querySelectorAll('.articleh, table.default_list tr.articleh');
        const toInt = (s) => {
          if (!s) return 0;
          const m = String(s).match(/[\d.]+/);
          if (!m) return 0;
          const n = parseFloat(m[0]);
          return /万/.test(s) ? Math.round(n * 10000) : Math.round(n);
        };
        const out = [];
        nodes.forEach((n) => {
          const reads = toInt((n.querySelector('.l1, span.l1') || {}).innerText);
          const replies = toInt((n.querySelector('.l2, span.l2') || {}).innerText);
          const a = n.querySelector('.l3 a, span.l3 a');
          const title = a ? (a.innerText || '').trim() : '';
          const href = a ? a.getAttribute('href') || '' : '';
          const url = href.startsWith('http') ? href : `https://guba.eastmoney.com${href}`;
          const author = (n.querySelector('.l4 a, span.l4 a, span.l4') || {}).innerText || '';
          const time = (n.querySelector('.l5, span.l5') || {}).innerText || '';
          if (title) out.push({ title, author: author.trim(), time: time.trim(), reads, replies, url });
        });
        return out;
      });

      for (const r of rows) {
        rank += 1;
        all.push({ rank, ...r });
      }
    }

    logger && logger.info(`[eastmoney/guba] parsed=${all.length} code=${code} pages=${pages}`);
    return all;
  },
};
