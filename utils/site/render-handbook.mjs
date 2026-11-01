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
  let tableIndex = state.env.tableIndex || 0;
  for (let i = 0; i < tokens.length; i++) {
    const children = paragraph(i) ? tokens[i + 1].children.filter(t => t.type !== 'text' || t.content.trim()) : [];
    const image = children.length === 1 && children[0].type === 'image'
      || children.length === 3 && children[0].type === 'link_open' && children[1].type === 'image' && children[2].type === 'link_close';
    if (image) {
      result.push(tag('figure', 1, [['class', 'handbook-figure']]), tokens[i + 1]);
      const label = caption(i + 3, 'figure');
      if (!label && state.env.requireCaptions) throw new Error(`${state.env.name}: рисунок без соседней подписи «Рисунок N — Название»`);
      if (label) result.push(tag('figcaption', 1), label, tag('figcaption', -1));
      result.push(tag('figure', -1));
      i += label ? 5 : 2;
      continue;
    }
    const label = caption(i, 'table');
    const table = tokens[i + (label ? 3 : 0)];
    if (table?.type === 'table_open') {
      if (!label && state.env.requireCaptions) throw new Error(`${state.env.name}: таблица без подписи «Таблица N — Название» сверху`);
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
  state.env.tableIndex = tableIndex;
  state.tokens = result;
});
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {important:'Важно', warning:'Предупреждение', note:'Примечание', tip:'Совет'};
function renderBlocks(nodes, env) {
  const fragment = source => {
    const tokens = md.parse(source, env);
    const check = list => { for (const token of list) {
      if (token.type.startsWith('math_')) katex.renderToString(token.content, {throwOnError:true, trust:false});
      if (token.children) check(token.children);
    }};
    check(tokens);
    // Assign the same heading anchors as the ordinary page pass below.
    for (let i=0; i<tokens.length; i++) if (tokens[i].type==='heading_open') {
      const text = tokens[i+1].children.map(t => t.type==='code_inline'||t.type==='text' ? t.content : '').join('');
      const base = text.toLowerCase().replace(/[^\p{L}\p{N}]+/gu,'-').replace(/^-|-$/g,'')||'section';
      const count=(env.seen.get(base)||0)+1; env.seen.set(base,count);
      tokens[i].attrSet('id',count===1?base:`${base}-${count}`);
    }
    return md.renderer.render(tokens, md.options, env);
  };
  return nodes.map(node => {
    if (node.kind==='text') return fragment(node.text);
    const attrs=node.attrs;
    if (node.kind==='callout') return `<aside class="handbook-callout callout-${escape(attrs.type)}"><div class="callout-title"><img src="${"../".repeat(1 + env.name.split("/").filter(Boolean).length)}assets/handbook-icons/${escape(attrs.type)}.svg" alt="" aria-hidden="true">${escape(attrs.title||labels[attrs.type])}</div>${renderBlocks(node.children,env)}</aside>`;
    if (node.kind==='self-check') {
      const questions = node.children.filter(child => child.kind==='question');
      const links = questions.map(question => {
        const key = `${env.name.replace(/[^a-zA-Z0-9-]/g,'-')}--${question.attrs.id}`;
        return `<a href="#${key}" data-number="${question.number}" aria-label="Вопрос ${question.number}: ещё не проверен">${question.number}<span class="quiz-nav-mark" aria-hidden="true"></span></a>`;
      }).join('');
      return `<section class="handbook-self-check" aria-label="Самопроверка"><div class="quiz-overview" hidden><div class="quiz-progress-heading"><p class="quiz-progress-text">Проверено 0 из ${questions.length}</p></div><progress value="0" max="${questions.length}" aria-label="Проверено вопросов">0 из ${questions.length}</progress><nav class="quiz-nav" aria-label="Вопросы самопроверки">${links}</nav></div>${renderBlocks(node.children,env)}<section class="quiz-summary" aria-label="Результат самопроверки" tabindex="-1" hidden><h3>Самопроверка завершена</h3><p class="quiz-score"></p><p class="quiz-summary-note"></p><div class="quiz-actions"><button type="button" class="quiz-review">К вопросам с ошибками</button><button type="button" class="quiz-restart">Начать заново</button></div></section></section>`;
    }
    if (node.kind==='question') {
      const key=`${env.name.replace(/[^a-zA-Z0-9-]/g,'-')}--${attrs.id}`;
      const group=kind=>node.children.find(c=>c.kind===kind);
      const prompt=renderBlocks(node.children.filter(c=>c.kind==='text'),env);
      const choices=group('choices').items.map((value,i)=>`<div class="quiz-choice"><input type="radio" id="${key}-${i}" name="${key}" value="${'ABCD'[i]}"><label for="${key}-${i}"><span class="quiz-letter">${'ABCD'[i]}.</span><div>${fragment(value)}</div></label></div>`).join('');
      return `<section class="handbook-question" id="${key}" tabindex="-1" aria-labelledby="${key}-number" aria-describedby="${key}-prompt" data-correct="${escape(attrs.correct)}"><fieldset aria-describedby="${key}-prompt"><legend id="${key}-number">Вопрос ${node.number}</legend><div class="quiz-prompt" id="${key}-prompt">${prompt}</div>${choices}</fieldset><details class="quiz-hint"><summary>Подсказка</summary>${renderBlocks(group('hint').children,env)}</details><div class="quiz-actions"><button type="button" class="quiz-check" hidden disabled>Проверить ответ</button><button type="button" class="quiz-retry" hidden>Ответить ещё раз</button><button type="button" class="quiz-next" hidden>Следующий вопрос</button></div><p class="quiz-result" role="status" aria-live="polite" aria-atomic="true"></p><details class="quiz-solution"><summary>Решение</summary>${renderBlocks(group('solution').children,env)}</details></section>`;
    }
    return renderBlocks(node.children,env);
  }).join('');
}
// texmath превращает ошибки KaTeX в HTML: для сборки они должны быть фатальными.
// Перед рендерингом отдельно проверяем математические токены.
const results = input.map(({ source, name, requireCaptions = false, blocks }) => {
  const tokens = md.parse(source, { name, requireCaptions });
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
  return { html: blocks ? renderBlocks(blocks, {name, requireCaptions, seen:new Map()}) : md.renderer.render(tokens, md.options, {}), toc };
});
process.stdout.write(JSON.stringify(results));
