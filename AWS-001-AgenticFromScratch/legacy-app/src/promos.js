// promo master - synced from marketing sheet (manual!!)
// typ: P=pct F=fixed B=bundle
// wk: 0 any 1 wkend 2 wkday
// chn: 1 dine 2 take 4 drive 8 dlv
// st: A / S
module.exports.PROMOS = [
  { pcd: 'WKND20', ds: 'Weekend 20% off', typ: 'P', val: 20, mx: 1000, mn: 0, wk: 1, chn: 3, brs: '*', sd: 20260901, ed: 20261231, hr: null, st: 'A' },
  { pcd: 'LUNCH5', ds: '$5 off weekday lunch', typ: 'F', val: 500, mx: 0, mn: 2500, wk: 2, chn: 15, brs: '*', sd: 20260801, ed: 20261130, hr: '11-14', st: 'A' },
  { pcd: 'DLV15', ds: 'Delivery 15% off', typ: 'P', val: 15, mx: 800, mn: 2000, wk: 0, chn: 8, brs: '1,2,3,12', sd: 20260915, ed: 20261031, hr: null, st: 'A' },
  { pcd: 'B1G1TART', ds: 'Buy 1 egg tart free 1', typ: 'B', bi: 19, bq: 1, gi: 19, gq: 1, mn: 0, wk: 0, chn: 15, brs: '*', sd: 20261001, ed: 20261015, hr: null, st: 'A' },
  { pcd: 'WINGS2', ds: '2 wings free fries', typ: 'B', bi: 3, bq: 2, gi: 9, gq: 1, mn: 0, wk: 0, chn: 15, brs: '*', sd: 20260901, ed: 20261231, hr: null, st: 'A' },
  { pcd: 'BAYSIDE10', ds: 'Bayside $10 off', typ: 'F', val: 1000, mx: 0, mn: 5000, wk: 0, chn: 15, brs: '12', sd: 20260901, ed: 20261231, hr: null, st: 'A' },
  { pcd: 'OLDSUMMER', ds: 'Summer 10%', typ: 'P', val: 10, mx: 500, mn: 0, wk: 0, chn: 15, brs: '*', sd: 20260601, ed: 20260831, hr: null, st: 'A' },
  { pcd: 'STAFF50', ds: 'staff meal', typ: 'P', val: 50, mx: 2000, mn: 0, wk: 0, chn: 3, brs: '*', sd: 20250101, ed: 20271231, hr: null, st: 'S' },
];

// prices in SEN. keep in sync w/ POS (TODO automate)
module.exports.PRC = {
  1: 1290, 2: 1340, 3: 1590, 4: 1150, 5: 990, 6: 1390, 7: 1190, 8: 1090, 9: 490, 10: 650,
  11: 390, 12: 390, 13: 450, 14: 390, 15: 490, 16: 450, 17: 250, 18: 490, 19: 350, 20: 420,
};
