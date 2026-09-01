# Lectures

Each presentation lives in `lectures/[number]-[name]/` with:

```
lectures/02-collections/
  main.tex       # driver: documentclass, package, metadata, \input{slides/...}
  meta.yaml      # site index metadata
  slides/        # numbered slide fragments
  assets/        # optional images (referenced via \graphicspath)
  materials/     # optional notebooks, PDFs, archives (published to _site/)
```

## Naming

Use a numeric prefix for human-readable labels on the site (e.g. «Лекция 2»), e.g. `01-project-setup`, `02-collections`. The **site sort order** is determined by `date` and `slot`/`time` in `meta.yaml`, not the folder prefix.

For practice sessions, see [`../practices/README.md`](../practices/README.md).

Folders starting with `_` (e.g. `_template`) are excluded from CI builds.

## meta.yaml schema

| Field | Required | Default | Purpose |
| ----- | -------- | ------- | ------- |
| `title` | yes | — | Index page title |
| `subtitle` | no | — | Card subtitle |
| `date` | yes | — | Session date (ISO `YYYY-MM-DD`) |
| `slot` | no | `1` | Time slot: `1` → 11:25–12:50, `2` → 13:15–14:40 |
| `time` | no | — | Override slot with custom time, e.g. `10:30` or `10:30–12:00` |
| `description` | no | — | Card blurb |
| `lang` | no | — | Informational (`ru`, `en`); language is set in `main.tex` |
| `build` | no | `true` | Set `false` to skip CI/local batch builds |
| `hidden` | no | `false` | Omit from public index (artifacts still built if `build: true`) |
| `references` | no | — | List of external links (see below) |
| `materials` | no | — | List of files to publish (see below) |

### references

External links shown as chips on the lecture card.

```yaml
references:
  - kind: contest
    url: https://new.contest.yandex.ru/contests/98758
    label: Задачи занятия          # optional
  - kind: kaggle
    url: https://www.kaggle.com/competitions/example
  - label: Custom link             # required when kind is omitted
    url: https://example.com
```

| `kind` | Default label |
| ------ | ------------- |
| `contest` | Яндекс.Контест |
| `kaggle` | Kaggle |
| `huggingface` | Hugging Face |
| `colab` | Google Colab |

### materials

Files relative to the lecture folder. `.ipynb` files are rendered to HTML and offered for download.

```yaml
materials:
  - path: materials/notebook.ipynb
    label: Jupyter Notebook        # optional
  - path: materials/cheatsheet.pdf
```

### Index inclusion

A lecture appears on the site when `build: true`, `hidden: false`, and **at least one** of:

- PDF was built (`main.tex` present)
- a declared material was copied to `_site/materials/<slug>/`
- `references` is non-empty

PDF alone is no longer required.

## Яндекс.Контест

1. Open the contest in the browser and copy the **student-facing URL** (`contest.yandex.ru`, `contest.yandex.com`, or `new.contest.yandex.ru`).
2. Add to `meta.yaml`:

```yaml
references:
  - kind: contest
    url: https://new.contest.yandex.ru/contests/98758
```

3. Optional custom label: `label: Задачи занятия` (defaults to «Яндекс.Контест»).
4. **Contest-only** lectures are valid: set `build: true`, add the reference, omit `main.tex`.

## Типы занятий

| Тип | Что добавить |
| --- | ------------ |
| Только слайды | `main.tex`, `slides/`, `meta.yaml` |
| Слайды + ноутбук | + `materials/*.ipynb` в `meta.yaml` |
| Слайды + контест | + `references` с `kind: contest` |
| Полный набор | слайды + `materials` + `references` |
| Только контест | `meta.yaml` с `kind: contest`, без `main.tex` |
| Только ноутбук | `meta.yaml` + `materials/*.ipynb`, без `main.tex` |

## Quick start

```bash
cp -R lectures/_template lectures/02-my-topic
# edit meta.yaml (set build: true), main.tex, slides/*
# add materials/ and references as needed
make session DIR=lectures/02-my-topic
make site   # regenerate index
```

## Theme

Load the shared theme in `main.tex`:

```latex
\usepackage[russian]{academicbeamer}  % or [english] — blue lecture theme
\setshorttitle{BelOAI \textbar\ Лекция 2}
```

See [`../latex/README.md`](../latex/README.md) for package options and customization.

## License

Lecture slides, metadata, and assets are [CC BY 4.0](../LICENSE-CC-BY-4.0). Copyright: Pavel Kasila and BelOAI Material Authors. See [`../LICENSE`](../LICENSE) and [`../LICENSING.md`](../LICENSING.md).
