// promo svc v1.3
const http = require('http');
const url = require('url');
const { PROMOS, PRC } = require('./promos');

const TKN = process.env.SVC_TKN || 'legacy-dev-token';
const PORT = process.env.PORT || 8081;

function nw() {
  // FAKE_NOW for uat
  return process.env.FAKE_NOW ? new Date(process.env.FAKE_NOW) : new Date();
}

function ymd(d) {
  return d.getFullYear() * 10000 + (d.getMonth() + 1) * 100 + d.getDate();
}

function out(res, code, body) {
  res.writeHead(code, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

function brOk(p, br) {
  if (p.brs === '*') return true;
  return p.brs.split(',').map(Number).indexOf(Number(br)) >= 0;
}

function actv(p, d) {
  var t = ymd(d);
  if (p.st !== 'A') return false;
  if (t < p.sd || t > p.ed) return false;
  var dw = d.getDay();
  var we = dw === 0 || dw === 6;
  if (p.wk === 1 && !we) return false;
  if (p.wk === 2 && we) return false;
  if (p.hr) {
    var h = p.hr.split('-');
    if (d.getHours() < Number(h[0]) || d.getHours() >= Number(h[1])) return false;
  }
  return true;
}

// redemptions (normally from rdm table)
function rdmFor(pcd, br, d) {
  var s = 0;
  for (var i = 0; i < pcd.length; i++) s += pcd.charCodeAt(i);
  return (s * 7 + br * 13 + d) % 37;
}

function pub(p) {
  // dont expose internal fields
  var o = Object.assign({}, p);
  delete o.st;
  return o;
}

function lst(q, res) {
  var br = Number(q.br);
  if (!br) return out(res, 400, { rc: 'E03', msg: 'br req' });
  var d = nw();
  var r = PROMOS.filter(function (p) { return brOk(p, br); });
  if (q.act === '1') r = r.filter(function (p) { return actv(p, d); });
  out(res, 200, { rc: '00', dt: r.map(pub) });
}

function dtl(pcd, res) {
  var p = PROMOS.find(function (x) { return x.pcd === String(pcd).toUpperCase(); });
  if (!p || p.st === 'S') return out(res, 404, { rc: 'E02', msg: 'nf' });
  out(res, 200, { rc: '00', dt: Object.assign(pub(p), { live: actv(p, nw()) }) });
}

function chk(b, res) {
  var p = PROMOS.find(function (x) { return x.pcd === String(b.pcd || '').toUpperCase(); });
  if (!p || p.st === 'S') return out(res, 404, { rc: 'E02', msg: 'nf' });
  if (!b.br || !Array.isArray(b.itms) || !b.itms.length) return out(res, 400, { rc: 'E03', msg: 'br/itms req' });
  var chn = Number(b.chn || 1);
  var no = function (rsn) { out(res, 200, { rc: 'E04', dt: { ok: false, dsc: 0, rsn: rsn } }); };

  if (!brOk(p, b.br)) return no('BR');
  if (!actv(p, nw())) return no('DT');
  if ((p.chn & chn) === 0) return no('CH');

  var tot = 0;
  var cnt = {};
  for (var i = 0; i < b.itms.length; i++) {
    var it = b.itms[i];
    if (!PRC[it.id]) return out(res, 400, { rc: 'E03', msg: 'bad itm ' + it.id });
    tot += PRC[it.id] * (it.q || 1);
    cnt[it.id] = (cnt[it.id] || 0) + (it.q || 1);
  }
  if (tot < p.mn) return no('MN');

  var dsc = 0;
  if (p.typ === 'P') {
    dsc = Math.floor(tot * p.val / 100);
    if (p.mx && dsc > p.mx) dsc = p.mx;
  } else if (p.typ === 'F') {
    dsc = Math.min(p.val, tot);
  } else if (p.typ === 'B') {
    var sets = Math.floor((cnt[p.bi] || 0) / p.bq);
    if (p.bi === p.gi) sets = Math.floor((cnt[p.bi] || 0) / (p.bq + p.gq));
    var free = Math.min(sets * p.gq, cnt[p.gi] || 0);
    if (!free) return no('BQ');
    dsc = free * PRC[p.gi];
  }
  out(res, 200, { rc: '00', dt: { ok: true, dsc: dsc, tot: tot, net: tot - dsc } });
}

function rpt(q, res) {
  var br = Number(q.br);
  var d1 = Number(q.dt1), d2 = Number(q.dt2);
  if (!br || !d1 || !d2 || d2 < d1) return out(res, 400, { rc: 'E03', msg: 'br/dt1/dt2' });
  var r = [];
  PROMOS.filter(function (p) { return brOk(p, br) && p.st === 'A'; }).forEach(function (p) {
    var n = 0;
    var s = Math.max(d1, p.sd), e = Math.min(d2, p.ed);
    for (var dd = s; dd <= e; dd++) {
      if (dd % 100 > 31 || dd % 100 === 0) continue; // lazy date loop
      n += rdmFor(p.pcd, br, dd % 100);
    }
    if (n) r.push({ pcd: p.pcd, rdm: n });
  });
  out(res, 200, { rc: '00', dt: r });
}

const srv = http.createServer(function (req, res) {
  var u = url.parse(req.url, true);
  if (u.pathname === '/hc') return out(res, 200, { ok: 1 });
  if (req.headers['x-svc-tkn'] !== TKN) return out(res, 401, { rc: 'E01', msg: 'unauth' });

  if (req.method === 'GET' && u.pathname === '/api/v1/promo/lst') return lst(u.query, res);
  if (req.method === 'GET' && u.pathname.indexOf('/api/v1/promo/dtl/') === 0) return dtl(u.pathname.split('/').pop(), res);
  if (req.method === 'GET' && u.pathname === '/api/v1/promo/rpt') return rpt(u.query, res);
  if (req.method === 'POST' && u.pathname === '/api/v1/promo/chk') {
    var buf = '';
    req.on('data', function (c) { buf += c; });
    req.on('end', function () {
      try { chk(JSON.parse(buf || '{}'), res); } catch (e) { out(res, 400, { rc: 'E03', msg: 'json' }); }
    });
    return;
  }
  out(res, 404, { rc: 'E02', msg: 'nf' });
});

if (require.main === module) {
  srv.listen(PORT, function () { console.log('promo svc on ' + PORT); });
}
module.exports = srv;
