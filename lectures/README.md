# Lectures

Each presentation lives in `lectures/[number]-[name]/` with:

```
lectures/02-collections/
  main.tex       # driver: documentclass, package, metadata, \input{slides/...}
  meta.yaml      # site index metadata
  slides/        # numbered slide fragments
  assets/        # optional images (referenced via \graphicspath)
```

## Naming

Use a numeric prefix for sort order on the site index, e.g. `01-project-setup`, `02-collections`.

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
| `hidden` | no | `false` | Omit from public index (PDF still built if `build: true`) |

## Quick start

```bash
cp -R lectures/_template lectures/02-my-topic
# edit meta.yaml (set build: true), main.tex, slides/*
# remove example slide files you do not need (see _template/slides/README.md)
make lecture DIR=lectures/02-my-topic
```

## Theme

Load the shared theme in `main.tex`:

```latex
\usepackage[russian]{academicbeamer}  % or [english]
\setshorttitle{Footer text}
```

See [`../latex/README.md`](../latex/README.md) for package options and customization.

## License

Lecture slides, metadata, and assets are [CC BY 4.0](../LICENSE-CC-BY-4.0). Copyright: Pavel Kasila and BelOAI Material Authors. See [`../LICENSE`](../LICENSE) and [`../LICENSING.md`](../LICENSING.md).
