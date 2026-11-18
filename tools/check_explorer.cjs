// Dependency-free interaction and graph geometry contract. Not a browser paint benchmark.
const fs = require('node:fs');
const vm = require('node:vm');
const { performance } = require('node:perf_hooks');
class Element {
  constructor(tag) {
    this.tagName = tag; this.attrs = {}; this.children = []; this.listeners = {};
    this.value = ''; this.hidden = false; this.dataset = {}; this.style = {}; this._text = '';
    this.clientWidth = 1024; this.clientHeight = 600;
  }
  set textContent(value) { this._text = String(value); this.children = []; }
  get textContent() { return this._text + this.children.map(n => n.textContent).join(''); }
  get childNodes() { return this.children; }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this._text = ''; this.children = items; }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  getBoundingClientRect() { return { left: 0, top: 0, width: this.clientWidth, height: this.clientHeight }; }
  // A deliberately tall measured action-item node proves layout uses DOM height.
  get offsetHeight() { return this.attrs['data-id'] === 'ACT-01' ? 220 : undefined; }
}
const html = fs.readFileSync(process.argv[2], 'utf8');
const encoded = html.match(/atob\('([A-Za-z0-9+/=]+)'\)/);
const payload = encoded ? JSON.parse(Buffer.from(encoded[1], 'base64').toString()) : null;
const formattingProbe = payload?.documents.find(d => d.id === 'drr');
if (formattingProbe) {
  formattingProbe.sections.push({
    id: 'formatting-probe', title: 'Formatting probe', claims: [], cited_revisions: { 'SRS-021': 'older-revision' },
    markdown: '## Parent heading\n### Formatting probe\n| Rule | Evidence |\n| --- | --- |\n' +
      '| G01 | A \\| B<br />[SRS-021](https://invalid.example/ignored) <em>literal markup</em> |',
  });
}
const byId = new Map();
const markupIDs = new Set([...html.matchAll(/\bid="([^"]+)"/g)].map(match => match[1]));
const document = {
  documentElement: new Element('html'),
  createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag),
  getElementById: id => {
    if (!markupIDs.has(id)) throw Error('Control has no markup: ' + id);
    if (!byId.has(id)) byId.set(id, new Element(id)); return byId.get(id);
  },
};
const decodeEvidence = value => formattingProbe ? Buffer.from(JSON.stringify(payload)).toString('binary') : Buffer.from(value, 'base64').toString('binary');
const context = { document, performance, atob: decodeEvidence, TextDecoder, Uint8Array, URL, window: {}, requestAnimationFrame: fn => fn() };
vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1], context);
const get = id => byId.get(id);
if (!payload) {
  if (document.documentElement.dataset.ready !== 'error' || get('load-status').hidden) throw Error('Template failed without an explanation');
  console.log(JSON.stringify({ template: 'clear missing-evidence message' })); process.exit(0);
}
const walk = (root, match) => [root, ...root.children.flatMap(n => walk(n, match))].filter(match);
const click = node => node.listeners.click({ detail: 1 });
const stats = () => context.window.explorerStats;
const initialApp = { ...stats() };
if (initialApp.page !== 'overview' || !get('page-content').textContent.includes('Trace coverage')) throw Error('App did not open on its useful overview');
click(get('nav-documents'));
if (stats().page !== 'documents' || stats().documents !== payload.documents.length) throw Error('Documents view missing');
if (payload.documents.length && !get('page-content').textContent.includes('Structural mock draft')) throw Error('Mock provenance not labeled');
const documentView = get('page-content');
const changeSelect = (select, value) => { select.value = value; select.listeners.change(); };
const findClass = (root, name) => walk(root, n => n.className === name)[0];
const switchDocument = id => changeSelect(findClass(documentView, 'doc-control doc-switcher').children[0], id);
const jumpToSection = (docID, sectionID) => {
  const index = payload.documents.find(d => d.id === docID).sections.findIndex(s => s.id === sectionID);
  changeSelect(findClass(documentView, 'doc-control doc-section-select').children[0], String(index));
  return findClass(documentView, 'doc-reader');
};
if (payload.documents.some(d => d.id === 'drr')) {
  switchDocument('drr');
  let reader = jumpToSection('drr', 'identification');
  if (!walk(reader, n => n.tagName === 'br').length || reader.textContent.includes('<br>')) throw Error('Document line breaks are printed as markup');
  reader = jumpToSection('drr', 'findings_table');
  const compact = walk(reader, n => n.tagName === 'th' && n.className === 'compact-column');
  if (!compact.some(n => n.textContent === 'Rule') || !compact.some(n => n.textContent === 'Count')) throw Error('Findings table lost its readable short columns');
  const matchingHeadings = walk(reader, n => /^h[1-6]$/.test(n.tagName) && n.textContent === 'Complete deterministic pre-review findings');
  if (matchingHeadings.length !== 1) throw Error('Document section title was repeated');
  const source = walk(reader, n => n.tagName === 'button' && n.textContent === 'SRS-012')[0];
  click(source);
  if (!stats().inspector || stats().page !== 'documents' || stats().selected !== 'SRS-012') throw Error('Document citation lost the reader or evidence inspector');
  switchDocument('sstr');
  reader = jumpToSection('sstr', 'anomaly_assessment');
  if (!walk(reader, n => n.tagName === 'table').length || !findClass(reader, 'claim')) throw Error('Mixed evidence table and commentary must both be readable');
  switchDocument('drr');
  if (!findClass(documentView, 'doc-reader').textContent.includes('Complete deterministic pre-review findings')) throw Error('Document switch lost the last-read section');
  reader = jumpToSection('drr', 'formatting-probe');
  const cells = walk(reader, n => n.tagName === 'td');
  if (cells.length !== 2 || !cells[1].textContent.includes('A | B') || !walk(cells[1], n => n.tagName === 'br').length) throw Error('Escaped pipe or break corrupted a document cell');
  if (!reader.textContent.includes('Parent heading') || !cells[1].textContent.includes('<em>literal markup</em>') || walk(cells[1], n => n.tagName === 'em').length) throw Error('Parent heading or safe literal text was lost');
  click(walk(cells[1], n => n.tagName === 'button' && n.textContent === 'SRS-021')[0]);
  if (!get('detail').textContent.includes('Document cited revision older-revision')) throw Error('Table citation lost its recorded revision');
}
if (payload.documents.some(d => d.id === 'sdd')) {
  switchDocument('sdd');
  const filter = walk(documentView, n => n.tagName === 'input' && n.type === 'search')[0];
  if (!filter) throw Error('Long document has no section search');
  filter.value = 'no matching section 7bdc'; filter.listeners.input();
  if (findClass(documentView, 'doc-outline-empty').hidden) throw Error('Empty section search has no feedback');
  filter.value = ''; filter.listeners.input();
  if (walk(documentView, n => n.className === 'doc-outline-item' && !n.hidden).length !== payload.documents.find(d => d.id === 'sdd').sections.length) throw Error('Section search failed to restore the outline');
}
click(get('nav-findings'));
const ruleFilter = walk(get('page-content'), n => n.tagName === 'select')[0];
ruleFilter.value = 'G06'; ruleFilter.listeners.change();
if (walk(get('page-content'), n => n.tagName === 'tr').length !== payload.findings.filter(f => f.rule === 'G06').length + 1) throw Error('Finding filter has wrong rows');
const findingArtifact = walk(get('page-content'), n => n.tagName === 'button' && n.textContent === 'RC-12')[0];
click(findingArtifact);
if (stats().page !== 'findings' || stats().selected !== 'RC-12' || !stats().inspector) throw Error('Finding inspection unexpectedly left the page');
click(get('nav-impact'));
if (payload.impact_reports.some(report => report.sections.length) && !get('page-content').textContent.includes('Recorded cause')) throw Error('Change causes missing');
click(get('nav-risk'));
if (walk(get('page-content'), n => n.tagName === 'tr').length !== payload.risk.length + 1) throw Error('Risk paths missing');
click(get('nav-trace'));
if (stats().anchor !== 'RC-12') throw Error('Trace navigation lost the artifact inspected in Findings');
click(get('reset'));
get('scope').value = 'trace'; get('scope').listeners.change();
const initial = { ...stats() };
function geometry() {
  const boxes = stats().layout;
  boxes.forEach((a, i) => boxes.slice(i + 1).forEach(b => {
    if (a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y) throw Error(`Overlapping nodes: ${a.id}/${b.id}`);
  }));
  const labels = stats().edgeLabels;
  labels.forEach((a, i) => [...labels.slice(i + 1), ...boxes].forEach(b => {
    if (a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y) throw Error(`Label overlap: ${a.src}/${a.dst}`);
  }));
  if (stats().scope === 'direct' && labels.length) throw Error('Direct arrows obscured by floating labels');
  const shown = new Set(boxes.map(n => n.id));
  const expected = payload.links.filter(e => shown.has(e.src) && shown.has(e.dst) && (stats().scope !== 'direct' || e.src === stats().anchor || e.dst === stats().anchor));
  const paths = get('edges').children.filter(n => n.tagName === 'path');
  if (paths.length !== expected.length) throw Error('A confirmed edge is missing');
  expected.forEach(e => {
    if (!paths.some(p => p.attrs['data-src'] === e.src && p.attrs['data-dst'] === e.dst && p.attrs['data-type'] === e.type && p.attrs['marker-end'])) throw Error('Edge direction/type/arrowhead missing');
  });
  get('nodes').children.forEach(node => {
    const source = payload.nodes.find(n => n.id === node.attrs['data-id']);
    const title = node.children.find(n => n.className === 'node-title');
    if (title.textContent !== source.title || !node.textContent.includes(source.id)) throw Error('Truncated node label');
  });
}
if (get('load-status').hidden !== true || initial.nodes !== payload.nodes.length || initial.links !== payload.links.length) throw Error('Evidence did not initialize');
// render_ms counts from page start and refreshes on every update, so only the stats taken at load time the initial render.
if (initialApp.render_ms >= 2000) throw Error(`Initial render took ${Math.round(initialApp.render_ms)} ms`);
if (initial.selected !== 'SRS-021' || !initial.focus.includes('SYS-007') || !initial.focus.includes('HAZ-04') || !initial.focus.includes('UNIT-sensor_pressure')) throw Error('Default trace incomplete');
geometry();
get('search').value = 'REV-01'; get('search').listeners.input();
if (stats().matched !== 1 || stats().anchor !== 'REV-01' || stats().visible < 5) throw Error('Review/action graph missing');
geometry();
if (stats().layout.find(n => n.id === 'ACT-01').height !== 220) throw Error('Measured node height ignored');
const action = get('nodes').children.find(n => n.attrs['data-id'] === 'ACT-01'); click(action);
if (stats().selected !== 'ACT-01' || stats().anchor !== 'REV-01' || !stats().inspector || !get('detail').textContent.includes(payload.nodes.find(n => n.id === 'ACT-01').title)) throw Error('Selection lost graph context or full title');
action.listeners.dblclick();
if (stats().anchor !== 'ACT-01' || get('search').value !== '') throw Error('Focus did not navigate beyond the filter');
click(get('back'));
if (stats().anchor !== 'REV-01') throw Error('Back navigation failed');
click(get('reset')); get('scope').value = 'direct'; get('scope').listeners.change();
if (stats().visible !== new Set(payload.links.filter(e => e.src === 'SRS-021' || e.dst === 'SRS-021').flatMap(e => [e.src, e.dst])).size) throw Error('Direct scope wrong');
geometry();
click(get('show-all'));
if (stats().view !== 'index' || stats().visible !== payload.nodes.length || walk(get('index'), n => n.tagName === 'tr').length !== payload.nodes.length + 1) throw Error('Full evidence index incomplete');
click(walk(get('index'), n => n.tagName === 'button' && n.textContent === 'COMP-05')[0]);
if (stats().anchor !== 'COMP-05' || stats().view !== 'graph') throw Error('Index navigation failed');
get('scope').value = 'trace'; get('scope').listeners.change(); geometry();
if (stats().visible < 20) throw Error('Component trace too thin');
click(get('reset')); get('rule').value = 'baseline'; get('rule').listeners.change();
if (stats().matched < 2) throw Error('Baseline rule filter failed');
click(get('reset')); get('rule').value = 'G06'; get('rule').listeners.change();
if (stats().matched !== 1) throw Error('G06 filter failed');
click(get('reset')); get('state').value = 'latest'; get('state').listeners.change();
if (stats().matched !== payload.nodes.filter(n => n.latest).length) throw Error('Latest filter failed');
get('search').value = 'missing-artifact'; get('search').listeners.input();
if (get('empty').hidden || stats().selected !== null) throw Error('Empty state failed');
get('search').value = ''; get('search').listeners.input();
if (!stats().selected) throw Error('Clearing empty query failed');
click(get('reset')); const scale = stats().scale; click(get('zoom-in'));
if (stats().scale <= scale) throw Error('Zoom in failed');
click(get('actual-size')); if (Math.abs(stats().scale - 1) > .0001) throw Error('Actual-size view failed');
click(get('fit')); if (stats().scale < .9) throw Error('Fit made labels unreadable');
const oldTransform = get('scene').style.transform;
get('viewport').listeners.keydown({ target: get('viewport'), key: 'ArrowLeft', preventDefault() {} });
if (get('scene').style.transform === oldTransform) throw Error('Keyboard pan failed');
get('viewport').listeners.pointerdown({ target: {}, button: 0, pointerId: 1, clientX: 20, clientY: 20 });
get('viewport').listeners.pointermove({ pointerId: 1, clientX: 80, clientY: 50 }); get('viewport').listeners.pointerup();
// Sweep every artifact: a direct view contains only its own recorded relationships.
// Full traces must retain all scoped edges without overlapping labels or node text.
let sweepContexts = 0;
for (const node of payload.nodes) {
  for (const scope of ['direct', 'trace']) {
    click(get('reset')); get('scope').value = scope;
    get('search').value = node.id; get('search').listeners.input();
    const result = get('results').children.find(n => n.children.some(c => c.className === 'result-id' && c.textContent === node.id));
    click(result); geometry(); sweepContexts++;
    const focused = stats().layout.find(n => n.id === node.id), camera = stats().camera;
    const left = focused.x * camera.scale + camera.x, top = focused.y * camera.scale + camera.y;
    if (left < 15 || left + focused.width * camera.scale > get('viewport').clientWidth - 15 || top < 50 || top + focused.height * camera.scale > get('viewport').clientHeight - 60) throw Error('Focused artifact is offscreen: ' + node.id);
    if (scope === 'direct') {
      const layout = new Map(stats().layout.map(p => [p.id, p]));
      for (const outgoing of [true, false]) {
        const ports = stats().ports.filter(p => outgoing ? p.src === node.id : p.dst === node.id);
        ports.sort((a, b) => {
          const pa = layout.get(outgoing ? a.dst : a.src), pb = layout.get(outgoing ? b.dst : b.src);
          return pa.y + pa.height / 2 - pb.y - pb.height / 2;
        });
        for (let i = 1; i < ports.length; i++) {
          if ((outgoing ? ports[i].ay - ports[i - 1].ay : ports[i].by - ports[i - 1].by) < 0) throw Error('Crossed direct fan ports: ' + node.id);
        }
      }
    }
    const failed = get('nodes').children.filter(n => payload.nodes.some(p => p.id === n.attrs['data-id'] && p.latest && p.outcome === 'Failed'));
    for (const card of failed) {
      if (!walk(card, n => n.className === 'flag failed' && n.textContent === 'Latest: Failed').length) throw Error('Failed evidence shown as a pass');
    }
  }
}
click(get('reset'));
if (!html.includes('data-theme="light"')) throw Error('Rejected dark palette still opens by default');
click(get('theme')); if (!document.documentElement.dataset.theme) throw Error('Theme control failed');
if (!html.includes('prefers-reduced-motion') || html.includes('text-overflow:ellipsis') || html.includes('line-clamp')) throw Error('Motion or label overflow regression');
console.log(JSON.stringify({ nodes: initial.nodes, links: initial.links, documents: payload.documents.length, workspace_views: '6 pass', default_context: initial.visible, mapped_links: initial.mappedLinks, render_ms: initial.render_ms, full_labels: 'pass', measured_layout: 'pass', edge_directions: 'pass', graph_contexts_checked: sweepContexts, label_collision: 'pass', focused_artifact_visible: 'pass', failure_color: 'pass', search_filters_index: 'pass', pan_zoom_navigation: 'pass', benchmark: 'DOM contract only; browser paint not measured' }));
