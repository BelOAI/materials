// Сборка Markdown и формул; браузеру не нужен Markdown/KaTeX runtime.
import fs from 'node:fs';
import MarkdownIt from 'markdown-it';
import katex from 'katex';
import texmath from 'markdown-it-texmath';

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const md = new MarkdownIt({ html: true, typographer: false });
md.use(texmath, { engine: katex, delimiters: 'dollars', katexOptions: {
  output: 'htmlAndMathml', throwOnError: true, trust: false,
} });

// Only a separate italic caption next to its object is a caption. Keep alt text
// independent, and leave prose, inline images and fenced examples untouched.
md.core.ruler.after('inline', 'handbook-objects', state => {
  const tokens = state.tokens;
  const paragraph = i => tokens[i]?.type === 'paragraph_open'
    && tokens[i + 1]?.type === 'inline' && tokens[i + 2]?.type === 'paragraph_close';
  function caption(i, kind) {
    if (!paragraph(i)) return null;
    let children = tokens[i + 1].children.filter(t => t.type !== 'text' || t.content);
    if (children[0]?.type !== 'em_open' || children.at(-1)?.type !== 'em_close') return null;
    let depth = 0;
    for (const [index, token] of children.entries()) {
      if (token.type === 'em_open') depth++;
      if (token.type === 'em_close' && --depth === 0 && index !== children.length - 1) return null;
    }
    children = children.slice(1, -1).map(t => Object.assign(Object.create(Object.getPrototypeOf(t)), t));
    const first = children[0];
    const prefix = /^(Рисунок|Рис\.|Таблица)\s+(\d+)\s*(?:—|[.:-])\s+/u;
    const match = first?.type === 'text' && first.content.match(prefix);
    if (!match || (match[1] === 'Таблица' ? 'table' : 'figure') !== kind) return null;
    first.content = first.content.replace(prefix, `${kind === 'table' ? 'Таблица' : 'Рисунок'} ${match[2]} — `);
    if (children.at(-1)?.type === 'text') children.at(-1).content = children.at(-1).content.replace(/\.\s*$/u, '');
    const inline = new state.Token('inline', '', 0);
    inline.children = children;
    return inline;
  }
  const tag = (name, nesting, attrs) => {
    const token = new state.Token(`${name}_${nesting === 1 ? 'open' : 'close'}`, name, nesting);
    token.block = true;
    token.attrs = attrs ?? null;
    return token;
  };
  const result = [];
  let tableIndex = 0;
  for (let i = 0; i < tokens.length; i++) {
    const children = paragraph(i) ? tokens[i + 1].children.filter(t => t.type !== 'text' || t.content.trim()) : [];
    const image = children.length === 1 && children[0].type === 'image'
      || children.length === 3 && children[0].type === 'link_open' && children[1].type === 'image' && children[2].type === 'link_close';
    if (image) {
      result.push(tag('figure', 1, [['class', 'handbook-figure']]), tokens[i + 1]);
      const label = caption(i + 3, 'figure');
      if (label) result.push(tag('figcaption', 1), label, tag('figcaption', -1));
      result.push(tag('figure', -1));
      i += label ? 5 : 2;
      continue;
    }
    const label = caption(i, 'table');
    const table = tokens[i + (label ? 3 : 0)];
    if (table?.type === 'table_open') {
      const id = `handbook-table-caption-${++tableIndex}`;
      result.push(tag('figure', 1, [['class', 'handbook-table']]));
      if (label) result.push(tag('figcaption', 1, [['id', id]]), label, tag('figcaption', -1));
      const name = label ? ['aria-labelledby', id] : ['aria-label', 'Таблица'];
      result.push(tag('div', 1, [['class', 'handbook-table-scroll'], ['tabindex', '0'], ['role', 'region'], name]));
      if (label) i += 3;
      if (label) tokens[i].attrSet('aria-labelledby', id);
      result.push(tokens[i]);
      while (tokens[++i].type !== 'table_close') result.push(tokens[i]);
      result.push(tokens[i], tag('div', -1), tag('figure', -1));
      continue;
    }
    result.push(tokens[i]);
  }
  state.tokens = result;
});
// texmath превращает ошибки KaTeX в HTML: для сборки они должны быть фатальными.
// Перед рендерингом отдельно проверяем математические токены.
const results = input.map(({ source, name }) => {
  const tokens = md.parse(source, {});
  const toc = [], seen = new Map();
  function check(items) {
    for (const token of items) {
      if (token.type.startsWith('math_')) {
        try { katex.renderToString(token.content, { throwOnError: true, trust: false }); }
        catch (error) { throw new Error(`${name}: ${error.message}`); }
      }
      if (token.children) check(token.children);
    }
  }
  check(tokens);
  tokens.forEach((token, index) => {
    if (token.type !== 'heading_open') return;
    const text = tokens[index + 1].children.map(t => t.type === 'code_inline' || t.type === 'text' ? t.content : '').join('');
    const base = text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu, '-').replace(/^-|-$/g, '') || 'section';
    const count = (seen.get(base) || 0) + 1;
    seen.set(base, count);
    const id = count === 1 ? base : `${base}-${count}`;
    token.attrSet('id', id);
    toc.push({ id, text, level: Number(token.tag.slice(1)) });
  });
  return { html: md.renderer.render(tokens, md.options, {}), toc };
});
process.stdout.write(JSON.stringify(results));
