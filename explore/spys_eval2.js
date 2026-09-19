// spys_eval2.js: correct extraction of spys.one port obfuscation
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const html = fs.readFileSync(path.join(__dirname, 'raw', 'spys.one.html'), 'utf-8');

const scriptRe = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;
const scripts = [];
let m;
while ((m = scriptRe.exec(html)) !== null) scripts.push(m[1]);
console.log('total inline scripts:', scripts.length);

let packIdx = scripts.findIndex(s => s.includes('eval(function') && s.includes('split'));
console.log('packer index:', packIdx);

const out = [];
const ctx = {
  atob: (s) => Buffer.from(s, 'base64').toString('latin1'),
  String, Number, parseInt, Math, isNaN,
  document: {
    write: (x) => out.push(String(x)),
    createElement: () => ({ set innerHTML(v) {}, appendChild() {}, style: {}, height: 1, width: 1 }),
    body: null, readyState: 'loading',
    addEventListener: () => {}, getElementsByTagName: () => [], getElementById: () => null
  },
  window: null, console
};
ctx.window = ctx;
vm.createContext(ctx);

for (let i = 0; i < packIdx; i++) {
  try { vm.runInContext(scripts[i], ctx, { timeout: 2000 }); } catch (e) { console.log('pre-script', i, 'ERR', e.message.slice(0, 80)); }
}
try {
  vm.runInContext(scripts[packIdx], ctx, { timeout: 4000 });
  console.log('packer executed OK');
} catch (e) {
  console.log('packer ERROR:', String(e.message).slice(0, 150));
}

const testExprs = ['Six3TwoSix','Three6Three','SixZeroFiveEight','SevenThreeEight',
  'EightThreeFourNine','TwoOneFive','FiveThreeZeroSeven','Three2Six','Three0ThreeFive',
  'SixTwoNine','Three0One','Nine5EightTwo','Three3Zero','FourFiveSevenFour',
  'Three4Seven','FiveFiveNineThree','Seven7Two','NineOneSixZero','FourOneFour','FourFourOneOne'];
const known = {};
for (const t of testExprs) {
  try { known[t] = vm.runInContext(t, ctx); } catch (e) { known[t] = 'UNDEF'; }
}
console.log('known vars:', JSON.stringify(known));

const rowRe = /<font class=spy14>(\d{1,3}(?:\.\d{1,3}){3})<script>document\.write\(":"\+([^<]+?)\)<\/script><\/font><\/td><td[^>]*><font class=spy1>(HTTP(?:(?:<font class=spy14>S<\/font>)?))/g;
const results = [];
while ((m = rowRe.exec(html)) !== null) {
  const ip = m[1], expr = m[2], typed = m[3];
  const before = out.length;
  try { vm.runInContext('document.write(":"+(' + expr + '))', ctx, { timeout: 1000 }); }
  catch (e) { console.log('row eval error', ip, String(e.message).slice(0, 60)); }
  const port = String(out.slice(before).join('')).replace(/^:/, '');
  results.push({ ip, port, type: typed.includes('S') ? 'HTTPS' : 'HTTP' });
}
console.log('RESULTS:');
console.log(JSON.stringify(results, null, 0));
fs.writeFileSync(path.join(__dirname, 'out_spys.json'), JSON.stringify({ results, known }, null, 1));