// Local-only rendering checks: node --test test_listing.cjs
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { join } = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const context = vm.createContext({
  document: { querySelector() { return null; }, addEventListener() {} },
  ElevenZeroApp: { escapeHtml: value => String(value).replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;') },
});
vm.runInContext(readFileSync(join(__dirname, 'listing.js'), 'utf8'), context);

test('seller prose and line breaks are retained', () => {
  const output = context.renderSellerNotes('Lightly used.\nIncludes a cover.');
  assert.match(output, /Lightly used\.\nIncludes a cover\./);
  assert.doesNotMatch(output, /<dl/);
});

test('pasted specifications render as labeled rows without losing values', () => {
  const output = context.renderSellerNotes('Original grip. Surface: Carbon Core: 16mm Grip Length: 5.5in');
  assert.match(output, /Original grip\./);
  assert.match(output, /<dt>Surface<\/dt><dd>Carbon<\/dd>/);
  assert.match(output, /<dt>Core<\/dt><dd>16mm<\/dd>/);
  assert.match(output, /<dt>Grip Length<\/dt><dd>5.5in<\/dd>/);
});

test('seller HTML is escaped in both prose and specification values', () => {
  for (const value of ['<img src=x onerror=alert(1)>', 'Surface: <script>alert(1)</script> Core: <img src=x>']) {
    const output = context.renderSellerNotes(value);
    assert.doesNotMatch(output, /<script|<img/);
    assert.match(output, /&lt;/);
  }
});
