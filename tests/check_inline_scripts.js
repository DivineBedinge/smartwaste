'use strict';

const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const pages = fs.readdirSync(path.join(root, 'static')).filter(name => name.endsWith('.html'));
let checked = 0;

for (const page of pages) {
    const source = fs.readFileSync(path.join(root, 'static', page), 'utf8');
    const pattern = /<script(?![^>]*\bsrc=)(?![^>]*type=["']application\/(?:ld\+)?json["'])[^>]*>([\s\S]*?)<\/script>/gi;
    for (const match of source.matchAll(pattern)) {
        try {
            new Function(match[1]);
            checked += 1;
        } catch (error) {
            throw new SyntaxError(`${page}: ${error.message}`);
        }
    }
}

console.log(`Inline scripts checked: ${checked}`);
