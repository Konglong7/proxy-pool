// spys_eval3.js: run whole row scripts verbatim
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const html = fs.readFileSync(path.join(__dirname, 'raw', 'spys.one.html'), 'utf-8');

const scriptRe = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;
const scripts = [];
let m;
while ((m = scriptRe.exec(html)) !== null) scripts.push(m[1]);
let packIdx = scripts.findIndex(s => s.includes('eval(function') && s.includes('split'));

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
  try { vm.runInContext(scripts[i], ctx, { timeout: 2000 }); } catch (e) { console.log('pre', i, String(e.message).slice(0,60)); }
}
try { vm.runInContext(scripts[packIdx], ctx, { timeout: 4000 }); console.log('packer OK'); }
catch (e) { console.log('packer ERR', String(e.message).slice(0,120)); }

// iterate rows: capture consecutive td pairs ip & port script
const rowRe = /<font class=spy14>(\d{1,3}(?:\.\d{1,3}){3})<script>(document\.write\([^)]+\)+)<\/script><\/font><\/td><td[^>]*><font class=spy1>(HTTP(?:(?:<font class=spy14>S<\/font>)?))/g;
const results = [];
while ((m = rowRe.exec(html)) !== null) {
  const ip = m[1], scriptText = m[2], typed = m[3];
  const before = out.length;
  try { vm.runInContext(scriptText, ctx, { timeout: 1000 }); }
  catch (e) { console.log('row err', ip, String(e.message).slice(0,60)); }
  const port = String(out.slice(before).join('')).replace(/^:/, '');
  results.push({ ip, port, type: typed.includes('S') ? 'HTTPS' : 'HTTP' });
}
console.log('RESULTS:', JSON.stringify(results, null, 0));
fs.writeFileSync(path.join(__dirname, 'out_spys.json'), JSON.stringify(results, null, 1));
console.log('count:', results.length);
const invalid = results.filter(r => !/^\d{1,5}$/.test(r.port));
console.log('invalid ports:', invalid);

// also collect the "raw ip" list for verification
const ips = [...html.matchAll(/\d{1,3}(?:\.\d{1,3}){3}/g)].map(x => x[0]);
console.log('total ip-like in html:', ips.length, 'unique:', new Set(ips).size);