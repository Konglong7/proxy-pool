// spys_eval.js v2: locate packer by content, run it, then evaluate row port scripts.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const html = fs.readFileSync(path.join(__dirname, 'raw', 'spys.one.html'), 'utf-8');

// extract all inline <script> tags in order (no src)
const scriptRe = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;
const scripts = [];
let m;
while ((m = scriptRe.exec(html)) !== null) {
  scripts.push(m[1]);
}
console.log('total inline scripts:', scripts.length);
console.log('script 2 (packer) head:', scripts[2].slice(0, 150));

// find each row's ip + port expression
const rowRe = /<font class=spy14>(\d{1,3}(?:\.\d{1,3}){3})<script>document\.write\(":"\+([^<]+?)\)<\/script><\/font><\/td><td[^>]*><font class=spy1>(HTTP(?:(?:<font class=spy14>S<\/font>)?))(?=<\/font>| ?)/g;
let rm;
const rows = [];
while ((rm = rowRe.exec(html)) !== null) {
  rows.push({ ip: rm[1], expr: rm[2], http: rm[3] });
}
console.log('rows found:', rows.length);

// Build sandbox: fake document.write collecting, atob, String, etc.
const out = [];
const ctx = {
  atob: (s) => Buffer.from(s, 'base64').toString('latin1'),
  String,
  document: {
    write: (x) => out.push(String(x)),
    createElement: () => ({ set innerHTML(v) {}, appendChild() {}, style: {}, height: 1, width: 1, position: '', top: '', left: '', border: '', visibility: '' }),
    body: null,
    readyState: 'loading',
    addEventListener: () => {},
    getElementsByTagName: () => [],
    createTextNode: () => ({})
  },
  window: null,
  console
};
ctx.window = ctx;
vm.createContext(ctx);

// 1) run packer (script index 1 = gtag, 2 = packer, rows from 3)
try {
  vm.runInContext(scripts[2], ctx, { timeout: 2000 });
  console.log('packer executed OK');
} catch (e) {
  console.log('packer ERROR:', e.message);
}

// 2) run each row script, capture writes
const results = [];
for (const r of rows) {
  const before = out.length;
  try {
    vm.runInContext('document.write(":"+(' + r.expr + '))', ctx, { timeout: 1000 });
  } catch (e) {
    console.log('row eval error', r.ip, e.message.slice(0, 80));
  }
  const wrote = out.slice(before);
  // the write appends ":"+port decoded
  const port = wrote.map(Number).filter(n => !isNaN(n)).join('');
  results.push({ ip: r.ip, port, type: r.http.includes('S') ? 'HTTPS' : 'HTTP' });
}
console.log(JSON.stringify(results.slice(0, 8), null, 1));

// test which row vars are known
const testExprs = [
  'Six3TwoSix', 'Three6Three', 'SixZeroFiveEight', 'SevenThreeEight',
  'EightThreeFourNine', 'TwoOneFive', 'FiveThreeZeroSeven', 'Three2Six',
  'Three0ThreeFive', 'SixTwoNine', 'Three0One', 'Nine5EightTwo',
  'Three3Zero', 'FourFiveSevenFour', 'Three4Seven', 'FiveFiveNineThree',
  'Seven7Two', 'NineOneSixZero', 'FourOneFour', 'FourFourOneOne'
];
for (const t of testExprs) {
  try {
    const val = vm.runInContext(t, ctx);
    console.log(t, '=', val);
  } catch (e) {
    console.log(t, 'UNDEFINED');
  }
}