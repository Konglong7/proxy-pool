// js_render.js <input.html> <output.json> : run inline scripts with DOM shim,
// capture document.write outputs per script index.
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const infile = process.argv[2];
const outfile = process.argv[3];
const html = fs.readFileSync(path.join(__dirname, infile), 'utf-8');

const scriptRe = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/gi;
const scripts = [];
let m;
while ((m = scriptRe.exec(html)) !== null) scripts.push(m[1]);

const allOut = [];
const ctx = {
  atob: (s) => Buffer.from(s, 'base64').toString('latin1'),
  String, Number, parseInt, parseFloat, Math, isNaN, escape, unescape, decodeURIComponent, encodeURIComponent,
  document: {
    write: (x) => { allOut.push(String(x)); },
    writeln: (x) => { allOut.push(String(x)); },
    createElement: () => ({ set innerHTML(v) {}, appendChild() {}, style: {}, height: 1, width: 1, src: '', type: '' }),
    createTextNode: (t) => ({}),
    body: null, readyState: 'loading', cookie: '',
    addEventListener: () => {}, removeEventListener: () => {},
    getElementsByTagName: () => [], getElementById: () => null,
    querySelectorAll: () => [], querySelector: () => null,
    documentElement: { style: {} }, location: { href: '' }
  },
  window: null,
  navigator: { userAgent: 'Mozilla/5.0' },
  location: { href: '' },
  console: { log(){}, warn(){}, error(){} },
  setTimeout: () => 0, clearTimeout: () => {}, setInterval: () => 0, clearInterval: () => {}
};
ctx.window = ctx;
ctx.self = ctx;
vm.createContext(ctx);

const perScript = [];
for (let i = 0; i < scripts.length; i++) {
  const before = allOut.length;
  try {
    vm.runInContext(scripts[i], ctx, { timeout: 3000 });
  } catch (e) {
    perScript.push({ index: i, error: String(e.message).slice(0, 200), outputs: allOut.slice(before) });
    continue;
  }
  perScript.push({ index: i, outputs: allOut.slice(before), error: null });
}

fs.writeFileSync(path.join(__dirname, outfile), JSON.stringify({ perScript, totalOut: allOut.length }, null, 1));
console.log('scripts:', scripts.length, 'total writes:', allOut.length, '->', outfile);