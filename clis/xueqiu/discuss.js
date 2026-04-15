// Input: CLI参数 (symbol 如 SZ000001, limit 默认30)
// Output: 结构化JSON数组 [{user, time, content, likes, comments, reposts}]
// Pos: OpenCLI自建适配器 (雪球讨论流) - 供 app/adapters/opencli_bridge.py 调用
// 一旦修改请更新 clis/README.md
//
// 权威源（2026-04-15 12:30 +08:00 检索）：
// - https://github.com/jackwener/OpenCLI/pull/1025 (hot-rank adapter 模板 Strategy.COOKIE)
// - https://github.com/jackwener/OpenCLI (主仓 clis/<site>/<action>.js 目录约定)
// - https://xueqiu.com/S/SZ000001/TIMELINE (目标页面 DOM 结构)
//
// [NEW-FILE:#20260415-13]

'use strict';

module.exports = {
  name: 'xueqiu/discuss',
  description: '雪球个股讨论流抓取 (timeline) - 输出 user/time/content/likes/comments/reposts',
  strategy: 'COOKIE',
  args: [
    { name: 'symbol', required: true, example: 'SZ000001', description: '雪球股票代码(含交易所前缀)' },
    { name: 'limit', required: false, default: 30, description: '返回条数上限' },
  ],

  /**
   * @param {object} ctx - OpenCLI 注入 { page, logger, args }
   * @returns {Promise<Array<object>>}
   */
  async run(ctx) {
    const { page, logger, args } = ctx;
    const symbol = (args.symbol || '').trim();
    const limit = parseInt(args.limit, 10) || 30;

    if (!symbol) {
      throw new Error('xueqiu/discuss: symbol 参数必填 (如 SZ000001)');
    }

    const url = `https://xueqiu.com/S/${symbol}/TIMELINE`;
    logger && logger.info(`[xueqiu/discuss] navigate -> ${url}`);

    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
    // 等待讨论列表挂载 (雪球使用 .AnonymousHome_home__timeline .home__timeline__item)
    await page.waitForSelector('.home__timeline__item, .timeline__item, article', { timeout: 15000 });

    const items = await page.evaluate((maxN) => {
      const nodes = document.querySelectorAll(
        '.home__timeline__item, .timeline__item, article.home__timeline__item'
      );
      const out = [];
      const toInt = (s) => {
        if (!s) return 0;
        const m = String(s).match(/[\d.]+/);
        if (!m) return 0;
        const n = parseFloat(m[0]);
        return /万/.test(s) ? Math.round(n * 10000) : Math.round(n);
      };
      for (let i = 0; i < nodes.length && out.length < maxN; i++) {
        const n = nodes[i];
        const user = (n.querySelector('.home__timeline__item__nick, a.user-nickname') || {}).innerText || '';
        const time = (n.querySelector('.date-and-source, time, .timestamp') || {}).innerText || '';
        const content = (n.querySelector('.content, .home__timeline__item__detail__content') || {}).innerText || '';
        const likes = toInt((n.querySelector('[class*="like"], .like__count') || {}).innerText);
        const comments = toInt((n.querySelector('[class*="comment"], .comment__count') || {}).innerText);
        const reposts = toInt((n.querySelector('[class*="retweet"], [class*="repost"]') || {}).innerText);
        out.push({
          user: user.trim(),
          time: time.trim(),
          content: content.trim(),
          likes, comments, reposts,
        });
      }
      return out;
    }, limit);

    logger && logger.info(`[xueqiu/discuss] parsed=${items.length} symbol=${symbol}`);
    return items;
  },
};
