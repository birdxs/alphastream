// Input: mock page.evaluate 桩数据
// Output: 断言通过 (4个unit test)
// Pos: OpenCLI自建适配器测试 (东方财富股吧) - node --test 可运行
// 一旦修改请更新 clis/README.md

'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const adapter = require('./guba');

function makeMockCtx({ evalResults = [[]] } = {}) {
  let callIdx = 0;
  return {
    args: { code: '600519', pages: 1 },
    logger: { info: () => {} },
    page: {
      goto: async () => {},
      waitForSelector: async () => true,
      evaluate: async () => {
        const r = evalResults[Math.min(callIdx, evalResults.length - 1)];
        callIdx += 1;
        return r;
      },
    },
  };
}

test('eastmoney/guba: 元信息契约', () => {
  assert.equal(adapter.name, 'eastmoney/guba');
  assert.equal(adapter.strategy, 'COOKIE');
  const codeArg = adapter.args.find((a) => a.name === 'code');
  assert.ok(codeArg && codeArg.required);
});

test('eastmoney/guba: 单页解析附带 rank 递增', async () => {
  const ctx = makeMockCtx({
    evalResults: [[
      { title: '帖子A', author: 'U1', time: '04-15 10:00', reads: 123, replies: 4, url: 'https://x' },
      { title: '帖子B', author: 'U2', time: '04-15 11:00', reads: 200, replies: 9, url: 'https://y' },
    ]],
  });
  const out = await adapter.run(ctx);
  assert.equal(out.length, 2);
  assert.equal(out[0].rank, 1);
  assert.equal(out[1].rank, 2);
  assert.equal(out[0].title, '帖子A');
});

test('eastmoney/guba: 非法 code 抛异常', async () => {
  const ctx = makeMockCtx();
  ctx.args = { code: 'ABC', pages: 1 };
  await assert.rejects(() => adapter.run(ctx), /6位数字/);
});

test('eastmoney/guba: 多页聚合 rank 连续', async () => {
  const ctx = makeMockCtx({
    evalResults: [
      [{ title: 'A', author: 'u', time: 't', reads: 1, replies: 0, url: '/1' }],
      [{ title: 'B', author: 'u', time: 't', reads: 2, replies: 1, url: '/2' }],
    ],
  });
  ctx.args = { code: '600519', pages: 2 };
  const out = await adapter.run(ctx);
  assert.equal(out.length, 2);
  assert.equal(out[0].rank, 1);
  assert.equal(out[1].rank, 2);
});
