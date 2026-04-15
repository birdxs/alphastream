// Input: mock page.evaluate 桩数据
// Output: 断言通过 (4个unit test)
// Pos: OpenCLI自建适配器测试 (雪球讨论) - node --test 可运行
// 一旦修改请更新 clis/README.md

'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const adapter = require('./discuss');

function makeMockCtx({ evalResult = [], throwOnGoto = false } = {}) {
  return {
    args: { symbol: 'SZ000001', limit: 30 },
    logger: { info: () => {}, warn: () => {} },
    page: {
      goto: async () => {
        if (throwOnGoto) throw new Error('network');
      },
      waitForSelector: async () => true,
      evaluate: async (_fn, _n) => evalResult,
    },
  };
}

test('xueqiu/discuss: 元信息契约 (name/strategy/args)', () => {
  assert.equal(adapter.name, 'xueqiu/discuss');
  assert.equal(adapter.strategy, 'COOKIE');
  assert.ok(Array.isArray(adapter.args));
  const symbolArg = adapter.args.find((a) => a.name === 'symbol');
  assert.ok(symbolArg && symbolArg.required === true);
});

test('xueqiu/discuss: mock 返回结构化 list', async () => {
  const ctx = makeMockCtx({
    evalResult: [
      { user: 'Alice', time: '01-01 10:00', content: 'hello', likes: 3, comments: 1, reposts: 0 },
      { user: 'Bob', time: '01-01 11:00', content: 'hi', likes: 5, comments: 2, reposts: 1 },
    ],
  });
  const out = await adapter.run(ctx);
  assert.equal(out.length, 2);
  assert.equal(out[0].user, 'Alice');
  assert.equal(out[1].likes, 5);
});

test('xueqiu/discuss: symbol 缺失应抛异常', async () => {
  const ctx = makeMockCtx();
  ctx.args = { limit: 10 };
  await assert.rejects(() => adapter.run(ctx), /symbol/);
});

test('xueqiu/discuss: 空 evaluate 结果返回空数组', async () => {
  const ctx = makeMockCtx({ evalResult: [] });
  const out = await adapter.run(ctx);
  assert.deepEqual(out, []);
});
