const fs = require('fs');
const path = require('path');
const { Resvg } = require('@resvg/resvg-js');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'static', 'mascot-recycleur.svg'));
for (const [name, size] of [['apple-touch-icon.png', 180], ['icon-192.png', 192], ['icon-512.png', 512], ['icon-maskable-512.png', 512]]) {
  const rendered = new Resvg(source, { fitTo: { mode: 'width', value: size }, background: name.includes('maskable') ? '#d1fae5' : '#ffffff' }).render().asPng();
  fs.writeFileSync(path.join(root, 'static', name), rendered);
}
