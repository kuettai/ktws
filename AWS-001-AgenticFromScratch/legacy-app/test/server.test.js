// Instructor smoke tests. Not shown to participants during Exercise B.
process.env.FAKE_NOW = '2026-10-03T12:30:00'; // Saturday lunchtime, server local time
process.env.SVC_TKN = 't';

const test = require('node:test');
const assert = require('node:assert');
const srv = require('../src/server');

let base;
test.before(() => new Promise((ok) => srv.listen(0, () => { base = `http://127.0.0.1:${srv.address().port}`; ok(); })));
test.after(() => srv.close());

const get = (p, tkn = 't') => fetch(base + p, { headers: { 'x-svc-tkn': tkn } }).then(async (r) => [r.status, await r.json()]);
const chk = (body) => fetch(base + '/api/v1/promo/chk', {
  method: 'POST', headers: { 'x-svc-tkn': 't' }, body: JSON.stringify(body),
}).then((r) => r.json());

test('auth', async () => {
  assert.deepStrictEqual((await get('/api/v1/promo/lst?br=12', 'bad'))[1].rc, 'E01');
});

test('active list for branch 12 on a Saturday excludes weekday + expired + suspended', async () => {
  const [, body] = await get('/api/v1/promo/lst?br=12&act=1');
  const codes = body.dt.map((p) => p.pcd).sort();
  assert.deepStrictEqual(codes, ['B1G1TART', 'BAYSIDE10', 'DLV15', 'WINGS2', 'WKND20']);
});

test('percent capped at mx (cents)', async () => {
  const r = await chk({ pcd: 'wknd20', br: 12, chn: 1, itms: [{ id: 3, q: 4 }] }); // 6360 cents, 20% = 1272, cap 1000
  assert.deepStrictEqual(r.dt, { ok: true, dsc: 1000, tot: 6360, net: 5360 });
});

test('channel bitmask', async () => {
  const r = await chk({ pcd: 'WKND20', br: 12, chn: 8, itms: [{ id: 1, q: 1 }] });
  assert.strictEqual(r.dt.rsn, 'CH');
});

test('bundle same item', async () => {
  const r = await chk({ pcd: 'B1G1TART', br: 5, itms: [{ id: 19, q: 2 }] });
  assert.strictEqual(r.dt.dsc, 350);
});

test('suspended promo hidden', async () => {
  assert.strictEqual((await get('/api/v1/promo/dtl/STAFF50'))[0], 404);
});

test('report', async () => {
  const [, body] = await get('/api/v1/promo/rpt?br=12&dt1=20260901&dt2=20260930');
  assert.ok(body.dt.find((r) => r.pcd === 'BAYSIDE10').rdm > 0);
});
