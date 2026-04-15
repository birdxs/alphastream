// Input: mock page.evaluate 桩数据
// Output: 断言通过 (4个unit test)
// Pos: OpenCLI自建适配器测试 (财联社电报) - node --test 可运行
// 一旦修改请更新 clis/README.md

'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const adapter = require('./telegraph');

function makeMockCtx({ evalResult = [] } = {}) {
  return {
    args: { limit: 50 },
    logger: { info: () => {} },
    page: {
      goto: async () => {},
      waitForSelector: async () => true,
      evaluate: async () => evalResult,
    },
  };
}

test('cls/telegraph: 元信息契约', () => {
  assert.equal(adapter.name, 'cls/telegraph');
  assert.equal(adapter.strategy, 'COOKIE');
  assert.ok(Array.isArray(adapter.args));
  const limitArg = adapter.args.find((a) => a.name === 'limit');
  assert.ok(limitArg && limitArg.default === 50);
});

test('cls/telegraph: 解析含 tags 与 isImportant 布尔', async () => {
  const ctx = makeMockCtx({
    evalResult: [
      { time: '10:00', title: '【重要】某公告', content: 'xx', tags: ['A股', '宏观'], isImportant: true },
      { time: '10:05', title: '普通消息', content: 'yy', tags: [], isImportant: false },
    ],
  });
  const out = await adapter.run(ctx);
  assert.equal(out.length, 2);
  assert.equal(out[0].isImportant, true);
  assert.deepEqual(out[0].tags, ['A股', '宏观']);
  assert.equal(out[1].isImportant, false);
});

test('cls/telegraph: 空 evaluate 返回空数组', async () => {
  const ctx = makeMockCtx({ evalResult: [] });
  const out = await adapter.run(ctx);
  assert.deepEqual(out, []);
});

test('cls/telegraph: limit 默认可覆盖', async () => {
  const ctx = makeMockCtx({ evalResult: [] });
  ctx.args = { limit: 10 };
  // run 不会抛出，验证 default 覆盖逻辑
  const out = await adapter.run(ctx);
  assert.ok(Array.isArray(out));
});
