# Slide fragments

Number files with a two-digit prefix so they sort in presentation order.
Leave gaps (`10-`, `20-`) when you expect to insert slides later.

Each file contains `\begin{frame}...\end{frame}` blocks and optional `\section{}`.
Do not put `\documentclass` or `\begin{document}` here.

## Example slides in this template

Patterns taken from the full Academic-theme reference deck:

| File | Pattern |
| ---- | ------- |
| `01-title.tex` | Титульный слайд |
| `02-outline.tex` | Содержание в двух колонках |
| `03-columns-blocks.tex` | `\lead{}` + блоки в колонках |
| `04-goals-blocks.tex` | Два блока «цель / задачи» |
| `05-table-stages.tex` | Широкая таблица `booktabs` + сноска |
| `06-formula-numbers.tex` | Формула, списки, `\tbd{}`, таблица в блоке |
| `07-image-placeholder.tex` | `\photoframe` и комментарий к `\includegraphics` |
| `08-responsibilities.tex` | Блоки «обеспечивает / не делает» |
| `09-rules-columns.tex` | Два списка с `\lead{}` |
| `10-tech-table.tex` | Таблица с `\orient` в заголовке |
| `11-packages-table.tex` | Длинная таблица + два блока в колонках |

When copying the template, remove example files you do not need and rename the rest.

## Theme macros

- `\lead{текст}` — акцентный lead-in
- `\tbd{текст}` — пометка черновика
- `\orient` — метка «ориентир» в заголовке слайда
- `\photoframe{ширина}{высота}{подпись}` — заглушка под фото
- `\orientnote` — сноска под таблицей (см. `10-tech-table.tex`)

Images go in `assets/`; `\graphicspath{{assets/}}` is set in `main.tex`.
