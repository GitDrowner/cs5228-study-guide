// Render a JSON array of TeX strings (stdin) to a JSON array of KaTeX HTML (stdout).
// Usage: node tools/katex_render.js < formulas.json
// Needs the katex npm package; set KATEX_PATH to its directory if it is not resolvable.
'use strict';
const katex = require(process.env.KATEX_PATH || 'katex');

let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => { input += chunk; });
process.stdin.on('end', () => {
  const items = JSON.parse(input);
  const out = items.map(tex => {
    try {
      return { ok: true, html: katex.renderToString(tex, { displayMode: true, throwOnError: true, strict: 'ignore', output: 'htmlAndMathml' }) };
    } catch (err) {
      return { ok: false, error: String(err.message || err) };
    }
  });
  process.stdout.write(JSON.stringify(out));
});
