# LaTeX theme — Academic Beamer

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
```

Build scripts set:

```bash
export TEXINPUTS="$REPO_ROOT/latex/tex/latex//:${TEXINPUTS:-}"
```

so decks can `\usepackage{academicbeamer}` without relative `\input` paths.

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

## Customisation

| Change | Edit |
| ------ | ---- |
| Lecture colours | `beamercolorthemeAcademic.sty` |
| Practice colours | `beamercolorthemeAcademicPractice.sty` |
| Frametitle / footline / margins | `beamerouterthemeAcademic.sty` |
| Blocks, lists, section dividers, macros | `beamerinnerthemeAcademic.sty` |
| Shared dependencies | `beamerthemeAcademic.sty` |
| Language / fonts | `academicbeamer.sty` |

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

Or use `make lecture DIR=lectures/01-project-setup` from the repository root.

## License

The Academic Beamer theme is [MIT](../LICENSE-MIT). Copyright: Pavel Kasila and BelOAI Material Authors. See [`../LICENSE`](../LICENSE) and [`../LICENSING.md`](../LICENSING.md).
