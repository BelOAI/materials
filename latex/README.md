# LaTeX theme — Academic Beamer and assignment packages

In-repo TeX packages following a minimal [TDS layout](https://www.ctan.org/TDS-guidelines):

```
latex/tex/latex/
  beamer/
    beamerthemeAcademic.sty
    beamerinnerthemeAcademic.sty
    beamerouterthemeAcademic.sty
    beamercolorthemeAcademic.sty
    beamercolorthemeAcademicPractice.sty
  academicbeamer/
    academicbeamer.sty
  academicworksheet/
    academicworksheet.sty
  academicstatement/
    academicstatement.sty
```

Build scripts set:

```bash
export TEXINPUTS="$REPO_ROOT/latex/tex/latex//:${TEXINPUTS:-}"
```

so decks can `\usepackage{academicbeamer}` and assignments can `\usepackage{academicworksheet}` without relative `\input` paths.

## Package: `academicbeamer`

```latex
\usepackage[russian]{academicbeamer}           % lecture (blue, default)
\usepackage[practice,russian]{academicbeamer}  % practice (teal-green)
\setshorttitle{Footer text \textbar\ Lecture 1}
```

| Option | Description |
| ------ | ----------- |
| `russian` | `T2A` fontenc, Russian babel (default) |
| `english` | `T1` fontenc, English babel |
| `lecture` | Blue palette (default) |
| `practice` | Teal-green palette for practice sessions |

After loading, the **Academic** Beamer theme is active.

## Package: `academicworksheet`

Math home task printouts (`assignments/` with `assignment_type: math`):

```latex
\documentclass[a4paper,11pt]{article}
\usepackage[russian]{academicworksheet}
\setassignmentno{2}
```

| Option | Description |
| ------ | ----------- |
| `russian` | `T2A` fontenc, Russian babel (default) |
| `english` | `T1` fontenc, English babel |

Helper macros: `exercise` environment, `\answerlines{n}`, `\answerbox[height]`.

## Package: `academicstatement`

Coding problem statements (`assignments/` with `assignment_type: coding`):

```latex
\documentclass[a4paper,11pt]{article}
\usepackage[russian]{academicstatement}
\setassignmentno{2}
```

Environments: `problem`, `io`, `example`, `constraints`; macro `\sampleio{input}{output}`.

## Customisation

| Change | Edit |
| ------ | ---- |
| Lecture colours | `beamercolorthemeAcademic.sty` |
| Practice colours | `beamercolorthemeAcademicPractice.sty` |
| Frametitle / footline / margins | `beamerouterthemeAcademic.sty` |
| Blocks, lists, section dividers, macros | `beamerinnerthemeAcademic.sty` |
| Shared dependencies | `beamerthemeAcademic.sty` |
| Language / fonts | `academicbeamer.sty` |
| Math worksheet layout | `academicworksheet/academicworksheet.sty` |
| Coding statement layout | `academicstatement/academicstatement.sty` |

## Helper macros (inner theme)

- `\lead{text}` — highlighted lead-in
- `\tbd{text}` — placeholder marker
- `\orient` — “ориентир” tag for draft slides
- `\photoframe{width}{height}{caption}` — image placeholder
- `\orientnote[extra]` — disclaimer footnote for tables

## Local build

From repo root with `latexmkrc` in place:

```bash
cd lectures/01-project-setup
latexmk -pdf main.tex
```

Or use `make session DIR=assignments/02-derivatives` from the repository root.

## License

The Academic Beamer theme and assignment packages are [MIT](../LICENSE-MIT). Copyright: Pavel Kasila and BelOAI Material Authors. See [`../LICENSE`](../LICENSE) and [`../LICENSING.md`](../LICENSING.md).
