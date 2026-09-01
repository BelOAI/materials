# AGENTS.md

Guidance for AI agents working in **beloai-materials** — BelOAI lecture slides (LaTeX Beamer → PDF) published to GitHub Pages.

## Repository purpose

| Audience | Primary doc | Goal |
| -------- | ----------- | ---- |
| Students | [`README.md`](README.md) | Find and download lecture PDFs |
| Maintainers | this file, [`lectures/README.md`](lectures/README.md) | Add/edit slides and publish |

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
    main.tex                # Driver only — no theme code here
    meta.yaml               # Site index metadata (Russian copy for students)
    slides/                 # Numbered \input{} fragments
    assets/                 # Optional images

scripts/                    # build-presentation.sh, build-all.sh, generate-site.py
_site/                      # Generated site (gitignored)
```

## Conventions

- **Line endings:** Unix LF only (see [`.gitattributes`](.gitattributes)).
- **Slide content** lives in `lectures/*/slides/*.tex`, not in theme files.
- **Theme/style** lives only in `latex/tex/latex/**/*.sty`.
- **Folder names:** `lectures/02-collections/` — numeric prefix controls site sort order.
- **Skip CI:** folders named `_…` or `meta.yaml` with `build: false`.
- **Hide from index:** `hidden: true` in `meta.yaml` (PDF still builds if `build: true`).
- **Generated artifacts:** never commit `main.pdf`, LaTeX aux files, or `_site/`.
- **Licensing:** path-based dual license — `lectures/` and student `README.md` are CC BY 4.0; `latex/`, `scripts/`, `Makefile`, and CI are MIT. Copyright: Pavel Kasila and BelOAI Material Authors. See [`LICENSE`](LICENSE) and [`LICENSING.md`](LICENSING.md).

## Basic workflows

### 1. Add a new lecture

```bash
cp -R lectures/_template lectures/02-collections
```

1. Edit `lectures/02-collections/meta.yaml` — set `build: true`, Russian `title`, `subtitle`, `description`, `date`.
2. Edit `main.tex` — title, author, `\setshorttitle{...}`, remove unused `\input{slides/...}` lines.
3. Replace or delete example slides in `slides/` (see [`lectures/_template/slides/README.md`](lectures/_template/slides/README.md) for patterns).
4. Build and verify:

```bash
make lecture DIR=lectures/02-collections
```

5. Update the lecture table in [`README.md`](README.md) (student-facing) with title, link, and short description.

### 2. Edit an existing lecture

1. Change files under `lectures/[NN]-name/slides/`.
2. Update `meta.yaml` if title, date, or site description changed.
3. Run `make lecture DIR=lectures/[NN]-name`.
4. Fix LaTeX errors from `main.log` — common issues: unclosed braces, `\verb` inside fragile contexts, missing `$` in math.

### 3. Build all lectures and regenerate the site

```bash
make          # or: make site
make clean    # remove aux files, PDFs, _site/
```

Pipeline:

1. `scripts/build-all.sh` — discovers publishable decks, runs `pdflatex` twice each, copies PDFs to `_site/pdfs/`, generates thumbnails via `pdftoppm`.
2. `scripts/generate-site.py` — writes Russian `_site/index.html` from `meta.yaml` + built PDFs.

Requires TeX Live (Cyrillic: `texlive-lang-cyrillic` for Russian decks) and `poppler-utils` locally; CI installs these on Ubuntu.

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

Do not embed theme code in lecture `main.tex` or slide files.

### 5. Change the public index page

Edit [`scripts/generate-site.py`](scripts/generate-site.py):

- `SITE` dict — Russian UI strings (page title, tagline, “Скачать PDF”, etc.).
- Card layout/CSS in `render_index()`.

Site copy comes from each lecture’s `meta.yaml` (`title`, `subtitle`, `description`, `date`).

Regenerate: `make site` (or `python3 scripts/generate-site.py` after PDFs exist in `_site/pdfs/`).

### 6. Publish to GitHub Pages

Push to `main`. Workflow [`.github/workflows/presentations.yml`](.github/workflows/presentations.yml):

- **Pull request:** build only, upload artifact.
- **Push to `main`:** build + deploy `_site/` to GitHub Pages.

Triggers on changes under `lectures/`, `latex/`, `scripts/`, workflow, `Makefile`, `latexmkrc`.

One-time repo setting: **Settings → Pages → Source: GitHub Actions**.

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

Build scripts set `TEXINPUTS=./latex/tex/latex//` so `\usepackage{academicbeamer}` resolves without `\input{../../...}`.

## meta.yaml (site index)

```yaml
title: "Название лекции"
subtitle: "Краткий подзаголовок"
date: "2026-09-01"
description: "1–2 предложения для студентов на сайте"
lang: ru
build: true
hidden: false
```

## Verification checklist

Before finishing a lecture or theme change:

- [ ] `make lecture DIR=lectures/…` exits 0 and produces `main.pdf`
- [ ] `make site` lists the deck on `_site/index.html` (unless `hidden: true`)
- [ ] `git status` shows no aux/PDF/`_site/` files staged
- [ ] Student [`README.md`](README.md) updated if a new public lecture was added
- [ ] Shell scripts remain LF (no `\r` — breaks `env: bash\r` in CI)

## What to avoid

- Committing build output (`main.pdf`, `_site/`, `*.aux`, `*.log`, …).
- Putting slide content into `.sty` files or theme into slide files.
- Editing [`README.md`](README.md) with LaTeX/CI instructions (use this file instead).
- Using `\input{../../latex/...}` for theme — use `\usepackage{academicbeamer}`.
- Renumbering lectures without updating student README links.

## Related docs

- [`lectures/README.md`](lectures/README.md) — lecture folder layout, `meta.yaml` schema
- [`latex/README.md`](latex/README.md) — theme file map and macros
- [`lectures/_template/slides/README.md`](lectures/_template/slides/README.md) — example slide patterns
- [`LICENSING.md`](LICENSING.md) — dual-license map and redistribution
- [`ATTRIBUTION.md`](ATTRIBUTION.md) — CC BY attribution examples
