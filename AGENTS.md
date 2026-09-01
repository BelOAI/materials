# AGENTS.md

Guidance for AI agents working in **beloai-materials** — BelOAI lecture materials (LaTeX Beamer → PDF, notebooks, external links) published to GitHub Pages.

## Repository purpose

| Audience | Primary doc | Goal |
| -------- | ----------- | ---- |
| Students | [`README.md`](README.md) | Find lecture PDFs, notebooks, and links |
| Maintainers | this file, [`lectures/README.md`](lectures/README.md) | Add/edit slides, materials, and publish |

**Live site:** https://beloai.github.io/materials/

**Do not** turn [`README.md`](README.md) into a developer manual — keep it student-focused. Put maintainer details here or in nested READMEs.

## Layout

```text
latex/tex/latex/          # Beamer .sty theme (TDS layout)
  beamer/                   # beamerthemeAcademic + inner/outer/color
  academicbeamer/           # \usepackage{academicbeamer}

lectures/
  _template/                # Copy-paste scaffold (build: false, skipped by CI)
  [NN]-[name]/              # One deck per folder
    main.tex                # Driver only — optional for notebook/contest-only
    meta.yaml               # Site index metadata (Russian copy for students)
    slides/                 # Numbered \input{} fragments
    assets/                 # Optional images for slides
    materials/              # Notebooks, PDFs, archives → published to _site/

scripts/                    # build-presentation.sh, build-materials.sh,
                            # build-all.sh, generate-site.py, meta_parser.py
_site/                      # Generated site (gitignored)
  index.html
  pdfs/<slug>.pdf
  thumbs/<slug>.png
  materials/<slug>/         # Copied files + .ipynb → .html
```

## Conventions

- **Line endings:** Unix LF only (see [`.gitattributes`](.gitattributes)).
- **Slide content** lives in `lectures/*/slides/*.tex`, not in theme files.
- **Theme/style** lives only in `latex/tex/latex/**/*.sty`.
- **Folder names:** `lectures/02-collections/` — numeric prefix controls site sort order.
- **Skip CI:** folders named `_…` or `meta.yaml` with `build: false`.
- **Hide from index:** `hidden: true` in `meta.yaml` (artifacts still built if `build: true`).
- **Generated artifacts:** never commit `main.pdf`, LaTeX aux files, or `_site/`.
- **Licensing:** path-based dual license — `lectures/` and student `README.md` are CC BY 4.0; `latex/`, `scripts/`, `Makefile`, and CI are MIT. Copyright: Pavel Kasila and BelOAI Material Authors. See [`LICENSE`](LICENSE) and [`LICENSING.md`](LICENSING.md).

## meta.yaml (site index)

```yaml
title: "Название лекции"
subtitle: "Краткий подзаголовок"
date: "2026-09-01"
description: "1–2 предложения для студентов на сайте"
lang: ru
build: true
hidden: false

references:
  - kind: contest
    url: https://new.contest.yandex.ru/contests/98758
    label: Задачи занятия          # optional; defaults to «Яндекс.Контест»
  - kind: kaggle
    url: https://www.kaggle.com/competitions/example

materials:
  - path: materials/notebook.ipynb
    label: Jupyter Notebook
```

Known `references` kinds and default labels: `contest` → Яндекс.Контест, `kaggle` → Kaggle, `huggingface` → Hugging Face, `colab` → Google Colab.

## Lecture types and recipes

### Slides only

```bash
cp -R lectures/_template lectures/02-collections
```

1. Edit `meta.yaml` — `build: true`, Russian `title`, `subtitle`, `description`, `date`.
2. Edit `main.tex` — title, author, `\setshorttitle{...}`, remove unused `\input{slides/...}` lines.
3. Replace example slides in `slides/`.
4. Build: `make lecture DIR=lectures/02-collections`
5. Verify: `make site` → card on `_site/index.html` with «Скачать PDF».

### Slides + notebook

1. Create `materials/notebook.ipynb` in the lecture folder.
2. Add to `meta.yaml`:

```yaml
materials:
  - path: materials/notebook.ipynb
```

3. Build: `make lecture DIR=lectures/02-collections && make site`
4. Verify: card shows «Скачать PDF» and «Открыть ноутбук» (requires `jupyter nbconvert` locally).

### Slides + Яндекс.Контест

1. Copy the student-facing contest URL from the browser.
2. Add to `meta.yaml`:

```yaml
references:
  - kind: contest
    url: https://new.contest.yandex.ru/contests/98758
```

3. Build and verify: contest chip «Яндекс.Контест» appears first in the references row.

### Slides + notebook + links

Combine `materials` and `references` blocks. Example:

```yaml
references:
  - kind: contest
    url: https://new.contest.yandex.ru/contests/98758
  - kind: huggingface
    url: https://huggingface.co/datasets/example
materials:
  - path: materials/notebook.ipynb
```

### Contest-only (no slides)

1. Create folder with `meta.yaml` only — no `main.tex`.
2. Set `build: true` and a `references` entry with `kind: contest`.
3. Build: `make site`
4. Verify: lecture appears on index with contest chip, no PDF action.

### Notebook-only (no slides)

1. Create folder with `meta.yaml` and `materials/notebook.ipynb`.
2. List the notebook under `materials:` in `meta.yaml`.
3. Build: `make site`
4. Verify: card shows notebook actions, no PDF.

## Basic workflows

### 1. Add a new lecture

See recipes above. Always update the student [`README.md`](README.md) if a new public lecture was added.

### 2. Edit an existing lecture

1. Change files under `lectures/[NN]-name/slides/`, `materials/`, or `meta.yaml`.
2. Run `make lecture DIR=lectures/[NN]-name`.
3. Fix LaTeX errors from `main.log` if applicable.

### 3. Build all lectures and regenerate the site

```bash
make          # or: make site
make clean    # remove aux files, PDFs, _site/
```

Pipeline:

1. `scripts/build-all.sh` — for each publishable lecture dir: build PDF (if `main.tex`), copy materials (if declared), generate thumbnails.
2. `scripts/generate-site.py` — writes Russian `_site/index.html` from `meta.yaml` + built artifacts.

Requires TeX Live, `poppler-utils`, and `jupyter nbconvert` (for notebook HTML) locally; CI installs these on Ubuntu.

### 4. Change theme or shared macros

Edit files under `latex/tex/latex/`:

| Change | File |
| ------ | ---- |
| Colours | `beamer/beamercolorthemeAcademic.sty` |
| Header/footer/margins | `beamer/beamerouterthemeAcademic.sty` |
| Blocks, lists, `\lead`, `\photoframe` | `beamer/beamerinnerthemeAcademic.sty` |
| Package deps | `beamer/beamerthemeAcademic.sty` |
| Language/fonts | `academicbeamer/academicbeamer.sty` |

After theme changes, rebuild **all** publishable lectures:

```bash
make clean && make
```

### 5. Change the public index page

Edit [`scripts/generate-site.py`](scripts/generate-site.py):

- `SITE` dict — Russian UI strings.
- Card layout/CSS in `render_index()` and `render_lecture_row()`.

### 6. Publish to GitHub Pages

Push to `main`. Workflow [`.github/workflows/presentations.yml`](.github/workflows/presentations.yml):

- **Pull request:** build only, upload artifact.
- **Push to `main`:** build + deploy `_site/` to GitHub Pages.

## LaTeX driver template

```latex
\documentclass[aspectratio=169,11pt,t]{beamer}
\usepackage[russian]{academicbeamer}   % or [english]
\setshorttitle{BelOAI \textbar\ Занятие 2}

\graphicspath{{assets/}}

\title{...}
\subtitle{...}
\author{...}
\date{...}

\begin{document}
\input{slides/01-title}
% ...
\end{document}
```

## Verification checklist

Before finishing a lecture or theme change:

- [ ] `make lecture DIR=lectures/…` exits 0 (PDF if `main.tex` exists; materials if declared)
- [ ] `make site` lists the deck on `_site/index.html` (unless `hidden: true`)
- [ ] Contest / Kaggle / HF links visible when declared in `references`
- [ ] Notebook HTML opens when `jupyter nbconvert` is available
- [ ] PDF-optional lectures (contest-only, notebook-only) appear without broken PDF links
- [ ] `git status` shows no aux/PDF/`_site/` files staged
- [ ] Student [`README.md`](README.md) updated if a new public lecture was added
- [ ] Shell scripts remain LF (no `\r` — breaks `env: bash\r` in CI)

## What to avoid

- Committing build output (`main.pdf`, `_site/`, `*.aux`, `*.log`, …).
- Broken or placeholder contest URLs in `references`.
- Forgetting `build: true` on new lectures.
- Putting slide content into `.sty` files or theme into slide files.
- Editing [`README.md`](README.md) with LaTeX/CI instructions (use this file instead).
- Using `\input{../../latex/...}` for theme — use `\usepackage{academicbeamer}`.
- Renumbering lectures without updating student README links.

## Related docs

- [`lectures/README.md`](lectures/README.md) — lecture folder layout, `meta.yaml` schema
- [`latex/README.md`](latex/README.md) — theme file map and macros
- [`lectures/_template/slides/README.md`](lectures/_template/slides/README.md) — example slide patterns
- [`lectures/_template/materials/README.md`](lectures/_template/materials/README.md) — supplementary files
- [`LICENSING.md`](LICENSING.md) — dual-license map and redistribution
- [`ATTRIBUTION.md`](ATTRIBUTION.md) — CC BY attribution examples
