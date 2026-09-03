'use strict';

const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const context = {window: {}, URL, location: {origin: 'https://smartwaste.test', hostname: 'smartwaste.test'}};
vm.createContext(context);
vm.runInContext(fs.readFileSync('static/dom-security.js', 'utf8'), context);

for (const payload of [
    '<img src=x onerror=alert(1)>',
    '<script>alert(1)</script>',
    'javascript:alert(1)',
    '" onmouseover="alert(1)',
]) {
    const rendered = String(context.window.safeHtml`<p>${payload}</p>`);
    assert.strictEqual(rendered, `<p>${context.window.escapeText(payload)}</p>`);
}
assert.strictEqual(context.window.safeUrl('javascript:alert(1)'), null);
assert.strictEqual(context.window.safeUrl('data:text/html,boom'), null);
assert(context.window.safeUrl('https://example.test/path').startsWith('https:'));
assert(context.window.safeUrl('tel:+237600000000').startsWith('tel:'));
assert.strictEqual(context.window.safeImageDataUrl('data:image/svg+xml,<svg/>'), null);
assert(context.window.safeImageDataUrl('data:image/png;base64,iVBORw0KGgo='));

console.log('DOM security payloads checked: 4');
