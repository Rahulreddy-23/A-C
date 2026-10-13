// Dependency-free DOM contract check for the inline script. This is not a browser paint benchmark.
const fs = require('node:fs'), vm = require('node:vm'), { performance } = require('node:perf_hooks');
class Element {
  constructor(tag) { this.tagName=tag; this.attrs={}; this.children=[]; this.style={}; this.listeners={}; this.value=''; this.dataset={}; this.classList={toggle:()=>{}}; }
  setAttribute(k,v) { this.attrs[k]=String(v); }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children=items; }
  addEventListener(type,fn) { this.listeners[type]=fn; }
  scrollTo() {}
  querySelector(selector){return this.querySelectorAll(selector)[0]}
  querySelectorAll(selector){return this.children.flatMap(n=>[...(selector.startsWith('.')?(n.attrs.class||'').split(' ').includes(selector.slice(1)):n.tagName===selector)?[n]:[],...n.querySelectorAll(selector)])}
  get childNodes() { return this.children; }
}
const html=fs.readFileSync(process.argv[2], 'utf8'), byId=new Map();
const document={documentElement:new Element('html'),createElement:tag=>new Element(tag),createElementNS:(_,tag)=>new Element(tag),getElementById:id=>{if(!byId.has(id))byId.set(id,new Element(id));return byId.get(id)}};
const context={document,performance,atob:s=>Buffer.from(s,'base64').toString('binary'),TextDecoder,Uint8Array,URL,window:{},requestAnimationFrame:fn=>fn()};
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
vm.runInNewContext(script,context);
const stats={...context.window.explorerStats};if(!stats.focus.includes('SYS-007')||!stats.focus.includes('HAZ-04')||!stats.focus.includes('UNIT-sensor_pressure'))throw Error('Trace chain incomplete');
const graph=byId.get('graph');
if (graph.children.filter(n=>n.tagName==='g').length !== stats.nodes || stats.render_ms>=2000) throw Error('Incomplete or slow DOM build');
if(byId.get('viewport').style.height!=='160px')throw Error('Focused chain did not fit viewport');
byId.get('search').value='SRS-021'; byId.get('search').listeners.input();
if(context.window.explorerStats.matched!==1)throw Error('Search failed');
byId.get('reset').listeners.click();
if(byId.get('search').value!==''||context.window.explorerStats.visible!==stats.nodes||context.window.explorerStats.focus.length)throw Error('Reset did not clear filters and focus');
byId.get('rule').value='baseline';byId.get('rule').listeners.change();
if(context.window.explorerStats.matched<2)throw Error('Baseline consistency filter failed');
byId.get('reset').listeners.click(); byId.get('rule').value='G06'; byId.get('rule').listeners.change();
if(context.window.explorerStats.matched!==1)throw Error('G06 filter failed');
byId.get('reset').listeners.click(); byId.get('state').value='latest'; byId.get('state').listeners.change();
if(context.window.explorerStats.matched!==40)throw Error('Latest results failed');
const allText=n=>n.textContent||n.children.map(allText).join(' ');
if(!allText(byId.get('detail')).includes('SRS-021')) throw Error('Source inspector failed');
console.log(JSON.stringify({...stats,search:'pass',G06:'pass',latest:'pass',inspector:'pass',benchmark:'DOM contract only; browser layout/paint not measured'}));
