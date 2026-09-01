# Assignments (home tasks)

Home task assignment sheets live in `assignments/[number]-[name]/`. They are **printable PDF worksheets** (LaTeX `article`), not slide decks.

Two variants:

| Template | `assignment_type` | Package | Purpose |
| -------- | ----------------- | ------- | ------- |
| `_template-math/` | `math` | `academicworksheet` | Math exercises with answer space |
| `_template-coding/` | `coding` | `academicstatement` | Coding problem statements |

## Folder layout

```
assignments/02-linear-algebra/
  main.tex          # article driver
  meta.yaml         # site index metadata (assignment_type required)
  sections/         # numbered \input{} fragments
  materials/        # optional notebooks, data, starter code
```

See [`../lectures/README.md`](../lectures/README.md) for shared `meta.yaml` fields (`references`, `materials`, `date`, `build`, `hidden`).

## Required meta.yaml field

```yaml
assignment_type: math   # or coding
```

The `date` field is the **issue date** (when the assignment was given). It controls sort order on the site.

## Naming

Use a numeric prefix for human-readable labels (e.g. «Домашнее задание 2»), e.g. `01-warmup`, `02-derivatives`. **Site sort order** is by `date` in `meta.yaml`, not the folder prefix.

Folders starting with `_` (e.g. `_template-math`) are excluded from CI builds.

## Quick start

**Math worksheet:**

```bash
cp -R assignments/_template-math assignments/02-linear-algebra
# edit meta.yaml (build: true, assignment_type: math), main.tex, sections/*
make session DIR=assignments/02-linear-algebra
make site
```

**Coding problem statement:**

```bash
cp -R assignments/_template-coding assignments/02-two-sum
# edit meta.yaml (build: true, assignment_type: coding), main.tex, sections/*
make session DIR=assignments/02-two-sum
make site
```

## LaTeX packages

**Math** (`academicworksheet`):

```latex
\documentclass[a4paper,11pt]{article}
\usepackage[russian]{academicworksheet}
\setassignmentno{2}
```

Environments: `exercise`, `\answerlines{n}`, `\answerbox[height]`.

**Coding** (`academicstatement`):

```latex
\documentclass[a4paper,11pt]{article}
\usepackage[russian]{academicstatement}
\setassignmentno{2}
```

Environments: `problem`, `io`, `example`, `constraints`, `\sampleio{input}{output}`.

See [`../latex/README.md`](../latex/README.md) for all package options.

## License

Assignment sources, metadata, and assets are [CC BY 4.0](../LICENSE-CC-BY-4.0). Copyright: Pavel Kasila and BelOAI Material Authors. See [`../LICENSE`](../LICENSE) and [`../LICENSING.md`](../LICENSING.md).
