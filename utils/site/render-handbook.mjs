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
