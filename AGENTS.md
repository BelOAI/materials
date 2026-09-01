# AGENTS.md

Guidance for AI agents working in **beloai-materials** — BelOAI session materials (LaTeX Beamer → PDF, notebooks, external links) published to GitHub Pages.

## Repository purpose

| Audience | Primary doc | Goal |
| -------- | ----------- | ---- |
| Students | [`README.md`](README.md) | Find lecture and practice PDFs, assignment sheets, notebooks, and links |
| Maintainers | this file, [`lectures/README.md`](lectures/README.md), [`practices/README.md`](practices/README.md), [`assignments/README.md`](assignments/README.md) | Add/edit slides, assignments, materials, and publish |

**Live site:** https://beloai.github.io/materials/

**Do not** turn [`README.md`](README.md) into a developer manual — keep it student-focused. Put maintainer details here or in nested READMEs.

## Layout

```text
latex/tex/latex/          # Beamer + assignment .sty packages (TDS layout)
  beamer/                   # beamerthemeAcademic + inner/outer/color
  academicbeamer/           # \usepackage{academicbeamer}
  academicworksheet/        # \usepackage{academicworksheet} — math printouts
  academicstatement/          # \usepackage{academicstatement} — coding statements

lectures/                  # Theory / slide decks (blue theme)
  _template/                # Copy-paste scaffold (build: false, skipped by CI)
  [NN]-[name]/              # One deck per folder

practices/                  # Hands-on / contest sessions (teal theme)
  _template/
  [NN]-[name]/              # Independent numbering from lectures/

assignments/                # Home task sheets (amber theme on site)
  _template-math/             # Math worksheet scaffold (assignment_type: math)
  _template-coding/           # Coding problem statement scaffold (assignment_type: coding)
  [NN]-[name]/              # Independent numbering

  [NN]-[name]/              # Shared per-folder layout:
    main.tex                # Driver — article for assignments; beamer for lectures/practices
    meta.yaml               # Site index metadata (Russian copy for students)
    slides/                 # Lecture/practice slide fragments
    sections/               # Assignment content fragments
    assets/                 # Optional images for slides
    materials/              # Notebooks, PDFs, archives → published to _site/

scripts/                    # build-presentation.sh, build-materials.sh,
                            # build-all.sh, generate-site.py, meta_parser.py
_site/                      # Generated site (gitignored)
  index.html                # Unified list with filter tabs; newest first
  pdfs/<kind>/<name>.pdf
  thumbs/<kind>/<name>.png
  materials/<kind>/<name>/   # Copied files + .ipynb → .html
```

## Conventions

- **Line endings:** Unix LF only (see [`.gitattributes`](.gitattributes)).
- **Slide content** lives in `lectures/*/slides/*.tex` or `practices/*/slides/*.tex`, not in theme files.
- **Theme/style** lives only in `latex/tex/latex/**/*.sty`.
- **Session kind** is determined by parent directory (`lectures/`, `practices/`, or `assignments/`), not `meta.yaml`.
- **Folder names:** `lectures/02-collections/`, `practices/02-warmup/`, or `assignments/02-derivatives/` — numeric prefix is for human labels («Лекция 2», «Практика 2», «Домашнее задание 2»).
- **Site sort order** is by `date` + `slot`/`time` in `meta.yaml` (newest first); on the same date, assignments appear before lectures and practices.
- **Skip CI:** folders named `_…` or `meta.yaml` with `build: false`.
- **Hide from index:** `hidden: true` in `meta.yaml` (artifacts still built if `build: true`).
- **Generated artifacts:** never commit `main.pdf`, LaTeX aux files, or `_site/`.
- **Color schemes:** lectures use default `\usepackage{academicbeamer}` (blue); practices use `\usepackage[practice]{academicbeamer}` (teal-green); assignments use amber-brown site cards and `academicworksheet` / `academicstatement` LaTeX packages.
- **Licensing:** path-based dual license — `lectures/`, `practices/`, `assignments/`, and student `README.md` are CC BY 4.0; `latex/`, `scripts/`, `Makefile`, and CI are MIT. Copyright: Pavel Kasila and BelOAI Material Authors. See [`LICENSE`](LICENSE) and [`LICENSING.md`](LICENSING.md).

## meta.yaml (site index)

```yaml
title: "Название лекции"
subtitle: "Краткий подзаголовок"
date: "2026-09-01"
slot: "1"                    # optional: 1 → 11:25–12:50, 2 → 13:15–14:40
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

**Assignments** require an additional field:

```yaml
assignment_type: math    # math | coding
```

Use `date` as the issue date. Omit `slot` unless you need a custom `time`; assignments do not default to class slot times.

## Session types and recipes

### Slides only (lecture)

```bash
cp -R lectures/_template lectures/02-collections
```

1. Edit `meta.yaml` — `build: true`, Russian `title`, `subtitle`, `description`, `date`.
2. Edit `main.tex` — title, author, `\setshorttitle{BelOAI \textbar\ Лекция 2}`, remove unused `\input{slides/...}` lines.
3. Replace example slides in `slides/`.
4. Build: `make session DIR=lectures/02-collections`
5. Verify: `make site` → card on `_site/index.html` with «Скачать PDF».

### Slides only (practice)

```bash
cp -R practices/_template practices/02-warmup
```

Same steps as lecture, but under `practices/` and with `\usepackage[practice,russian]{academicbeamer}` in `main.tex`.

### Slides + notebook

1. Create `materials/notebook.ipynb` in the session folder.
2. Add to `meta.yaml`:

```yaml
materials:
  - path: materials/notebook.ipynb
```

3. Build: `make session DIR=lectures/02-collections && make site`
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

1. Create folder under `lectures/` or `practices/` with `meta.yaml` only — no `main.tex`.
2. Set `build: true` and a `references` entry with `kind: contest`.
3. Build: `make site`
4. Verify: session appears on index with contest chip, no PDF action.

### Notebook-only (no slides)

1. Create folder with `meta.yaml` and `materials/notebook.ipynb`.
2. List the notebook under `materials:` in `meta.yaml`.
3. Build: `make site`
4. Verify: card shows notebook actions, no PDF.

### Math worksheet (assignment)

```bash
cp -R assignments/_template-math assignments/02-derivatives
```

1. Edit `meta.yaml` — `build: true`, `assignment_type: math`, Russian `title`, `description`, `date`.
2. Edit `main.tex` — `\setassignmentno{2}`, title, remove unused `\input{sections/...}` lines.
3. Replace example content in `sections/`.
4. Build: `make session DIR=assignments/02-derivatives`
5. Verify: `make site` → amber card with «Скачать задание» and «Математика» badge.

### Coding problem statement (assignment)

```bash
cp -R assignments/_template-coding assignments/02-two-sum
```

Same steps, with `assignment_type: coding` and `\usepackage[russian]{academicstatement}` in `main.tex`. Card shows «Программирование» badge.

## Basic workflows

### 1. Add a new lecture or practice

See recipes above. Always update the student [`README.md`](README.md) when adding the first public item of a new kind.

### 2. Edit an existing session

1. Change files under `lectures/[NN]-name/`, `practices/[NN]-name/`, or `assignments/[NN]-name/` (`slides/`, `sections/`, `materials/`, or `meta.yaml`).
2. Run `make session DIR=lectures/[NN]-name` (or `practices/…`, `assignments/…`).
3. Fix LaTeX errors from `main.log` if applicable.

### 3. Build all sessions and regenerate the site

```bash
make          # or: make site
make clean    # remove aux files, PDFs, _site/
```

Pipeline:

1. `scripts/build-all.sh` — for each publishable dir under `lectures/`, `practices/`, and `assignments/`: build PDF (if `main.tex`), copy materials (if declared), generate thumbnails.
2. `scripts/generate-site.py` — writes Russian `_site/index.html` from `meta.yaml` + built artifacts; unified list with filter tabs, sorted by datetime descending.

Requires TeX Live, `poppler-utils`, and `jupyter nbconvert` (for notebook HTML) locally; CI installs these on Ubuntu.

### 4. Change theme or shared macros

Edit files under `latex/tex/latex/`:

| Change | File |
| ------ | ---- |
| Lecture colours | `beamer/beamercolorthemeAcademic.sty` |
| Practice colours | `beamer/beamercolorthemeAcademicPractice.sty` |
| Header/footer/margins | `beamer/beamerouterthemeAcademic.sty` |
| Blocks, lists, `\lead`, `\photoframe` | `beamer/beamerinnerthemeAcademic.sty` |
| Package deps | `beamer/beamerthemeAcademic.sty` |
| Language/fonts, practice option | `academicbeamer/academicbeamer.sty` |
| Math worksheet layout | `academicworksheet/academicworksheet.sty` |
| Coding statement layout | `academicstatement/academicstatement.sty` |

After theme changes, rebuild **all** publishable sessions:

```bash
make clean && make
```

### 5. Change the public index page

Edit [`scripts/generate-site.py`](scripts/generate-site.py):

- `SITE` dict — Russian UI strings.
- Card layout/CSS in `render_index()` and `render_session_row()`.

### 6. Publish to GitHub Pages

Push to `main`. Workflow [`.github/workflows/presentations.yml`](.github/workflows/presentations.yml):

- **Pull request:** build only, upload artifact.
- **Push to `main`:** build + deploy `_site/` to GitHub Pages.

## LaTeX driver templates

**Lecture:**

```latex
\documentclass[aspectratio=169,11pt,t]{beamer}
\usepackage[russian]{academicbeamer}   % or [english]
\setshorttitle{BelOAI \textbar\ Лекция 2}
```

**Practice:**

```latex
\documentclass[aspectratio=169,11pt,t]{beamer}
\usepackage[practice,russian]{academicbeamer}   % or [practice,english]
\setshorttitle{BelOAI \textbar\ Практика 2}
```

**Math assignment:**

```latex
\documentclass[a4paper,11pt]{article}
\usepackage[russian]{academicworksheet}
\setassignmentno{2}
```

**Coding assignment:**

```latex
\documentclass[a4paper,11pt]{article}
\usepackage[russian]{academicstatement}
\setassignmentno{2}
```

## Verification checklist

Before finishing a session or theme change:

- [ ] `make session DIR=lectures/…`, `practices/…`, or `assignments/…` exits 0 (PDF if `main.tex` exists; materials if declared)
- [ ] `make site` lists the session on `_site/index.html` in correct datetime order (unless `hidden: true`)
- [ ] Lecture cards are blue; practice cards are teal-green; assignment cards are amber-brown
- [ ] Filter tabs (Все / Лекции / Практики / Задания) work; hash deep-links (`#assignments`) work
- [ ] Assignment cards show subtype badge (Математика / Программирование) and «Выдано» date label
- [ ] Contest / Kaggle / HF links visible when declared in `references`
- [ ] Notebook HTML opens when `jupyter nbconvert` is available
- [ ] PDF-optional sessions (contest-only, notebook-only) appear without broken PDF links
- [ ] `git status` shows no aux/PDF/`_site/` files staged
- [ ] Student [`README.md`](README.md) updated if a new public kind was added
- [ ] Shell scripts remain LF (no `\r` — breaks `env: bash\r` in CI)

## What to avoid

- Committing build output (`main.pdf`, `_site/`, `*.aux`, `*.log`, …).
- Broken or placeholder contest URLs in `references`.
- Forgetting `build: true` on new sessions.
- Putting slide content into `.sty` files or theme into slide files.
- Mixing lectures, practices, and assignments in one folder — use the correct parent directory.
- Using Beamer `\documentclass{beamer}` in `assignments/` — use `article` with `academicworksheet` or `academicstatement`.
- Omitting `assignment_type` in `assignments/*/meta.yaml` — site generator skips the entry.
- Using `[practice]` option in `lectures/` decks or omitting it in `practices/` decks.
- Editing [`README.md`](README.md) with LaTeX/CI instructions (use this file instead).
- Using `\input{../../latex/...}` for theme — use `\usepackage{academicbeamer}`.
- Assuming folder numeric prefix controls site order — use `date` and `slot`/`time` in `meta.yaml`.

## Related docs

- [`lectures/README.md`](lectures/README.md) — lecture folder layout, `meta.yaml` schema
- [`practices/README.md`](practices/README.md) — practice folder layout and theme
- [`assignments/README.md`](assignments/README.md) — assignment folder layout and worksheet packages
- [`latex/README.md`](latex/README.md) — theme file map and macros
- [`lectures/_template/slides/README.md`](lectures/_template/slides/README.md) — example slide patterns
- [`lectures/_template/materials/README.md`](lectures/_template/materials/README.md) — supplementary files
- [`LICENSING.md`](LICENSING.md) — dual-license map and redistribution
- [`ATTRIBUTION.md`](ATTRIBUTION.md) — CC BY attribution examples
