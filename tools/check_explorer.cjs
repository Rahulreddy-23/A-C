// Dependency-free interaction contract for the offline explorer. Browser layout/paint is separate.
const fs = require('node:fs');
const vm = require('node:vm');
const { performance } = require('node:perf_hooks');

class Element {
  constructor(tag) {
    this.tagName = tag;
    this.attrs = {};
    this.children = [];
    this.listeners = {};
    this.value = '';
    this.hidden = false;
    this.dataset = {};
    this._text = '';
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  get childNodes() { return this.children; }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this._text = ''; this.children = items; }
  addEventListener(type, callback) { this.listeners[type] = callback; }
}

const html = fs.readFileSync(process.argv[2], 'utf8');
const payload = JSON.parse(Buffer.from(html.match(/atob\('([A-Za-z0-9+/=]+)'\)/)[1], 'base64').toString());
const byId = new Map();
const document = {
  documentElement: new Element('html'),
  createElement: tag => new Element(tag),
  getElementById: id => {
    if (!byId.has(id)) byId.set(id, new Element(id));
    return byId.get(id);
  },
};
const context = {
  document, performance,
  atob: value => Buffer.from(value, 'base64').toString('binary'),
  TextDecoder, Uint8Array, URL,
  window: {}, requestAnimationFrame: callback => callback(),
};
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
vm.runInNewContext(script, context);
const get = id => byId.get(id);
const walk = (root, match) => [root, ...root.children.flatMap(child => walk(child, match))].filter(match);
const click = node => node.listeners.click();
const stats = { ...context.window.explorerStats };
if (![248, 251].includes(stats.nodes) || stats.nodes !== payload.nodes.length || stats.links !== payload.links.length || stats.render_ms >= 2000) throw Error('Graph payload incomplete or DOM build slow');
if (stats.selected !== 'SRS-021' || stats.focus.length < 10 || !stats.focus.includes('HAZ-04')) throw Error('Initial trace missing');
if (get('graph').children.length !== 3 || stats.directLinks < 2) throw Error('Focused relationship map missing');
if (walk(get('graph'), node => node.className === 'relation-card').length !== stats.directLinks) throw Error('Only direct confirmed links should be mapped');
const mappedDirections = walk(get('graph'), node => node.className === 'relation-card').map(node => node.attrs['aria-label']);
payload.links.filter(link => link.src === stats.selected || link.dst === stats.selected).forEach(link => {
  const direction = `${link.src} → ${link.type.replaceAll('_', ' ')} → ${link.dst}:`;
  if (!mappedDirections.some(label => label.startsWith(direction))) throw Error('Recorded link direction missing or reversed');
});
if (get('stages').children.length !== 5 || !get('stages').textContent.includes('UNIT-sensor_pressure')) throw Error('Trace context incomplete');
if (!get('detail').textContent.includes('SRS-021') || !walk(get('detail'), node => node.tagName === 'a').length) throw Error('Provenance inspector missing');

get('search').value = 'SRS-021'; get('search').listeners.input();
if (context.window.explorerStats.matched !== 1) throw Error('Search failed');
get('reset').listeners.click();
get('show-all').listeners.click();
if (context.window.explorerStats.view !== 'index' || context.window.explorerStats.visible !== stats.nodes || get('index').hidden) throw Error('Full index missing');
if (walk(get('index'), node => node.tagName === 'tr').length !== stats.nodes + 1) throw Error('Full index does not expose all artifacts');
const target = walk(get('index'), node => node.tagName === 'button' && node.textContent === 'COMP-05')[0];
click(target);
if (context.window.explorerStats.selected !== 'COMP-05' || context.window.explorerStats.view !== 'trace') throw Error('Index selection failed');
if (get('graph').children.length !== 3 || context.window.explorerStats.directLinks < 1) throw Error('Component map missing');
get('search').value = 'occlusion'; get('search').listeners.input();
if (context.window.explorerStats.selected === 'COMP-05' || context.window.explorerStats.matched < 2) throw Error('Inspector did not follow search');
get('reset').listeners.click(); get('rule').value = 'baseline'; get('rule').listeners.change();
if (context.window.explorerStats.matched < 2) throw Error('Baseline consistency filter failed');
get('reset').listeners.click(); get('rule').value = 'G06'; get('rule').listeners.change();
if (context.window.explorerStats.matched !== 1) throw Error('G06 filter failed');
get('reset').listeners.click(); get('state').value = 'latest'; get('state').listeners.change();
if (context.window.explorerStats.matched !== payload.nodes.filter(node => node.latest).length) throw Error('Latest result filter failed');
get('search').value = 'no-such-artifact'; get('search').listeners.input();
if (get('empty').hidden || context.window.explorerStats.selected !== null) throw Error('Empty state failed');
get('search').value = ''; get('search').listeners.input();
if (context.window.explorerStats.matched !== payload.nodes.filter(node => node.latest).length || !context.window.explorerStats.selected) throw Error('Clearing empty search failed');
get('reset').listeners.click();
if (context.window.explorerStats.matched !== stats.nodes || context.window.explorerStats.selected !== 'SRS-021') throw Error('Reset failed');
if (html.includes('<svg id="graph"') || !html.includes('[hidden]{display:none!important}')) throw Error('Old canvas or hidden-state regression');
console.log(JSON.stringify({ ...stats, search: 'pass', index: `${stats.nodes} accessible artifacts`, gap: 'pass', latest: 'pass', inspector: 'pass', benchmark: 'DOM contract only; browser layout/paint not measured' }));
